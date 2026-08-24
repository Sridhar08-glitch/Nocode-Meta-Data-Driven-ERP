"""
Credit Engine services (F3).

``CreditService`` is the single reusable entry point for issuing and voiding credits. It REUSES
the platform engines and adds no accounting of its own:
  * account codes  → ``apps.ledger.provisioning.ensure_accounting_settings`` (no hardcoded codes)
  * gapless number → ``apps.numbering.NumberingService`` (inside the write transaction)
  * balanced post  → ``apps.ledger.GLBus`` (the single double-entry engine)
  * domain events  → ``apps.eventstore`` (via the shared ``emit_event`` helper)

A credit is idempotent on ``external_ref``: re-issuing with the same token returns the existing
credit instead of double-crediting / double-posting. A correction is ``void`` (a GL reversal),
never an edit — posted books stay immutable.
"""
from __future__ import annotations

import uuid

from django.db import transaction
from django.utils import timezone

from apps.ledger.provisioning import ensure_accounting_settings
from apps.solution_templates.documents import emit_event

from .models import KIND_ACCOUNTS, KIND_SEQUENCES, CreditNote
from .money import money


class CreditError(Exception):  # noqa: N818 — domain error
    pass


def _uid(actor_id):
    return uuid.UUID(str(actor_id)) if actor_id else None


class CreditService:
    @staticmethod
    def ensure_sequences(workspace_id, *, actor_id=None):
        """Idempotently register the credit numbering sequences (CN-/SCH-/WO-/RF-)."""
        from apps.numbering.services import NumberingService
        seen = set()
        for _kind, (key, prefix) in KIND_SEQUENCES.items():
            if key in seen:
                continue
            seen.add(key)
            NumberingService.ensure_sequence(
                workspace_id, key,
                defaults={"prefix": prefix, "padding": 6}, created_by=actor_id)

    @staticmethod
    def issue(*, workspace_id, kind, amount, subject_ref="", applies_to_ref="", reason="",
              external_ref="", debit_account=None, credit_account=None, currency="",
              date=None, actor_id=None) -> CreditNote:
        """Issue a credit (discount/scholarship/waiver/credit_note/write_off/refund).

        Posts a balanced GL entry (Dr contra-revenue/expense/refund, Cr receivable/cash),
        allocates a gapless number, emits ``credit.<kind>.issued``. Idempotent on ``external_ref``.
        """
        if kind not in KIND_ACCOUNTS:
            raise CreditError(f"Unknown credit kind: {kind!r}")
        amount = money(amount)
        if amount <= 0:
            raise CreditError("Credit amount must be positive.")

        settings = ensure_accounting_settings(workspace_id, actor_id=actor_id)
        dr_field, cr_field = KIND_ACCOUNTS[kind]
        dr = debit_account or getattr(settings, dr_field)
        cr = credit_account or getattr(settings, cr_field)
        seq_key, seq_prefix = KIND_SEQUENCES[kind]

        with transaction.atomic():
            # Idempotency: same external token → return the existing (non-void) credit.
            if external_ref:
                existing = (CreditNote.objects.select_for_update()
                            .filter(workspace_id=workspace_id, external_ref=external_ref)
                            .exclude(status=CreditNote.VOID).first())
                if existing is not None:
                    return existing

            from apps.numbering.services import NumberingService
            NumberingService.ensure_sequence(
                workspace_id, seq_key,
                defaults={"prefix": seq_prefix, "padding": 6}, created_by=actor_id)
            number = NumberingService.allocate(
                workspace_id, seq_key, actor_id=actor_id,
                context={"source_module": "credits", "source_ref": kind})

            note = CreditNote.objects.create(
                workspace_id=workspace_id, kind=kind, number=number,
                subject_ref=str(subject_ref or ""), applies_to_ref=str(applies_to_ref or ""),
                amount=amount, currency=currency, reason=reason,
                gl_debit_account=dr, gl_credit_account=cr,
                external_ref=str(external_ref or ""), status=CreditNote.POSTED,
                created_by=_uid(actor_id))
            note.journal_entry_id = CreditService._post_gl(
                workspace_id, note, date or timezone.now().date(), actor_id)
            note.save(update_fields=["journal_entry_id"])

        emit_event(workspace_id, "credit_note", note.id, f"credit.{kind}.issued",
                   {"number": number, "amount": str(amount), "kind": kind,
                    "applies_to": note.applies_to_ref}, actor_id)
        return note

    @staticmethod
    def _post_gl(workspace_id, note, date, actor_id):
        from apps.ledger.services import GLBus, LedgerError, emit_post_failure
        try:
            entry = GLBus.post(
                workspace_id, date=date, lines=[
                    {"account_code": note.gl_debit_account, "debit": str(note.amount),
                     "memo": f"{note.kind} {note.number}", "partner_ref": note.subject_ref},
                    {"account_code": note.gl_credit_account, "credit": str(note.amount),
                     "memo": f"{note.kind} {note.number}", "partner_ref": note.subject_ref}],
                memo=note.reason or note.get_kind_display(), currency=note.currency,
                source_module="credits", source_ref=note.number, actor_id=actor_id)
            return entry.id if entry is not None else None
        except LedgerError as exc:
            emit_post_failure(workspace_id, module="credits", source_ref=note.number,
                              error=str(exc), actor_id=actor_id)
            raise

    @staticmethod
    def void(*, workspace_id, credit_id, reason="", actor_id=None) -> CreditNote:
        """Void a posted credit — posts a reversing GL entry (books stay immutable) and marks the
        credit void. Idempotent: voiding an already-void credit returns it unchanged."""
        from apps.ledger.services import GLBus, LedgerError, emit_post_failure
        with transaction.atomic():
            note = (CreditNote.objects.select_for_update()
                    .filter(workspace_id=workspace_id, id=credit_id).first())
            if note is None:
                raise CreditError("Credit not found.")
            if note.status == CreditNote.VOID:
                return note
            if note.journal_entry_id:
                try:
                    rev = GLBus.reverse(
                        workspace_id, note.journal_entry_id,
                        memo=reason or f"Void {note.number}", actor_id=actor_id)
                    note.reversal_entry_id = rev.id if rev is not None else None
                except LedgerError as exc:
                    emit_post_failure(workspace_id, module="credits", source_ref=note.number,
                                      error=str(exc), actor_id=actor_id)
                    raise
            note.status = CreditNote.VOID
            note.save(update_fields=["status", "reversal_entry_id", "updated_at"])
        emit_event(workspace_id, "credit_note", note.id, f"credit.{note.kind}.voided",
                   {"number": note.number, "amount": str(note.amount)}, actor_id)
        return note
