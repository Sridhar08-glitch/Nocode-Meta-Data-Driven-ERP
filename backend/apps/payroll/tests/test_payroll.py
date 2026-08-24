"""
Payroll Engine (Phase P2.8) — formula engine (safe-eval reuse), calculator (gross/net/percent/
proration), the run lifecycle (calculate→approve→post→lock) with segregation of duties +
reconciliation + GL + immutable posted payslips, loan/overtime/adjustment integration, final
settlement with gratuity, and the framework template install.
"""
import datetime
import uuid
from decimal import Decimal

import pytest

from apps.eventstore.models import DomainEvent
from apps.payroll import calculator
from apps.payroll.blueprint import seed_payroll_template
from apps.payroll.countries import GulfGratuityAdapter
from apps.payroll.extras import AdjustmentService, LoanService, OvertimeService, SettlementService
from apps.payroll.formula import PayrollFormulaError, evaluate
from apps.payroll.models import (
    EmployeeLoan,
    PayrollPeriod,
    Payslip,
    PayslipLine,
    SalaryStructure,
    SalaryStructureAssignment,
    StructureComponent,
)
from apps.payroll.services import PayrollError, PayrollService
from apps.permissions.models import Role
from apps.solution_templates import services as st
from apps.studio.models import Application

A, B, C = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())


# ── formula engine (reuses apps.computed safe_eval) ──────────────────────────
def test_formula_evaluates_and_rejects_unsafe():
    assert evaluate("basic * 0.25", {"basic": Decimal("1000")}) == Decimal("250.00")
    assert evaluate("gross - ded", {"gross": 1250, "ded": 125}) == Decimal("1125.00")
    with pytest.raises(PayrollFormulaError):
        evaluate("__import__('os').system('x')", {})


# ── calculator ────────────────────────────────────────────────────────────────
def _components():
    return [
        {"code": "basic", "name": "Basic", "component_type": "earning",
         "calc_type": "formula", "formula": "base_salary", "sequence": 10},
        {"code": "housing", "name": "Housing", "component_type": "earning",
         "calc_type": "percent", "base_code": "basic", "amount": Decimal("25"), "sequence": 20},
        {"code": "tax", "name": "Tax", "component_type": "deduction",
         "calc_type": "formula", "formula": "gross * 0.1", "sequence": 30},
    ]


def test_calculator_gross_net():
    r = calculator.calculate(components=_components(), base_salary=Decimal("1000"))
    assert r["gross_pay"] == Decimal("1250.00")       # basic 1000 + housing 250
    assert r["total_deductions"] == Decimal("125.00")  # tax 10% of gross
    assert r["net_pay"] == Decimal("1125.00")


def test_calculator_proration_halves_earnings():
    r = calculator.calculate(components=_components(), base_salary=Decimal("1000"),
                             proration=Decimal("0.5"))
    assert r["gross_pay"] == Decimal("625.00")  # earnings prorated


def test_proration_factor_mid_month_join():
    f = calculator.proration_factor(
        period_start=datetime.date(2026, 6, 1), period_end=datetime.date(2026, 6, 30),
        worked_start=datetime.date(2026, 6, 16))
    assert f == Decimal("0.500000")  # 15 of 30 days


# ── run lifecycle helpers ─────────────────────────────────────────────────────
def _structure(ws, *, with_loan_for=None):
    struct = SalaryStructure.objects.create(workspace_id=ws, name="Standard")
    for c in _components():
        StructureComponent.objects.create(
            workspace_id=ws, salary_structure_id=struct.id, code=c["code"], name=c["name"],
            component_type=c["component_type"], calc_type=c["calc_type"],
            amount=c.get("amount", 0), formula=c.get("formula", ""),
            base_code=c.get("base_code", ""), sequence=c["sequence"])
    emp = uuid.uuid4()
    SalaryStructureAssignment.objects.create(
        workspace_id=ws, employee_record_id=emp, salary_structure_id=struct.id,
        effective_date=datetime.date(2026, 6, 1), base_salary=Decimal("1000"), is_current=True)
    return struct, emp


def _period(ws):
    # Provision the chart so payroll posting produces a real (visible) journal entry.
    from apps.ledger.provisioning import provision_accounting
    provision_accounting(ws)
    p = PayrollPeriod.objects.create(
        workspace_id=ws, name="June 2026", start_date=datetime.date(2026, 6, 1),
        end_date=datetime.date(2026, 6, 30))
    PayrollService.open_period(workspace_id=ws, period_id=p.id, actor_id=A)
    return p


@pytest.mark.django_db
def test_full_run_lifecycle_with_sod():
    ws = uuid.uuid4()
    _structure(ws)
    period = _period(ws)
    run = PayrollService.create_run(workspace_id=ws, period_id=period.id, actor_id=A)
    run = PayrollService.calculate_run(workspace_id=ws, run_id=run.id, actor_id=A)
    assert run.status == "completed" and run.employee_count == 1
    slip = Payslip.objects.get(workspace_id=ws, payroll_run_id=run.id)
    assert slip.number == "PS-000001"
    assert slip.net_pay == Decimal("1125.00")
    assert PayslipLine.objects.filter(workspace_id=ws, payslip_id=slip.id).count() == 3

    # SoD: creator cannot approve.
    with pytest.raises(PayrollError):
        PayrollService.approve_run(workspace_id=ws, run_id=run.id, actor_id=A)
    PayrollService.approve_run(workspace_id=ws, run_id=run.id, actor_id=B)
    # SoD: approver cannot post.
    with pytest.raises(PayrollError):
        PayrollService.post_run(workspace_id=ws, run_id=run.id, actor_id=B)
    run = PayrollService.post_run(workspace_id=ws, run_id=run.id, actor_id=C)
    assert run.status == "posted"
    assert Payslip.objects.get(workspace_id=ws, id=slip.id).status == "posted"
    assert DomainEvent.objects.filter(event_type="payroll.run.posted").exists()
    # Payroll → Accounting: a balanced journal entry was posted (chart provisioned in _period).
    from apps.ledger.models import JournalEntry
    je = JournalEntry.objects.filter(workspace_id=ws, source_module="payroll")
    assert je.count() == 1
    posted_je = je.first()
    assert posted_je.status == "posted"
    assert sum(line.debit for line in posted_je.lines.all()) == \
        sum(line.credit for line in posted_je.lines.all())
    assert DomainEvent.objects.filter(event_type="payroll.payslip.generated").exists()

    run = PayrollService.lock_run(workspace_id=ws, run_id=run.id, actor_id=C)
    assert run.status == "locked"
    assert PayrollPeriod.objects.get(workspace_id=ws, id=period.id).status == "locked"


@pytest.mark.django_db
def test_loan_recovery_in_run_and_balance_decrement():
    ws = uuid.uuid4()
    _, emp = _structure(ws)
    loan = LoanService.create_loan(
        workspace_id=ws, employee_record_id=emp, amount=500, installment=100, actor_id=A)
    period = _period(ws)
    run = PayrollService.create_run(workspace_id=ws, period_id=period.id, actor_id=A)
    PayrollService.calculate_run(workspace_id=ws, run_id=run.id, actor_id=A)
    slip = Payslip.objects.get(workspace_id=ws, payroll_run_id=run.id)
    # net = gross 1250 - tax 125 - loan 100 = 1025
    assert slip.net_pay == Decimal("1025.00")
    assert PayslipLine.objects.filter(
        workspace_id=ws, payslip_id=slip.id, source="loan").exists()

    PayrollService.approve_run(workspace_id=ws, run_id=run.id, actor_id=B)
    PayrollService.post_run(workspace_id=ws, run_id=run.id, actor_id=C)
    assert EmployeeLoan.objects.get(id=loan.id).balance == Decimal("400.00")


@pytest.mark.django_db
def test_overtime_and_adjustment_lines():
    ws = uuid.uuid4()
    _, emp = _structure(ws)
    ot = OvertimeService.create(workspace_id=ws, employee_record_id=emp, hours=10, rate=5,
                                multiplier=2, actor_id=A)        # 10*5*2 = 100
    OvertimeService.approve(workspace_id=ws, overtime_id=ot.id, actor_id=B)
    AdjustmentService.create(workspace_id=ws, employee_record_id=emp, adj_type="bonus",
                             amount=200, name="Spot bonus", actor_id=A)
    period = _period(ws)
    run = PayrollService.create_run(workspace_id=ws, period_id=period.id, actor_id=A)
    PayrollService.calculate_run(workspace_id=ws, run_id=run.id, actor_id=A)
    slip = Payslip.objects.get(workspace_id=ws, payroll_run_id=run.id)
    # gross = 1250 + OT 100 + bonus 200 = 1550; tax is 10% of base earnings gross (1250) = 125
    assert slip.gross_pay == Decimal("1550.00")
    assert PayslipLine.objects.filter(workspace_id=ws, payslip_id=slip.id, source="overtime").exists()


@pytest.mark.django_db
def test_posted_run_cannot_be_recalculated():
    ws = uuid.uuid4()
    _structure(ws)
    period = _period(ws)
    run = PayrollService.create_run(workspace_id=ws, period_id=period.id, actor_id=A)
    PayrollService.calculate_run(workspace_id=ws, run_id=run.id, actor_id=A)
    PayrollService.approve_run(workspace_id=ws, run_id=run.id, actor_id=B)
    PayrollService.post_run(workspace_id=ws, run_id=run.id, actor_id=C)
    with pytest.raises(PayrollError):
        PayrollService.calculate_run(workspace_id=ws, run_id=run.id, actor_id=A)


# ── final settlement + gratuity (country adapter) ────────────────────────────
def test_gulf_gratuity_adapter():
    # 6 years service, basic 3000 → 5y*21 + 1y*30 days of (3000/30)=100/day
    g = GulfGratuityAdapter().gratuity(service_years=6, last_basic=Decimal("3000"), context={})
    assert g == Decimal("13500.00")  # (5*21 + 1*30) * 100


@pytest.mark.django_db
def test_final_settlement_nets_loans_and_gratuity():
    ws = uuid.uuid4()
    emp = uuid.uuid4()
    LoanService.create_loan(workspace_id=ws, employee_record_id=emp, amount=500,
                            installment=100, actor_id=A)
    fs = SettlementService.compute_final_settlement(
        workspace_id=ws, employee_record_id=emp, salary=2000, leave_encashment=1000,
        bonus=500, benefits=0, penalties=100, actor_id=A)
    # 2000 + 1000 + 500 + 0 + gratuity(0, no country) - loans 500 - advances 0 - penalties 100
    assert fs.loans == Decimal("500.00")
    assert fs.net == Decimal("2900.00")
    assert DomainEvent.objects.filter(event_type="payroll.final_settlement.created").exists()


# ── framework template install ────────────────────────────────────────────────
@pytest.mark.django_db
def test_install_provisions_roles_and_app():
    ws = uuid.uuid4()
    tpl = seed_payroll_template()
    assert tpl.slug == "payroll" and tpl.is_published
    st.install(template_id=tpl.id, workspace_id=ws, installed_by=None)
    assert Role.objects.filter(workspace_id=ws, slug="payroll_administrator").exists()
    assert Role.objects.filter(workspace_id=ws, slug="payroll_finance_manager").exists()
    assert Application.objects.filter(workspace_id=ws, slug="payroll").exists()


@pytest.mark.django_db
def test_period_must_be_open_for_run():
    ws = uuid.uuid4()
    p = PayrollPeriod.objects.create(
        workspace_id=ws, name="Draft", start_date=datetime.date(2026, 6, 1),
        end_date=datetime.date(2026, 6, 30))  # status draft
    with pytest.raises(PayrollError):
        PayrollService.create_run(workspace_id=ws, period_id=p.id, actor_id=A)
