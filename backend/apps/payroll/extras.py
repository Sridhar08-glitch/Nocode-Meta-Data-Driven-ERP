"""
Payroll ancillary services (Phase P2.8) — loans, salary advances, overtime, adjustments,
retro/arrears, and final settlement (with country-adapter gratuity). These feed the run via
``PayrollService._extra_lines`` (recovery/overtime/adjustment payslip lines). Kept separate
from the run lifecycle for clarity; all reuse numbering/audit/GL where relevant.
"""
from __future__ import annotations

from decimal import Decimal

from .countries import get_adapter
from .formula import money
from .models import (
    EmployeeLoan,
    FinalSettlement,
    OvertimeRequest,
    PayrollAdjustment,
    SalaryAdvance,
)
from .services import PayrollError, _emit, _uid


class LoanService:
    @staticmethod
    def create_loan(*, workspace_id, employee_record_id, amount, installment,
                    reference="", actor_id=None) -> EmployeeLoan:
        amt = money(amount)
        loan = EmployeeLoan.objects.create(
            workspace_id=workspace_id, employee_record_id=employee_record_id,
            reference=reference, amount=amt, balance=amt, installment=money(installment),
            status="active", created_by=_uid(actor_id))
        _emit(loan, "payroll_loan", "payroll.loan.created",
              {"amount": str(amt), "installment": str(loan.installment)}, actor_id)
        return loan


class AdvanceService:
    @staticmethod
    def create_advance(*, workspace_id, employee_record_id, amount, installment,
                       reference="", actor_id=None) -> SalaryAdvance:
        amt = money(amount)
        adv = SalaryAdvance.objects.create(
            workspace_id=workspace_id, employee_record_id=employee_record_id,
            reference=reference, amount=amt, balance=amt, installment=money(installment),
            status="active", created_by=_uid(actor_id))
        _emit(adv, "payroll_advance", "payroll.advance.created",
              {"amount": str(amt), "installment": str(adv.installment)}, actor_id)
        return adv


class OvertimeService:
    @staticmethod
    def create(*, workspace_id, employee_record_id, hours, rate, multiplier=1,
               date=None, actor_id=None) -> OvertimeRequest:
        return OvertimeRequest.objects.create(
            workspace_id=workspace_id, employee_record_id=employee_record_id,
            hours=money(hours), rate=money(rate), multiplier=Decimal(str(multiplier)),
            date=date, status="submitted", created_by=_uid(actor_id))

    @staticmethod
    def approve(*, workspace_id, overtime_id, actor_id=None) -> OvertimeRequest:
        ot = OvertimeRequest.objects.filter(workspace_id=workspace_id, id=overtime_id).first()
        if ot is None:
            raise PayrollError("Overtime request not found.")
        ot.status = "approved"
        ot.save(update_fields=["status", "updated_at"])
        return ot


class AdjustmentService:
    @staticmethod
    def create(*, workspace_id, employee_record_id, adj_type, amount, name="", code="",
               reason="", period_id=None, actor_id=None) -> PayrollAdjustment:
        return PayrollAdjustment.objects.create(
            workspace_id=workspace_id, employee_record_id=employee_record_id,
            adj_type=adj_type, amount=money(amount), name=name, code=code, reason=reason,
            payroll_period_id=period_id, status="pending", created_by=_uid(actor_id))


class RetroService:
    @staticmethod
    def generate_retro(*, workspace_id, employee_record_id, amount, reason="Retro adjustment",
                       actor_id=None) -> PayrollAdjustment:
        """Backdated salary/contract change → an arrears adjustment applied in the next run."""
        return AdjustmentService.create(
            workspace_id=workspace_id, employee_record_id=employee_record_id,
            adj_type="correction", amount=amount, name="Arrears", code="retro_arrears",
            reason=reason, actor_id=actor_id)


class SettlementService:
    @staticmethod
    def compute_final_settlement(*, workspace_id, employee_record_id, salary=0,
                                 leave_encashment=0, bonus=0, benefits=0, penalties=0,
                                 service_years=0, last_basic=0, country="",
                                 actor_id=None) -> FinalSettlement:
        """Final settlement = salary + leave encashment + bonus + benefits + gratuity
        − outstanding loans − outstanding advances − penalties. Gratuity via the country adapter."""
        loans = money(sum((loan.balance for loan in EmployeeLoan.objects.filter(
            workspace_id=workspace_id, employee_record_id=employee_record_id, status="active")),
            Decimal("0.00")))
        advances = money(sum((adv.balance for adv in SalaryAdvance.objects.filter(
            workspace_id=workspace_id, employee_record_id=employee_record_id, status="active")),
            Decimal("0.00")))
        gratuity = get_adapter(country).gratuity(
            service_years=service_years, last_basic=last_basic, context={})
        net = money(money(salary) + money(leave_encashment) + money(bonus) + money(benefits)
                    + money(gratuity) - loans - advances - money(penalties))
        fs = FinalSettlement.objects.create(
            workspace_id=workspace_id, employee_record_id=employee_record_id,
            salary=money(salary), leave_encashment=money(leave_encashment), bonus=money(bonus),
            benefits=money(benefits), gratuity=money(gratuity), loans=loans, advances=advances,
            penalties=money(penalties), net=net, status="draft", created_by=_uid(actor_id))
        _emit(fs, "payroll_final_settlement", "payroll.final_settlement.created",
              {"net": str(net), "gratuity": str(money(gratuity))}, actor_id)
        return fs
