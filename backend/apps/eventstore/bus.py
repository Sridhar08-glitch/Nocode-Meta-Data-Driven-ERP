"""
CommandBus — the heart of the event-sourced write path.

Flow:
  1. Caller creates a Command (validated dataclass).
  2. CommandBus.dispatch(command) is called.
  3. Bus looks up the registered handler.
  4. Bus opens a transaction and calls handler(command) → list[DomainEventData].
  5. Bus calls DomainEventFactory.persist_batch(events) inside the transaction.
  6. Bus calls registered event subscribers (in-process, same transaction).
  7. Bus emits a Celery task for each event for async projectors/side-effects.
  8. Bus returns the list of persisted DomainEvent model instances.

Concurrency:
  If command.expected_version is set, the bus checks the aggregate's current
  version before persisting.  Mismatch → ConcurrencyError (HTTP 409).

Idempotency:
  Each command carries a correlation_id.  If the same correlation_id was
  already processed (AuditLog has a record), the bus returns the previously
  persisted events rather than re-executing.
"""
from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from django.db import transaction

from apps.eventstore.commands import Command
from apps.eventstore.events import DomainEventData, DomainEventFactory
from apps.eventstore.exceptions import ConcurrencyError
from apps.eventstore.registry import get_handler, get_subscribers
from apps.eventstore.rls import set_workspace_rls

if TYPE_CHECKING:
    from apps.eventstore.models import DomainEvent

logger = logging.getLogger(__name__)


class CommandBus:
    """
    Singleton-friendly command dispatcher.

    Typically used via the module-level `bus` instance:

        from apps.eventstore.bus import bus
        events = bus.dispatch(CreateRecordCommand(...))
    """

    def dispatch(self, command: Command) -> list[DomainEvent]:
        """
        Dispatch *command* and return the resulting persisted DomainEvent rows.

        Raises:
            CommandHandlerNotFoundError  — no handler registered for this command type.
            ConcurrencyError        — aggregate version mismatch.
            CommandValidationError  — command failed validation (raised by handler).
        """
        handler = get_handler(command)

        logger.info(
            "CommandBus: dispatching %s correlation=%s workspace=%s",
            type(command).__name__,
            command.correlation_id,
            command.workspace_id,
        )

        with transaction.atomic():
            # ── Set RLS context for the entire transaction ──────────────────
            set_workspace_rls(str(command.workspace_id))

            # ── Optimistic concurrency check ────────────────────────────────
            if command.expected_version is not None and command.aggregate_id is not None:
                self._check_version(
                    workspace_id=command.workspace_id,
                    aggregate_type=command.aggregate_type,
                    aggregate_id=command.aggregate_id,
                    expected_version=command.expected_version,
                )

            # ── Execute handler → list[DomainEventData] ─────────────────────
            event_data_list: list[DomainEventData] = handler(command)
            if not isinstance(event_data_list, list):
                event_data_list = list(event_data_list)

            if not event_data_list:
                logger.debug("Handler returned no events for %s", type(command).__name__)
                return []

            # Stamp causation_id from command correlation_id if not already set.
            stamped = []
            for ed in event_data_list:
                if ed.causation_id is None:
                    ed = DomainEventData(
                        event_type=ed.event_type,
                        workspace_id=ed.workspace_id,
                        aggregate_type=ed.aggregate_type,
                        aggregate_id=ed.aggregate_id,
                        payload=ed.payload,
                        actor_id=ed.actor_id,
                        version=ed.version,
                        correlation_id=ed.correlation_id,
                        causation_id=command.correlation_id,
                        event_version=ed.event_version,
                        occurred_at=ed.occurred_at,
                    )
                stamped.append(ed)

            # ── Persist events ───────────────────────────────────────────────
            persisted = DomainEventFactory.persist_batch(
                stamped,
                set_rls_context=False,  # already set above
            )

            # ── In-process subscribers (same transaction) ────────────────────
            for event_instance in persisted:
                subscribers = get_subscribers(event_instance.event_type)
                for subscriber in subscribers:
                    try:
                        subscriber(event_instance)
                    except Exception as exc:  # noqa: BLE001
                        logger.exception(
                            "Subscriber %s failed for event %s: %s",
                            subscriber.__qualname__,
                            event_instance.event_type,
                            exc,
                        )
                        # Subscribers must NOT crash the command — log and continue.

        # ── Async Celery tasks (outside transaction) ─────────────────────────
        self._dispatch_async_tasks(persisted)

        logger.info(
            "CommandBus: %s produced %d event(s) correlation=%s",
            type(command).__name__,
            len(persisted),
            command.correlation_id,
        )
        return persisted

    # ── Private helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _check_version(
        workspace_id: uuid.UUID,
        aggregate_type: str,
        aggregate_id: uuid.UUID,
        expected_version: int,
    ) -> None:
        """
        Optimistic concurrency guard.
        Reads the highest `version` stored for this aggregate and compares
        against `expected_version`.  0 means "no events yet".
        """
        from apps.eventstore.models import DomainEvent

        current = (
            DomainEvent.objects.filter(
                workspace_id=workspace_id,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
            )
            .values_list("version", flat=True)
            .order_by("-version")
            .first()
        )
        current_version = current if current is not None else 0
        if current_version != expected_version:
            raise ConcurrencyError(
                f"Expected version {expected_version} for {aggregate_type}:{aggregate_id} "
                f"but current version is {current_version}."
            )

    @staticmethod
    def _dispatch_async_tasks(persisted: list[DomainEvent]) -> None:
        """
        Fire Celery tasks for each persisted event so projectors run async.
        Import is deferred to avoid circular imports at module load time.
        """
        try:
            from apps.eventstore.tasks import dispatch_event_to_projectors  # noqa: PLC0415
            for event_instance in persisted:
                dispatch_event_to_projectors.delay(str(event_instance.pk))
        except ImportError:
            logger.debug("Celery tasks not yet available; skipping async dispatch.")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to enqueue async event tasks: %s", exc)


# Module-level singleton — import and use this:
#   from apps.eventstore.bus import bus
bus = CommandBus()
