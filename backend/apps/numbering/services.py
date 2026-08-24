"""
NumberingService (Phase P2.1).

Allocation is gapless and concurrency-safe: ``allocate`` advances the counter inside a
``transaction.atomic()`` holding a ``SELECT … FOR UPDATE`` lock on the sequence row, so two
concurrent callers are serialized and can never read the same ``current_value``. Because the
increment lives in the caller's transaction, an outer rollback also rolls back the increment —
so to keep document numbers truly gapless, callers should allocate **inside the same
transaction** that inserts the document. A standalone ``allocate`` commits immediately.

Period resets (yearly/monthly/daily) are detected by comparing the sequence's stored
``period_key`` to the token for the allocation instant; on change the counter restarts at
``start_value``.
"""
from __future__ import annotations

import uuid

from django.db import transaction
from django.utils import timezone

from apps.eventstore.events import DomainEventData, DomainEventFactory

from .models import NumberAllocation, NumberSequence


class NumberingError(Exception):
    """Raised for unknown/inactive sequences or invalid configuration."""


def _period_key(reset_scope: str, now) -> str:
    if reset_scope == NumberSequence.RESET_YEARLY:
        return now.strftime("%Y")
    if reset_scope == NumberSequence.RESET_MONTHLY:
        return now.strftime("%Y-%m")
    if reset_scope == NumberSequence.RESET_DAILY:
        return now.strftime("%Y-%m-%d")
    return ""  # RESET_NEVER → single, unbounded period


def _format(seq: NumberSequence, value: int, period_key: str) -> str:
    body = str(value).zfill(seq.padding)
    period_part = f"{period_key}-" if (seq.include_period_in_format and period_key) else ""
    return f"{seq.prefix}{period_part}{body}{seq.suffix}"


def _emit(seq: NumberSequence, event_type: str, payload: dict, actor_id=None):
    from apps.eventstore.models import DomainEvent
    version = DomainEvent.objects.filter(aggregate_id=seq.id).count() + 1
    DomainEventFactory.persist_one(DomainEventData(
        event_type=event_type, workspace_id=seq.workspace_id,
        aggregate_type="number_sequence", aggregate_id=seq.id, version=version,
        payload={"key": seq.key, **payload},
        actor_id=uuid.UUID(str(actor_id)) if actor_id else uuid.UUID(int=0)))


class NumberingService:
    @staticmethod
    def ensure_sequence(workspace_id, key, *, defaults=None, created_by=None) -> NumberSequence:
        """Idempotently register a sequence. Engines call this to lazily provision their own
        counters (e.g. accounting ensures ``journal_entry``) without forcing manual setup."""
        defaults = dict(defaults or {})
        defaults.setdefault("is_system", True)
        seq, created = NumberSequence.objects.get_or_create(
            workspace_id=workspace_id, key=key,
            defaults={**defaults, "created_by": created_by})
        return seq

    @staticmethod
    def peek(workspace_id, key, *, now=None) -> str:
        """Preview the next formatted number WITHOUT consuming it (no lock, no write)."""
        now = now or timezone.now()
        seq = NumberSequence.objects.filter(workspace_id=workspace_id, key=key).first()
        if seq is None:
            raise NumberingError(f"Number sequence {key!r} is not defined.")
        pk = _period_key(seq.reset_scope, now)
        is_new_period = (not seq.initialized) or pk != seq.period_key
        next_value = seq.start_value if is_new_period else seq.current_value + seq.increment
        return _format(seq, next_value, pk)

    @staticmethod
    def allocate(workspace_id, key, *, actor_id=None, context=None, now=None) -> str:
        """Issue the next number for ``key``. Serialized + gapless under concurrency."""
        now = now or timezone.now()
        with transaction.atomic():
            seq = (NumberSequence.objects
                   .select_for_update()
                   .filter(workspace_id=workspace_id, key=key)
                   .first())
            if seq is None:
                raise NumberingError(f"Number sequence {key!r} is not defined.")
            if not seq.is_active:
                raise NumberingError(f"Number sequence {key!r} is inactive.")

            pk = _period_key(seq.reset_scope, now)
            if (not seq.initialized) or pk != seq.period_key:
                # First-ever allocation or a new period → restart the counter at start_value.
                value = seq.start_value
                seq.period_key = pk
                seq.initialized = True
            else:
                value = seq.current_value + seq.increment
            seq.current_value = value
            seq.save(update_fields=["current_value", "period_key", "initialized", "updated_at"])

            formatted = _format(seq, value, pk)
            alloc = NumberAllocation.objects.create(
                workspace_id=workspace_id, sequence=seq, key=seq.key,
                formatted=formatted, value=value, period_key=pk,
                context=dict(context or {}),
                allocated_by=uuid.UUID(str(actor_id)) if actor_id else None)
            _emit(seq, "numbering.allocated",
                  {"formatted": formatted, "value": value, "period_key": pk,
                   "allocation_id": str(alloc.id)}, actor_id=actor_id)
            return formatted

    @staticmethod
    def reset(workspace_id, key, *, to_value=None, actor_id=None) -> NumberSequence:
        """Admin reset of the counter (audited). ``to_value`` defaults to ``start_value - increment``
        so the next allocation yields ``start_value``."""
        with transaction.atomic():
            seq = (NumberSequence.objects
                   .select_for_update()
                   .filter(workspace_id=workspace_id, key=key)
                   .first())
            if seq is None:
                raise NumberingError(f"Number sequence {key!r} is not defined.")
            previous = seq.current_value
            seq.current_value = seq.start_value - seq.increment if to_value is None else int(to_value)
            seq.save(update_fields=["current_value", "updated_at"])
            _emit(seq, "numbering.reset",
                  {"previous_value": previous, "current_value": seq.current_value},
                  actor_id=actor_id)
            return seq
