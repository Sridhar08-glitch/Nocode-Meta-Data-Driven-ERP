"""
Collections Engine services (F2).

``CollectionsService`` builds and services due schedules, REUSING the platform engines:
  * account codes → ``apps.ledger.provisioning.ensure_accounting_settings``
  * gapless number → ``apps.numbering.NumberingService``
  * late-fee post  → ``apps.ledger.GLBus`` (Dr Receivable / Cr Late-fee income — the ONLY GL this
    engine posts; payment cash is the payment document's job, never double-posted here)
  * reminders      → ``apps.notifications.NotificationService`` (best-effort)
  * domain events  → ``apps.eventstore`` (via the shared ``emit_event`` helper)

Idempotency: a plan is idempotent on ``external_ref``; a late fee is charged at most once per
installment (a boolean guard + row lock). Beats filter by ``workspace_id`` explicitly (ORM is the
first isolation line; RLS is the backstop).
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.ledger.provisioning import ensure_accounting_settings
from apps.solution_templates.documents import emit_event

from .dates import due_date_for
from .models import Installment, InstallmentPlan
from .money import money


class CollectionsError(Exception):  # noqa: N818 — domain error
    pass


def _uid(actor_id):
    return uuid.UUID(str(actor_id)) if actor_id else None


def _split_amount(total: Decimal, n: int) -> list[Decimal]:
    """Split ``total`` into ``n`` 2-dp parts; the last absorbs any rounding remainder."""
    each = money(total / n)
    parts = [each] * (n - 1)
    parts.append(money(total - each * (n - 1)))
    return parts


class CollectionsService:
    # ── setup ────────────────────────────────────────────────────────────────
    @staticmethod
    def ensure_sequences(workspace_id, *, actor_id=None):
        from apps.numbering.services import NumberingService
        NumberingService.ensure_sequence(
            workspace_id, "installment_plan",
            defaults={"prefix": "PLAN-", "padding": 6}, created_by=actor_id)

    # ── create plan + schedule ────────────────────────────────────────────────
    @staticmethod
    def create_plan(*, workspace_id, total_amount, num_installments, start_date,
                    frequency="monthly", interval_days=0, subject_ref="", source_document_ref="",
                    notify_ref="", grace_days=0, late_fee_type="none", late_fee_value=0,
                    currency="", external_ref="", receivable_account=None,
                    late_fee_income_account=None, actor_id=None) -> InstallmentPlan:
        total = money(total_amount)
        n = int(num_installments or 0)
        if total <= 0:
            raise CollectionsError("Plan total must be positive.")
        if n < 1:
            raise CollectionsError("A plan needs at least one installment.")

        settings = ensure_accounting_settings(workspace_id, actor_id=actor_id)
        recv = receivable_account or settings.default_receivable_account
        lfi = late_fee_income_account or settings.default_late_fee_income_account

        with transaction.atomic():
            if external_ref:
                existing = (InstallmentPlan.objects.select_for_update()
                            .filter(workspace_id=workspace_id, external_ref=external_ref)
                            .exclude(status=InstallmentPlan.CANCELLED).first())
                if existing is not None:
                    return existing

            from apps.numbering.services import NumberingService
            NumberingService.ensure_sequence(
                workspace_id, "installment_plan",
                defaults={"prefix": "PLAN-", "padding": 6}, created_by=actor_id)
            number = NumberingService.allocate(
                workspace_id, "installment_plan", actor_id=actor_id,
                context={"source_module": "collections", "source_ref": "plan"})

            plan = InstallmentPlan.objects.create(
                workspace_id=workspace_id, number=number, subject_ref=str(subject_ref or ""),
                source_document_ref=str(source_document_ref or ""), notify_ref=str(notify_ref or ""),
                total_amount=total, currency=currency, num_installments=n, frequency=frequency,
                interval_days=int(interval_days or 0), start_date=start_date,
                grace_days=int(grace_days or 0), late_fee_type=late_fee_type,
                late_fee_value=money(late_fee_value), receivable_account=recv,
                late_fee_income_account=lfi, external_ref=str(external_ref or ""),
                status=InstallmentPlan.ACTIVE, created_by=_uid(actor_id))

            parts = _split_amount(total, n)
            Installment.objects.bulk_create([
                Installment(
                    workspace_id=workspace_id, plan_id=plan.id, seq=i + 1,
                    due_date=due_date_for(start_date, frequency, i, interval_days),
                    amount=parts[i])
                for i in range(n)])

        emit_event(workspace_id, "collection_plan", plan.id, "collections.plan.created",
                   {"number": number, "total": str(total), "installments": n}, actor_id)
        return plan

    @staticmethod
    def plan_installments(workspace_id, plan_id):
        return list(Installment.objects.filter(workspace_id=workspace_id, plan_id=plan_id)
                    .order_by("seq"))

    # ── payment tracking (no GL — the payment document posts the cash) ─────────
    @staticmethod
    def record_payment(*, workspace_id, amount, plan_id=None, installment_id=None,
                       paid_at=None, actor_id=None) -> dict:
        amt = money(amount)
        if amt <= 0:
            raise CollectionsError("Payment amount must be positive.")
        paid_at = paid_at or timezone.now()
        updated = []
        with transaction.atomic():
            if installment_id:
                qs = (Installment.objects.select_for_update()
                      .filter(workspace_id=workspace_id, id=installment_id))
            elif plan_id:
                qs = (Installment.objects.select_for_update()
                      .filter(workspace_id=workspace_id, plan_id=plan_id)
                      .exclude(status=Installment.PAID).order_by("seq"))
            else:
                raise CollectionsError("record_payment needs plan_id or installment_id.")
            remaining = amt
            for inst in qs:
                if remaining <= 0:
                    break
                outstanding = inst.amount + inst.late_fee_amount - inst.paid_amount
                if outstanding <= 0:
                    continue
                applied = min(remaining, outstanding)
                inst.paid_amount = money(inst.paid_amount + applied)
                remaining = money(remaining - applied)
                if inst.paid_amount >= inst.amount + inst.late_fee_amount:
                    inst.status = Installment.PAID
                    inst.paid_at = paid_at
                else:
                    inst.status = Installment.PARTIAL
                inst.save(update_fields=["paid_amount", "status", "paid_at", "updated_at"])
                updated.append(inst)
            # Complete the plan when every installment is settled.
            if plan_id or (updated and installment_id):
                pid = plan_id or updated[0].plan_id
                open_left = Installment.objects.filter(
                    workspace_id=workspace_id, plan_id=pid).exclude(
                    status__in=[Installment.PAID, Installment.WAIVED]).exists()
                if not open_left:
                    InstallmentPlan.objects.filter(
                        workspace_id=workspace_id, id=pid).update(
                        status=InstallmentPlan.COMPLETED)
        emit_event(workspace_id, "collection_plan", plan_id or (updated[0].plan_id if updated else uuid.uuid4()),
                   "collections.payment.recorded",
                   {"amount": str(amt), "applied_to": len(updated)}, actor_id)
        return {"applied": str(money(amt - remaining)), "unapplied": str(remaining),
                "installments_updated": len(updated)}

    # ── late fees (the one GL this engine posts) ──────────────────────────────
    @staticmethod
    def charge_late_fee(*, workspace_id, installment_id, as_of=None, actor_id=None):
        as_of = as_of or timezone.now().date()
        with transaction.atomic():
            inst = (Installment.objects.select_for_update()
                    .filter(workspace_id=workspace_id, id=installment_id).first())
            if inst is None:
                raise CollectionsError("Installment not found.")
            if inst.late_fee_charged:
                return None
            plan = InstallmentPlan.objects.filter(
                workspace_id=workspace_id, id=inst.plan_id).first()
            if plan is None or plan.late_fee_type == "none" or plan.status != InstallmentPlan.ACTIVE:
                return None
            outstanding = inst.amount + inst.late_fee_amount - inst.paid_amount
            if outstanding <= 0:
                return None
            if plan.late_fee_type == "flat":
                fee = money(plan.late_fee_value)
            else:  # percent of outstanding
                fee = money(outstanding * plan.late_fee_value / Decimal("100"))
            if fee <= 0:
                return None
            je_id = CollectionsService._post_late_fee_gl(
                workspace_id, plan, inst, fee, as_of, actor_id)
            inst.late_fee_amount = money(inst.late_fee_amount + fee)
            inst.late_fee_charged = True
            inst.late_fee_journal_entry_id = je_id
            if inst.status in (Installment.PENDING, Installment.PARTIAL):
                inst.status = Installment.OVERDUE
            inst.save(update_fields=["late_fee_amount", "late_fee_charged",
                                     "late_fee_journal_entry_id", "status", "updated_at"])
        emit_event(workspace_id, "installment", inst.id, "collections.late_fee.charged",
                   {"plan": str(plan.id), "seq": inst.seq, "fee": str(fee)}, actor_id)
        return inst

    @staticmethod
    def _post_late_fee_gl(workspace_id, plan, inst, fee, as_of, actor_id):
        from apps.ledger.services import GLBus, LedgerError, emit_post_failure
        try:
            entry = GLBus.post(
                workspace_id, date=as_of, lines=[
                    {"account_code": plan.receivable_account, "debit": str(fee),
                     "memo": f"Late fee {plan.number} #{inst.seq}", "partner_ref": plan.subject_ref},
                    {"account_code": plan.late_fee_income_account, "credit": str(fee),
                     "memo": f"Late fee {plan.number} #{inst.seq}", "partner_ref": plan.subject_ref}],
                memo="Late fee", source_module="collections",
                source_ref=f"LF-{inst.id}", actor_id=actor_id)
            return entry.id if entry is not None else None
        except LedgerError as exc:
            emit_post_failure(workspace_id, module="collections", source_ref=f"LF-{inst.id}",
                              error=str(exc), actor_id=actor_id)
            raise

    # ── beats: overdue marking, reminders, late fees, dunning ─────────────────
    @staticmethod
    def _open_installments(workspace_id=None, as_of=None):
        qs = Installment.objects.filter(
            status__in=[Installment.PENDING, Installment.PARTIAL, Installment.OVERDUE])
        if workspace_id:
            qs = qs.filter(workspace_id=workspace_id)
        return qs

    @staticmethod
    def run_late_fees(*, workspace_id=None, as_of=None, actor_id=None) -> int:
        as_of = as_of or timezone.now().date()
        plans = {p.id: p for p in InstallmentPlan.objects.filter(
            **({"workspace_id": workspace_id} if workspace_id else {}),
            status=InstallmentPlan.ACTIVE).exclude(late_fee_type="none")}
        count = 0
        for inst in CollectionsService._open_installments(workspace_id, as_of).filter(
                late_fee_charged=False, plan_id__in=list(plans.keys())):
            plan = plans.get(inst.plan_id)
            if plan is None:
                continue
            import datetime as _dt
            if inst.due_date + _dt.timedelta(days=plan.grace_days) >= as_of:
                continue  # still within grace
            charged = CollectionsService.charge_late_fee(
                workspace_id=inst.workspace_id, installment_id=inst.id, as_of=as_of,
                actor_id=actor_id)
            if charged is not None:
                count += 1
        return count

    @staticmethod
    def run_reminders(*, workspace_id=None, as_of=None, window_days=3, actor_id=None) -> int:
        import datetime as _dt
        as_of = as_of or timezone.now().date()
        horizon = as_of + _dt.timedelta(days=window_days)
        count = 0
        qs = CollectionsService._open_installments(workspace_id, as_of).filter(
            due_date__lte=horizon, reminder_sent_at__isnull=True)
        plans = {p.id: p for p in InstallmentPlan.objects.filter(
            id__in=list(qs.values_list("plan_id", flat=True)))}
        for inst in qs:
            plan = plans.get(inst.plan_id)
            if plan is None:
                continue
            CollectionsService._notify(workspace_id=inst.workspace_id, plan=plan, inst=inst,
                                       as_of=as_of)
            inst.reminder_sent_at = timezone.now()
            inst.save(update_fields=["reminder_sent_at", "updated_at"])
            emit_event(inst.workspace_id, "installment", inst.id, "collections.reminder.sent",
                       {"plan": str(plan.id), "seq": inst.seq, "due_date": str(inst.due_date)},
                       actor_id)
            count += 1
        return count

    @staticmethod
    def _notify(*, workspace_id, plan, inst, as_of):
        """Best-effort reminder via the Notification engine. The actual channel/template is a
        package concern; Core only fires it when the plan carries a recipient (``notify_ref``)."""
        if not plan.notify_ref:
            return
        try:
            from apps.notifications.services import NotificationService
            NotificationService.send(
                recipient_id=plan.notify_ref, recipient_type="member",
                template_slug="collections_reminder",
                context={"plan_number": plan.number, "seq": inst.seq,
                         "amount": str(inst.outstanding), "due_date": str(inst.due_date)},
                workspace_id=workspace_id)
        except Exception:  # noqa: BLE001 — reminders never break the beat
            pass

    @staticmethod
    def run_dunning(*, workspace_id=None, as_of=None, actor_id=None) -> int:
        as_of = as_of or timezone.now().date()
        count = 0
        for inst in CollectionsService._open_installments(workspace_id, as_of).filter(
                due_date__lt=as_of):
            if inst.amount + inst.late_fee_amount - inst.paid_amount <= 0:
                continue
            with transaction.atomic():
                locked = Installment.objects.select_for_update().get(
                    workspace_id=inst.workspace_id, id=inst.id)
                if locked.status not in (Installment.PENDING, Installment.PARTIAL,
                                         Installment.OVERDUE):
                    continue
                locked.dunning_level += 1
                if locked.status != Installment.OVERDUE:
                    locked.status = Installment.OVERDUE
                locked.save(update_fields=["dunning_level", "status", "updated_at"])
            emit_event(inst.workspace_id, "installment", inst.id, "collections.dunning.escalated",
                       {"plan": str(inst.plan_id), "seq": inst.seq,
                        "level": locked.dunning_level,
                        "overdue_days": (as_of - inst.due_date).days}, actor_id)
            count += 1
        return count

    # ── dashboard ─────────────────────────────────────────────────────────────
    @staticmethod
    def dashboard(workspace_id) -> dict:
        from django.db.models import Count, Sum
        by_status = dict(Installment.objects.filter(workspace_id=workspace_id)
                         .values_list("status").annotate(c=Count("id")))
        agg = Installment.objects.filter(workspace_id=workspace_id).aggregate(
            billed=Sum("amount"), fees=Sum("late_fee_amount"), paid=Sum("paid_amount"))
        billed = money(agg["billed"] or 0) + money(agg["fees"] or 0)
        paid = money(agg["paid"] or 0)
        return {
            "installments_by_status": by_status,
            "plans_active": InstallmentPlan.objects.filter(
                workspace_id=workspace_id, status=InstallmentPlan.ACTIVE).count(),
            "plans_completed": InstallmentPlan.objects.filter(
                workspace_id=workspace_id, status=InstallmentPlan.COMPLETED).count(),
            "total_billed": str(billed),
            "total_paid": str(paid),
            "total_outstanding": str(money(billed - paid)),
        }
