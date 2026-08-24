"""
Revenue Recognition services (Financial Platform — F5 / Gap G5).

``RevenueService`` is the single reusable entry point for deferred-revenue recognition. It REUSES the
platform engines and adds NO accounting of its own:
  * account codes → ``apps.ledger.provisioning.ensure_accounting_settings`` (no hardcoded codes)
  * gapless number → ``apps.numbering.NumberingService``
  * balanced post  → ``apps.ledger.GLBus`` (Dr Deferred Revenue, Cr Earned Revenue per period)
  * domain events  → ``apps.eventstore`` (via ``emit_event``)

``create_schedule`` is idempotent on ``external_ref``; ``recognize_due`` posts every unrecognised
period on/ before a date (idempotent per line); ``cancel`` reverses recognised periods (books stay
immutable). Straight-line, immediate and milestone methods.
"""
from __future__ import annotations

import datetime as _dt
import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from apps.ledger.provisioning import ensure_accounting_settings
from apps.solution_templates.documents import emit_event

from .models import RevenueSchedule, RevenueScheduleLine

CENTS = Decimal("0.01")


class RevenueError(Exception):  # noqa: N818 — domain error
    pass


def _m(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(CENTS, rounding=ROUND_HALF_UP)


def _uid(actor_id):
    return uuid.UUID(str(actor_id)) if actor_id else None


def _add_period(day, frequency, n):
    if frequency == "daily":
        return day + _dt.timedelta(days=n)
    if frequency == "weekly":
        return day + _dt.timedelta(weeks=n)
    # monthly (default): add n calendar months, clamping the day-of-month
    month = day.month - 1 + n
    year = day.year + month // 12
    month = month % 12 + 1
    import calendar
    last = calendar.monthrange(year, month)[1]
    return _dt.date(year, month, min(day.day, last))


class RevenueService:
    @staticmethod
    def create_schedule(*, workspace_id, total_amount, method="straight_line", num_periods=1,
                        start_date=None, frequency="monthly", source_module="", source_ref="",
                        external_ref="", partner_ref="", currency="", deferred_account=None,
                        revenue_account=None, milestone_amounts=None, actor_id=None) -> RevenueSchedule:
        """Create a recognition schedule + its period lines. Idempotent on ``external_ref``."""
        total = _m(total_amount)
        if total <= 0:
            raise RevenueError("Schedule total must be positive.")
        settings = ensure_accounting_settings(workspace_id, actor_id=actor_id)
        deferred = deferred_account or "2400"                     # Unearned Revenue
        revenue = revenue_account or settings.default_revenue_account
        start = start_date or timezone.now().date()

        if method == "immediate":
            amounts = [total]
        elif method == "milestone":
            amounts = [_m(a) for a in (milestone_amounts or []) if _m(a) > 0]
            if not amounts:
                raise RevenueError("Milestone method requires milestone_amounts.")
        else:  # straight_line
            n = max(1, int(num_periods or 1))
            per = _m(total / n)
            amounts = [per] * n
            amounts[-1] = _m(total - per * (n - 1))               # absorb rounding on the last period

        with transaction.atomic():
            if external_ref:
                existing = (RevenueSchedule.objects.select_for_update()
                            .filter(workspace_id=workspace_id, external_ref=external_ref)
                            .exclude(status=RevenueSchedule.CANCELLED).first())
                if existing is not None:
                    return existing
            from apps.numbering.services import NumberingService
            NumberingService.ensure_sequence(
                workspace_id, "revenue_schedule",
                defaults={"prefix": "REV-", "padding": 6}, created_by=actor_id)
            number = NumberingService.allocate(
                workspace_id, "revenue_schedule", actor_id=actor_id,
                context={"source_module": source_module, "source_ref": source_ref})
            sched = RevenueSchedule.objects.create(
                workspace_id=workspace_id, number=number, method=method, total_amount=total,
                recognized_amount=Decimal("0"), currency=currency, num_periods=len(amounts),
                start_date=start, frequency=frequency, source_module=str(source_module),
                source_ref=str(source_ref), external_ref=str(external_ref or ""),
                partner_ref=str(partner_ref or ""), deferred_account=deferred,
                revenue_account=revenue, status=RevenueSchedule.ACTIVE, created_by=_uid(actor_id))
            for i, amt in enumerate(amounts):
                RevenueScheduleLine.objects.create(
                    workspace_id=workspace_id, schedule=sched, period_no=i + 1,
                    period_date=_add_period(start, frequency, i), amount=amt)
        emit_event(workspace_id, "revenue_schedule", sched.id, "revenue.schedule.created",
                   {"number": number, "total": str(total), "periods": len(amounts)}, actor_id)
        return sched

    @staticmethod
    def recognize_due(*, workspace_id, schedule_id=None, as_of=None, actor_id=None) -> dict:
        """Recognise every unrecognised line with ``period_date <= as_of`` (all active schedules, or
        one). Posts Dr Deferred / Cr Revenue per line via GLBus. Idempotent per line."""
        as_of = as_of or timezone.now().date()
        lines = (RevenueScheduleLine.objects
                 .filter(workspace_id=workspace_id, recognized=False, period_date__lte=as_of,
                         schedule__status=RevenueSchedule.ACTIVE)
                 .select_related("schedule").order_by("schedule_id", "period_no"))
        if schedule_id:
            lines = lines.filter(schedule_id=schedule_id)
        recognized, total = 0, Decimal("0")
        for line in lines:
            if RevenueService._recognize_line(workspace_id, line, as_of, actor_id):
                recognized += 1
                total += line.amount
        return {"recognized_lines": recognized, "recognized_amount": str(_m(total))}

    @staticmethod
    def _recognize_line(workspace_id, line, day, actor_id) -> bool:
        from apps.ledger.services import GLBus, LedgerError, emit_post_failure
        with transaction.atomic():
            locked = (RevenueScheduleLine.objects.select_for_update()
                      .filter(workspace_id=workspace_id, id=line.id, recognized=False).first())
            if locked is None:
                return False
            sched = locked.schedule
            try:
                entry = GLBus.post(
                    workspace_id, date=day, lines=[
                        {"account_code": sched.deferred_account, "debit": str(locked.amount),
                         "memo": f"Rev rec {sched.number} p{locked.period_no}",
                         "partner_ref": sched.partner_ref},
                        {"account_code": sched.revenue_account, "credit": str(locked.amount),
                         "memo": f"Rev rec {sched.number} p{locked.period_no}",
                         "partner_ref": sched.partner_ref}],
                    memo=f"Revenue recognition {sched.number}", currency=sched.currency,
                    source_module="revenue", source_ref=f"{sched.number}:{locked.period_no}",
                    actor_id=actor_id)
            except LedgerError as exc:
                emit_post_failure(workspace_id, module="revenue", source_ref=sched.number,
                                  error=str(exc), actor_id=actor_id)
                raise
            locked.recognized = True
            locked.journal_entry_id = entry.id if entry is not None else None
            locked.recognized_at = timezone.now()
            locked.save(update_fields=["recognized", "journal_entry_id", "recognized_at",
                                       "updated_at"])
            sched.recognized_amount = _m(sched.recognized_amount + locked.amount)
            if not sched.lines.filter(recognized=False).exists():
                sched.status = RevenueSchedule.COMPLETED
            sched.save(update_fields=["recognized_amount", "status", "updated_at"])
        emit_event(workspace_id, "revenue_schedule", sched.id, "revenue.recognized",
                   {"number": sched.number, "period": locked.period_no,
                    "amount": str(locked.amount)}, actor_id)
        return True

    @staticmethod
    def cancel(*, workspace_id, schedule_id, reason="", actor_id=None) -> RevenueSchedule:
        """Cancel a schedule — reverse every recognised period's GL entry (books immutable) and stop
        future recognition. Idempotent."""
        from apps.ledger.services import GLBus, LedgerError, emit_post_failure
        with transaction.atomic():
            sched = (RevenueSchedule.objects.select_for_update()
                     .filter(workspace_id=workspace_id, id=schedule_id).first())
            if sched is None:
                raise RevenueError("Schedule not found.")
            if sched.status == RevenueSchedule.CANCELLED:
                return sched
            for line in sched.lines.filter(recognized=True, journal_entry_id__isnull=False):
                try:
                    GLBus.reverse(workspace_id, line.journal_entry_id,
                                  memo=reason or f"Cancel {sched.number}", actor_id=actor_id)
                except LedgerError as exc:
                    emit_post_failure(workspace_id, module="revenue", source_ref=sched.number,
                                      error=str(exc), actor_id=actor_id)
                    raise
            sched.status = RevenueSchedule.CANCELLED
            sched.recognized_amount = Decimal("0")
            sched.save(update_fields=["status", "recognized_amount", "updated_at"])
        emit_event(workspace_id, "revenue_schedule", sched.id, "revenue.schedule.cancelled",
                   {"number": sched.number}, actor_id)
        return sched
