"""
Payroll Engine models (Phase P2.8) — a native ERP core engine.

Payroll calculation, periods, runs, payslips, snapshots, loans/advances/overtime, retro and
final settlement are NATIVE (double-entry GL posting, gapless payslip numbers, period locks,
immutable posted payslips, race-safe runs — none of which can be metadata). The HR Employee
stays a framework metadata entity; payroll references it by record-id UUID (no FK, no HR
redesign). Every model is workspace-scoped (TenantModel) with PostgreSQL RLS (migration 0002).
"""
from django.db import models

from apps.core.models import TenantModel

MONEY = {"max_digits": 16, "decimal_places": 2, "default": 0}
RATE = {"max_digits": 16, "decimal_places": 6, "default": 0}

# Status vocabularies
PERIOD_STATUS = ["draft", "open", "processing", "closed", "locked"]
RUN_STATUS = ["draft", "processing", "completed", "approved", "posted", "cancelled", "locked"]
PAYSLIP_STATUS = ["draft", "approved", "posted", "paid"]
COMPONENT_TYPES = ["earning", "deduction", "benefit"]


def _choices(values):
    return [(v, v.replace("_", " ").title()) for v in values]


class PayrollSettings(TenantModel):
    """One per workspace — company-wide payroll configuration."""
    frequency = models.CharField(max_length=20, default="monthly")  # monthly|weekly|biweekly|semi_monthly
    currency = models.CharField(max_length=8, default="")
    default_country = models.CharField(max_length=8, default="")
    default_cost_center = models.CharField(max_length=64, blank=True)
    pay_start_day = models.IntegerField(default=1)
    pay_end_day = models.IntegerField(default=31)

    class Meta:
        db_table = "payroll_settings"
        indexes = [models.Index(fields=["workspace_id"])]


class PayrollCalendar(TenantModel):
    name = models.CharField(max_length=150)
    frequency = models.CharField(max_length=20, default="monthly")
    processing_date = models.DateField(null=True, blank=True)
    approval_date = models.DateField(null=True, blank=True)
    payment_date = models.DateField(null=True, blank=True)
    cutoff_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "payroll_calendars"
        indexes = [models.Index(fields=["workspace_id", "is_active"])]


class SalaryStructure(TenantModel):
    name = models.CharField(max_length=150)
    currency = models.CharField(max_length=8, default="")
    country = models.CharField(max_length=8, default="")
    effective_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, default="active")  # active|archived

    class Meta:
        db_table = "payroll_salary_structures"
        indexes = [models.Index(fields=["workspace_id", "status"])]


class StructureComponent(TenantModel):
    """A pay component within a salary structure (earning/deduction/benefit)."""
    salary_structure_id = models.UUIDField(db_index=True)
    code = models.CharField(max_length=64)
    name = models.CharField(max_length=150)
    component_type = models.CharField(max_length=20, choices=_choices(COMPONENT_TYPES))
    calc_type = models.CharField(max_length=20, default="fixed")  # fixed|formula|percent
    amount = models.DecimalField(**MONEY)
    formula = models.TextField(blank=True)            # safe formula, e.g. "basic * 0.25"
    formula_version = models.IntegerField(default=1)
    base_code = models.CharField(max_length=64, blank=True)  # for percent: base component code
    taxable = models.BooleanField(default=True)
    gl_account_code = models.CharField(max_length=32, blank=True)
    sequence = models.IntegerField(default=100)

    class Meta:
        db_table = "payroll_structure_components"
        indexes = [models.Index(fields=["workspace_id", "salary_structure_id", "sequence"])]


class SalaryStructureAssignment(TenantModel):
    """Effective-dated assignment of a structure to an employee — full history, never overwritten."""
    employee_record_id = models.UUIDField(db_index=True)
    salary_structure_id = models.UUIDField(db_index=True)
    effective_date = models.DateField()
    base_salary = models.DecimalField(**MONEY)
    is_current = models.BooleanField(default=True)

    class Meta:
        db_table = "payroll_structure_assignments"
        indexes = [models.Index(fields=["workspace_id", "employee_record_id", "-effective_date"])]


class EmployeePayrollProfile(TenantModel):
    """Payroll-specific data attached to an HR Employee (referenced by record-id; no HR redesign)."""
    employee_record_id = models.UUIDField(db_index=True)
    payroll_status = models.CharField(max_length=20, default="active")  # active|inactive|hold
    bank_account = models.CharField(max_length=64, blank=True)
    bank_name = models.CharField(max_length=150, blank=True)
    iban = models.CharField(max_length=64, blank=True)
    payment_method = models.CharField(max_length=20, default="bank")  # bank|cash|cheque
    cost_center = models.CharField(max_length=64, blank=True)
    currency = models.CharField(max_length=8, default="")
    payroll_calendar_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "payroll_employee_profiles"
        unique_together = [("workspace_id", "employee_record_id")]


class EmploymentContract(TenantModel):
    employee_record_id = models.UUIDField(db_index=True)
    contract_number = models.CharField(max_length=64, blank=True)
    contract_type = models.CharField(max_length=20, default="permanent")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, default="active")  # active|expired|terminated

    class Meta:
        db_table = "payroll_contracts"
        indexes = [models.Index(fields=["workspace_id", "employee_record_id", "status"])]


class PayrollPeriod(TenantModel):
    name = models.CharField(max_length=150)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, default="draft", choices=_choices(PERIOD_STATUS))
    payroll_calendar_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "payroll_periods"
        indexes = [models.Index(fields=["workspace_id", "status", "start_date"])]


class PayrollRun(TenantModel):
    payroll_period_id = models.UUIDField(db_index=True)
    status = models.CharField(max_length=20, default="draft", choices=_choices(RUN_STATUS))
    started_by = models.UUIDField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.UUIDField(null=True, blank=True)
    posted_by = models.UUIDField(null=True, blank=True)
    journal_entry_id = models.UUIDField(null=True, blank=True)
    total_gross = models.DecimalField(**MONEY)
    total_deductions = models.DecimalField(**MONEY)
    total_net = models.DecimalField(**MONEY)
    employee_count = models.IntegerField(default=0)
    is_retro = models.BooleanField(default=False)

    class Meta:
        db_table = "payroll_runs"
        indexes = [models.Index(fields=["workspace_id", "payroll_period_id", "status"])]


class Payslip(TenantModel):
    number = models.CharField(max_length=64, blank=True)
    employee_record_id = models.UUIDField(db_index=True)
    payroll_period_id = models.UUIDField(db_index=True)
    payroll_run_id = models.UUIDField(db_index=True)
    currency = models.CharField(max_length=8, default="")
    fx_rate = models.DecimalField(**RATE)
    gross_pay = models.DecimalField(**MONEY)
    total_earnings = models.DecimalField(**MONEY)
    total_deductions = models.DecimalField(**MONEY)
    net_pay = models.DecimalField(**MONEY)
    cost_center = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=20, default="draft", choices=_choices(PAYSLIP_STATUS))
    snapshot = models.JSONField(default=dict)  # immutable: formula versions, rates, employee data, fx

    class Meta:
        db_table = "payroll_payslips"
        indexes = [models.Index(fields=["workspace_id", "payroll_run_id"]),
                   models.Index(fields=["workspace_id", "employee_record_id"])]


class PayslipLine(TenantModel):
    payslip_id = models.UUIDField(db_index=True)
    code = models.CharField(max_length=64)
    name = models.CharField(max_length=150)
    component_type = models.CharField(max_length=20, choices=_choices(COMPONENT_TYPES))
    amount = models.DecimalField(**MONEY)
    formula_version = models.IntegerField(default=0)
    source = models.CharField(max_length=20, default="computed")  # computed|adjustment|loan|advance|overtime|retro
    sequence = models.IntegerField(default=100)

    class Meta:
        db_table = "payroll_payslip_lines"
        indexes = [models.Index(fields=["workspace_id", "payslip_id", "sequence"])]


class PayrollSnapshot(TenantModel):
    """Immutable snapshot of a run's inputs so historical payroll never recalculates."""
    payroll_run_id = models.UUIDField(db_index=True)
    data = models.JSONField(default=dict)

    class Meta:
        db_table = "payroll_snapshots"
        indexes = [models.Index(fields=["workspace_id", "payroll_run_id"])]


class EmployeeLoan(TenantModel):
    employee_record_id = models.UUIDField(db_index=True)
    reference = models.CharField(max_length=64, blank=True)
    amount = models.DecimalField(**MONEY)
    balance = models.DecimalField(**MONEY)
    installment = models.DecimalField(**MONEY)
    status = models.CharField(max_length=20, default="active")  # active|closed|cancelled

    class Meta:
        db_table = "payroll_loans"
        indexes = [models.Index(fields=["workspace_id", "employee_record_id", "status"])]


class SalaryAdvance(TenantModel):
    employee_record_id = models.UUIDField(db_index=True)
    reference = models.CharField(max_length=64, blank=True)
    amount = models.DecimalField(**MONEY)
    balance = models.DecimalField(**MONEY)
    installment = models.DecimalField(**MONEY)
    status = models.CharField(max_length=20, default="active")

    class Meta:
        db_table = "payroll_advances"
        indexes = [models.Index(fields=["workspace_id", "employee_record_id", "status"])]


class OvertimeRequest(TenantModel):
    employee_record_id = models.UUIDField(db_index=True)
    date = models.DateField(null=True, blank=True)
    hours = models.DecimalField(**MONEY)
    rate = models.DecimalField(**MONEY)
    multiplier = models.DecimalField(max_digits=6, decimal_places=2, default=1)
    status = models.CharField(max_length=20, default="submitted")  # submitted|approved|rejected|processed
    payroll_period_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "payroll_overtime"
        indexes = [models.Index(fields=["workspace_id", "employee_record_id", "status"])]


class PayrollAdjustment(TenantModel):
    employee_record_id = models.UUIDField(db_index=True)
    payroll_period_id = models.UUIDField(null=True, blank=True)
    adj_type = models.CharField(max_length=20, default="bonus")  # bonus|correction|one_time|deduction|recovery
    code = models.CharField(max_length=64, blank=True)
    name = models.CharField(max_length=150, blank=True)
    amount = models.DecimalField(**MONEY)
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, default="pending")  # pending|applied

    class Meta:
        db_table = "payroll_adjustments"
        indexes = [models.Index(fields=["workspace_id", "employee_record_id", "status"])]


class FinalSettlement(TenantModel):
    employee_record_id = models.UUIDField(db_index=True)
    salary = models.DecimalField(**MONEY)
    leave_encashment = models.DecimalField(**MONEY)
    bonus = models.DecimalField(**MONEY)
    benefits = models.DecimalField(**MONEY)
    gratuity = models.DecimalField(**MONEY)
    loans = models.DecimalField(**MONEY)
    advances = models.DecimalField(**MONEY)
    penalties = models.DecimalField(**MONEY)
    net = models.DecimalField(**MONEY)
    status = models.CharField(max_length=20, default="draft")  # draft|approved|posted
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "payroll_final_settlements"
        indexes = [models.Index(fields=["workspace_id", "employee_record_id"])]


class FXRate(TenantModel):
    from_currency = models.CharField(max_length=8)
    to_currency = models.CharField(max_length=8)
    rate = models.DecimalField(**RATE)
    effective_date = models.DateField()

    class Meta:
        db_table = "payroll_fx_rates"
        indexes = [models.Index(fields=["workspace_id", "from_currency", "to_currency",
                                        "-effective_date"])]


class CostAllocation(TenantModel):
    """Splits an employee's payroll cost across dimensions (department/branch/cost_center/project)."""
    employee_record_id = models.UUIDField(db_index=True)
    dimension = models.CharField(max_length=20, default="cost_center")
    target_ref = models.CharField(max_length=64)
    percentage = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    class Meta:
        db_table = "payroll_cost_allocations"
        indexes = [models.Index(fields=["workspace_id", "employee_record_id"])]
