from rest_framework import serializers

from .models import (
    EmployeeLoan,
    EmployeePayrollProfile,
    EmploymentContract,
    FinalSettlement,
    OvertimeRequest,
    PayrollAdjustment,
    PayrollCalendar,
    PayrollPeriod,
    PayrollRun,
    PayrollSettings,
    Payslip,
    PayslipLine,
    SalaryAdvance,
    SalaryStructure,
    SalaryStructureAssignment,
    StructureComponent,
)

_RO = ["id", "workspace_id", "created_at", "updated_at"]


def _ser(model_cls, read_only=None):
    meta_ro = list(_RO) + list(read_only or [])

    class _S(serializers.ModelSerializer):
        class Meta:
            model = model_cls
            exclude = ["deleted_at", "deleted_by", "created_by", "updated_by"]
            read_only_fields = meta_ro

    return _S


SettingsSerializer = _ser(PayrollSettings)
CalendarSerializer = _ser(PayrollCalendar)
SalaryStructureSerializer = _ser(SalaryStructure)
StructureComponentSerializer = _ser(StructureComponent)
AssignmentSerializer = _ser(SalaryStructureAssignment)
ProfileSerializer = _ser(EmployeePayrollProfile)
ContractSerializer = _ser(EmploymentContract)
PeriodSerializer = _ser(PayrollPeriod, read_only=["status"])
RunSerializer = _ser(PayrollRun, read_only=[
    "status", "started_by", "started_at", "approved_by", "posted_by", "journal_entry_id",
    "total_gross", "total_deductions", "total_net", "employee_count"])
PayslipSerializer = _ser(Payslip, read_only=[
    "number", "gross_pay", "total_earnings", "total_deductions", "net_pay", "status", "snapshot"])
PayslipLineSerializer = _ser(PayslipLine)
LoanSerializer = _ser(EmployeeLoan, read_only=["balance", "status"])
AdvanceSerializer = _ser(SalaryAdvance, read_only=["balance", "status"])
OvertimeSerializer = _ser(OvertimeRequest, read_only=["status"])
AdjustmentSerializer = _ser(PayrollAdjustment, read_only=["status"])
FinalSettlementSerializer = _ser(FinalSettlement, read_only=[
    "salary", "leave_encashment", "bonus", "benefits", "gratuity", "loans", "advances",
    "penalties", "net", "status"])
