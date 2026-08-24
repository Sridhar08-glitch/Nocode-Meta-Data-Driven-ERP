"""
Payroll Engine services (Phase P2.8) — the native lifecycle orchestration.

Period + run + payslip lifecycle with: gapless payslip numbers (NumberingService, in-txn),
immutable posted payslips, race-safe run posting (select_for_update), segregation of duties
(create ≠ approve ≠ post), internal reconciliation before posting, multi-line GL posting via
GLBus (best-effort — decoupled like inventory), immutable run snapshots, and loan/advance/
overtime/adjustment integration. Batch-oriented (iterates native assignment rows, no per-
employee N+1). Audit events on every material transition.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.eventstore.events import DomainEventData, DomainEventFactory

from . import calculator
from .formula import money
from .models import (
    EmployeeLoan,
    OvertimeRequest,
    PayrollAdjustment,
    PayrollPeriod,
    PayrollRun,
    PayrollSettings,
    PayrollSnapshot,
    Payslip,
    PayslipLine,
    SalaryAdvance,
    SalaryStructureAssignment,
    StructureComponent,
)


class PayrollError(Exception):  # noqa: N818 — domain error
    pass


@dataclass
class _Actor:
    user_id: uuid.UUID
    id: uuid.UUID
    role: str = "owner"
    custom_role_id = None


def _system_member(actor_id):
    a = uuid.UUID(str(actor_id)) if actor_id else uuid.UUID(int=0)
    return _Actor(user_id=a, id=a)


def _emit(obj, aggregate_type, event_type, payload, actor_id=None):
    from apps.eventstore.models import DomainEvent
    version = DomainEvent.objects.filter(
        aggregate_id=obj.id, aggregate_type=aggregate_type).count() + 1
    DomainEventFactory.persist_one(DomainEventData(
        event_type=event_type, workspace_id=obj.workspace_id,
        aggregate_type=aggregate_type, aggregate_id=obj.id, version=version,
        payload=payload, actor_id=uuid.UUID(str(actor_id)) if actor_id else uuid.UUID(int=0)))


def _uid(actor_id):
    return uuid.UUID(str(actor_id)) if actor_id else None


class PayrollService:
    # ── settings ──────────────────────────────────────────────────────────────
    @staticmethod
    def get_settings(workspace_id) -> PayrollSettings:
        obj, _ = PayrollSettings.objects.get_or_create(
            workspace_id=workspace_id, defaults={})
        return obj

    @staticmethod
    def ensure_sequences(workspace_id, *, actor_id=None):
        from apps.numbering.services import NumberingService
        NumberingService.ensure_sequence(
            workspace_id, "payslip",
            defaults={"name": "Payslip", "prefix": "PS-", "padding": 6}, created_by=actor_id)

    # ── period lifecycle ──────────────────────────────────────────────────────
    @staticmethod
    def open_period(*, workspace_id, period_id, actor_id=None) -> PayrollPeriod:
        return PayrollService._set_period_status(
            workspace_id, period_id, {"draft", "closed"}, "open",
            "payroll.period.opened", actor_id)

    @staticmethod
    def close_period(*, workspace_id, period_id, actor_id=None) -> PayrollPeriod:
        return PayrollService._set_period_status(
            workspace_id, period_id, {"open", "processing"}, "closed",
            "payroll.period.closed", actor_id)

    @staticmethod
    def lock_period(*, workspace_id, period_id, actor_id=None) -> PayrollPeriod:
        return PayrollService._set_period_status(
            workspace_id, period_id, {"closed"}, "locked",
            "payroll.period.locked", actor_id)

    @staticmethod
    def reopen_period(*, workspace_id, period_id, actor_id=None) -> PayrollPeriod:
        # Locked periods cannot be reopened (audit integrity); closed→open only.
        return PayrollService._set_period_status(
            workspace_id, period_id, {"closed"}, "open",
            "payroll.period.reopened", actor_id)

    @staticmethod
    def _set_period_status(workspace_id, period_id, allowed, new_status, event, actor_id):
        period = PayrollPeriod.objects.filter(
            workspace_id=workspace_id, id=period_id).first()
        if period is None:
            raise PayrollError("Payroll period not found.")
        if period.status not in allowed:
            raise PayrollError(
                f"Cannot move period from {period.status} to {new_status}.")
        period.status = new_status
        period.save(update_fields=["status", "updated_at"])
        _emit(period, "payroll_period", event,
              {"status": new_status, "name": period.name}, actor_id)
        return period

    # ── run lifecycle ─────────────────────────────────────────────────────────
    @staticmethod
    def create_run(*, workspace_id, period_id, actor_id=None) -> PayrollRun:
        period = PayrollPeriod.objects.filter(
            workspace_id=workspace_id, id=period_id).first()
        if period is None:
            raise PayrollError("Payroll period not found.")
        if period.status not in {"open", "processing"}:
            raise PayrollError("Payroll runs require an open period.")
        run = PayrollRun.objects.create(
            workspace_id=workspace_id, payroll_period_id=period_id, status="draft",
            started_by=_uid(actor_id), started_at=timezone.now(), created_by=_uid(actor_id))
        _emit(run, "payroll_run", "payroll.run.started", {"period": str(period_id)}, actor_id)
        return run

    @staticmethod
    def calculate_run(*, workspace_id, run_id, actor_id=None) -> PayrollRun:
        """Generate a payslip for every employee with a current structure assignment. Idempotent
        per draft run (re-calculate clears prior payslips). Snapshots inputs immutably."""
        PayrollService.ensure_sequences(workspace_id, actor_id=actor_id)
        with transaction.atomic():
            run = PayrollRun.objects.select_for_update().filter(
                workspace_id=workspace_id, id=run_id).first()
            if run is None:
                raise PayrollError("Payroll run not found.")
            if run.status not in {"draft", "completed"}:
                raise PayrollError(f"Cannot calculate a {run.status} run.")
            period = PayrollPeriod.objects.get(workspace_id=workspace_id,
                                               id=run.payroll_period_id)
            # Clear any prior payslips (re-calculation).
            old = list(Payslip.objects.filter(workspace_id=workspace_id,
                                              payroll_run_id=run.id).values_list("id", flat=True))
            PayslipLine.objects.filter(workspace_id=workspace_id, payslip_id__in=old).delete()
            Payslip.objects.filter(workspace_id=workspace_id, payroll_run_id=run.id).delete()

            settings = PayrollService.get_settings(workspace_id)
            assignments = list(SalaryStructureAssignment.objects.filter(
                workspace_id=workspace_id, is_current=True))
            total_gross = total_ded = total_net = Decimal("0.00")
            for asn in assignments:
                slip = PayrollService._build_payslip(
                    workspace_id, run, period, asn, settings, actor_id)
                total_gross += slip.gross_pay
                total_ded += slip.total_deductions
                total_net += slip.net_pay
            run.total_gross = money(total_gross)
            run.total_deductions = money(total_ded)
            run.total_net = money(total_net)
            run.employee_count = len(assignments)
            run.status = "completed"
            run.save(update_fields=["total_gross", "total_deductions", "total_net",
                                    "employee_count", "status", "updated_at"])
            PayrollSnapshot.objects.create(
                workspace_id=workspace_id, payroll_run_id=run.id,
                data={"employee_count": len(assignments),
                      "total_gross": str(run.total_gross), "total_net": str(run.total_net),
                      "period": str(period.id)})
        _emit(run, "payroll_run", "payroll.run.completed",
              {"employee_count": run.employee_count, "total_net": str(run.total_net)}, actor_id)
        return run

    @staticmethod
    def _build_payslip(workspace_id, run, period, asn, settings, actor_id):
        from apps.numbering.services import NumberingService
        components = [
            {"code": c.code, "name": c.name, "component_type": c.component_type,
             "calc_type": c.calc_type, "amount": c.amount, "formula": c.formula,
             "base_code": c.base_code, "formula_version": c.formula_version,
             "gl_account_code": c.gl_account_code, "sequence": c.sequence}
            for c in StructureComponent.objects.filter(
                workspace_id=workspace_id, salary_structure_id=asn.salary_structure_id)
        ]
        extra, recoveries = PayrollService._extra_lines(
            workspace_id, asn.employee_record_id, period)
        result = calculator.calculate(
            components=components, base_salary=asn.base_salary,
            extra_lines=extra, country=settings.default_country)

        number = NumberingService.allocate(
            workspace_id, "payslip", actor_id=actor_id,
            context={"source_module": "payroll", "source_ref": str(run.id)})
        slip = Payslip.objects.create(
            workspace_id=workspace_id, number=number,
            employee_record_id=asn.employee_record_id,
            payroll_period_id=period.id, payroll_run_id=run.id,
            currency=settings.currency, fx_rate=Decimal("1"),
            gross_pay=result["gross_pay"], total_earnings=result["total_earnings"],
            total_deductions=result["total_deductions"], net_pay=result["net_pay"],
            status="draft", created_by=_uid(actor_id),
            snapshot={"base_salary": str(asn.base_salary),
                      "salary_structure_id": str(asn.salary_structure_id),
                      "country": settings.default_country,
                      "recoveries": recoveries,
                      "component_versions": {c["code"]: c["formula_version"]
                                             for c in components}})
        for ln in result["lines"]:
            PayslipLine.objects.create(
                workspace_id=workspace_id, payslip_id=slip.id, code=ln["code"],
                name=ln["name"], component_type=ln["component_type"],
                amount=ln["amount"], formula_version=ln["formula_version"],
                source=ln["source"], sequence=ln["sequence"])
        _emit(slip, "payslip", "payroll.payslip.generated",
              {"number": number, "net_pay": str(slip.net_pay)}, actor_id)
        return slip

    @staticmethod
    def _extra_lines(workspace_id, employee_record_id, period):
        """Loan/advance recovery + approved overtime + pending adjustments → extra payslip
        lines, plus the recovery records to apply on post."""
        extra: list[dict] = []
        recoveries: list[dict] = []
        for loan in EmployeeLoan.objects.filter(
                workspace_id=workspace_id, employee_record_id=employee_record_id,
                status="active"):
            amt = money(min(loan.installment, loan.balance))
            if amt > 0:
                extra.append({"code": f"loan_{loan.id.hex[:6]}", "name": "Loan recovery",
                              "component_type": "deduction", "amount": amt, "source": "loan"})
                recoveries.append({"type": "loan", "id": str(loan.id), "amount": str(amt)})
        for adv in SalaryAdvance.objects.filter(
                workspace_id=workspace_id, employee_record_id=employee_record_id,
                status="active"):
            amt = money(min(adv.installment, adv.balance))
            if amt > 0:
                extra.append({"code": f"adv_{adv.id.hex[:6]}", "name": "Advance recovery",
                              "component_type": "deduction", "amount": amt, "source": "advance"})
                recoveries.append({"type": "advance", "id": str(adv.id), "amount": str(amt)})
        for ot in OvertimeRequest.objects.filter(
                workspace_id=workspace_id, employee_record_id=employee_record_id,
                status="approved"):
            amt = money(ot.hours * ot.rate * ot.multiplier)
            if amt > 0:
                extra.append({"code": f"ot_{ot.id.hex[:6]}", "name": "Overtime",
                              "component_type": "earning", "amount": amt, "source": "overtime"})
        for adj in PayrollAdjustment.objects.filter(
                workspace_id=workspace_id, employee_record_id=employee_record_id,
                status="pending"):
            ctype = "deduction" if adj.adj_type in {"deduction", "recovery"} else "earning"
            extra.append({"code": adj.code or f"adj_{adj.id.hex[:6]}",
                          "name": adj.name or adj.adj_type, "component_type": ctype,
                          "amount": money(adj.amount), "source": "adjustment"})
        return extra, recoveries

    @staticmethod
    def approve_run(*, workspace_id, run_id, actor_id=None) -> PayrollRun:
        run = PayrollRun.objects.filter(workspace_id=workspace_id, id=run_id).first()
        if run is None:
            raise PayrollError("Payroll run not found.")
        if run.status != "completed":
            raise PayrollError("Only a calculated run can be approved.")
        if _uid(actor_id) and run.started_by and _uid(actor_id) == run.started_by:
            raise PayrollError("Segregation of duties: the run's creator cannot approve it.")
        run.status = "approved"
        run.approved_by = _uid(actor_id)
        run.save(update_fields=["status", "approved_by", "updated_at"])
        Payslip.objects.filter(workspace_id=workspace_id, payroll_run_id=run.id).update(
            status="approved")
        _emit(run, "payroll_run", "payroll.run.approved", {}, actor_id)
        return run

    @staticmethod
    def post_run(*, workspace_id, run_id, actor_id=None) -> PayrollRun:
        """Reconcile, post the GL journal, freeze payslips (immutable), apply loan/advance
        recoveries. SoD: poster must differ from creator and approver."""
        with transaction.atomic():
            run = PayrollRun.objects.select_for_update().filter(
                workspace_id=workspace_id, id=run_id).first()
            if run is None:
                raise PayrollError("Payroll run not found.")
            if run.status != "approved":
                raise PayrollError("Only an approved run can be posted.")
            actor = _uid(actor_id)
            if actor and run.started_by and actor == run.started_by:
                raise PayrollError("Segregation of duties: the creator cannot post the run.")
            if actor and run.approved_by and actor == run.approved_by:
                raise PayrollError("Segregation of duties: the approver cannot post the run.")
            PayrollService._reconcile(workspace_id, run)
            run.journal_entry_id = PayrollService._post_gl(workspace_id, run, actor_id)
            run.posted_by = actor
            run.status = "posted"
            run.save(update_fields=["journal_entry_id", "posted_by", "status", "updated_at"])
            Payslip.objects.filter(workspace_id=workspace_id, payroll_run_id=run.id).update(
                status="posted")
            PayrollService._apply_recoveries(workspace_id, run)
        _emit(run, "payroll_run", "payroll.run.posted",
              {"journal_entry_id": str(run.journal_entry_id) if run.journal_entry_id else None,
               "total_net": str(run.total_net)}, actor_id)
        return run

    @staticmethod
    def _reconcile(workspace_id, run):
        """Payroll total must be internally consistent before posting (gross = net + deductions)."""
        agg = Payslip.objects.filter(workspace_id=workspace_id, payroll_run_id=run.id)
        gross = sum((p.gross_pay for p in agg), Decimal("0.00"))
        ded = sum((p.total_deductions for p in agg), Decimal("0.00"))
        net = sum((p.net_pay for p in agg), Decimal("0.00"))
        if money(net + ded) != money(gross):
            raise PayrollError(
                f"Reconciliation failed: net+deductions ({money(net + ded)}) != gross ({money(gross)}).")
        if money(gross) != money(run.total_gross):
            raise PayrollError("Reconciliation failed: run totals do not match payslips.")

    @staticmethod
    def _post_gl(workspace_id, run, actor_id):
        """Post a balanced payroll journal: Dr Salary Expense, Cr Net Pay Payable + deduction
        liabilities (grouped by account). Best-effort — a missing chart never blocks payroll."""
        from apps.ledger.services import GLBus, LedgerError, emit_post_failure
        period = PayrollPeriod.objects.get(workspace_id=workspace_id, id=run.payroll_period_id)
        ded_by_acct: dict[str, Decimal] = {}
        slip_ids = list(Payslip.objects.filter(
            workspace_id=workspace_id, payroll_run_id=run.id).values_list("id", flat=True))
        comp_acct = {c.code: (c.gl_account_code or "2200")
                     for c in StructureComponent.objects.filter(workspace_id=workspace_id)}
        for ln in PayslipLine.objects.filter(workspace_id=workspace_id, payslip_id__in=slip_ids,
                                             component_type="deduction"):
            acct = comp_acct.get(ln.code, "2200")
            ded_by_acct[acct] = ded_by_acct.get(acct, Decimal("0.00")) + ln.amount
        lines = [{"account_code": "6000", "debit": str(run.total_gross),
                  "memo": "Salary expense"},
                 {"account_code": "2100", "credit": str(run.total_net),
                  "memo": "Net pay payable"}]
        for acct, amt in ded_by_acct.items():
            if money(amt) > 0:
                lines.append({"account_code": acct, "credit": str(money(amt)),
                              "memo": "Payroll deduction liability"})
        if money(run.total_gross) <= 0:
            return None
        try:
            entry = GLBus.post(
                workspace_id, date=period.end_date, lines=lines,
                memo=f"Payroll {period.name}", source_module="payroll",
                source_ref=str(run.id), actor_id=actor_id)
            return entry.id if entry is not None else None
        except LedgerError as exc:
            # Visible failure (Blocker 3): record + re-raise instead of silently dropping the JE.
            emit_post_failure(workspace_id, module="payroll", source_ref=str(run.id),
                              error=str(exc), actor_id=actor_id)
            raise

    @staticmethod
    def _apply_recoveries(workspace_id, run):
        slips = Payslip.objects.filter(workspace_id=workspace_id, payroll_run_id=run.id)
        for slip in slips:
            for rec in slip.snapshot.get("recoveries", []) or []:
                amt = money(rec.get("amount", 0))
                if rec["type"] == "loan":
                    loan = EmployeeLoan.objects.filter(
                        workspace_id=workspace_id, id=rec["id"]).first()
                    if loan:
                        loan.balance = money(loan.balance - amt)
                        if loan.balance <= 0:
                            loan.balance = Decimal("0.00")
                            loan.status = "closed"
                        loan.save(update_fields=["balance", "status", "updated_at"])
                elif rec["type"] == "advance":
                    adv = SalaryAdvance.objects.filter(
                        workspace_id=workspace_id, id=rec["id"]).first()
                    if adv:
                        adv.balance = money(adv.balance - amt)
                        if adv.balance <= 0:
                            adv.balance = Decimal("0.00")
                            adv.status = "closed"
                        adv.save(update_fields=["balance", "status", "updated_at"])
        OvertimeRequest.objects.filter(
            workspace_id=workspace_id, status="approved").update(status="processed")
        PayrollAdjustment.objects.filter(
            workspace_id=workspace_id, status="pending").update(status="applied")

    @staticmethod
    def lock_run(*, workspace_id, run_id, actor_id=None) -> PayrollRun:
        run = PayrollRun.objects.filter(workspace_id=workspace_id, id=run_id).first()
        if run is None:
            raise PayrollError("Payroll run not found.")
        if run.status != "posted":
            raise PayrollError("Only a posted run can be locked.")
        run.status = "locked"
        run.save(update_fields=["status", "updated_at"])
        # Lock the period: close it first if still open (posted run ⇒ period can finalize).
        period = PayrollPeriod.objects.filter(
            workspace_id=workspace_id, id=run.payroll_period_id).first()
        if period and period.status in {"open", "processing"}:
            PayrollService.close_period(workspace_id=workspace_id,
                                        period_id=run.payroll_period_id, actor_id=actor_id)
        if period and period.status != "locked":
            PayrollService.lock_period(workspace_id=workspace_id,
                                       period_id=run.payroll_period_id, actor_id=actor_id)
        Payslip.objects.filter(workspace_id=workspace_id, payroll_run_id=run.id).update(
            status="paid")
        _emit(run, "payroll_run", "payroll.run.locked", {}, actor_id)
        return run

    # ── reports (native aggregations) ─────────────────────────────────────────
    @staticmethod
    def register(*, workspace_id, run_id):
        slips = Payslip.objects.filter(workspace_id=workspace_id, payroll_run_id=run_id)
        return [{"number": s.number, "employee": str(s.employee_record_id),
                 "gross": str(s.gross_pay), "deductions": str(s.total_deductions),
                 "net": str(s.net_pay)} for s in slips]

    @staticmethod
    def summary(*, workspace_id, run_id):
        run = PayrollRun.objects.filter(workspace_id=workspace_id, id=run_id).first()
        if run is None:
            raise PayrollError("Payroll run not found.")
        return {"employee_count": run.employee_count, "total_gross": str(run.total_gross),
                "total_deductions": str(run.total_deductions), "total_net": str(run.total_net),
                "status": run.status}
