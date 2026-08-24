"""
Payroll Engine REST API (Phase P2.8) at /api/v1/payroll/.

Master data (settings/calendars/structures/components/profiles/contracts/periods) + ancillary
records (loans/advances/overtime/adjustments) are CRUD-managed (admin writes). The run lifecycle
(create/calculate/approve/post/lock) enforces segregation of duties at the service layer. Posted
payslips are immutable.
"""
import uuid

from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from . import serializers as S
from .extras import (
    AdjustmentService,
    AdvanceService,
    LoanService,
    OvertimeService,
    SettlementService,
)
from .models import (
    EmployeeLoan,
    EmployeePayrollProfile,
    EmploymentContract,
    OvertimeRequest,
    PayrollAdjustment,
    PayrollCalendar,
    PayrollPeriod,
    PayrollRun,
    Payslip,
    PayslipLine,
    SalaryAdvance,
    SalaryStructure,
    SalaryStructureAssignment,
    StructureComponent,
)
from .services import PayrollError, PayrollService

_ADMIN_ROLES = {"owner", "admin"}


def _ws(request) -> uuid.UUID:
    ws = getattr(request, "workspace_id", None)
    if not ws:
        raise PermissionDenied("No active workspace. Send the X-Workspace-Slug header.")
    return ws if isinstance(ws, uuid.UUID) else uuid.UUID(str(ws))


def _member(request):
    m = getattr(request, "workspace_member", None)
    if m is None:
        raise PermissionDenied("No workspace membership for this request.")
    return m


def _require_admin(request):
    if getattr(_member(request), "role", "") not in _ADMIN_ROLES:
        raise PermissionDenied("Payroll management requires an admin or owner role.")


def _uid(request):
    return getattr(request.user, "id", None)


# ── generic CRUD base for master data (admin writes, member reads) ────────────
class _CrudList(APIView):
    model = None
    serializer = None
    order = "-created_at"

    def get(self, request):
        qs = self.model.objects.filter(workspace_id=_ws(request)).order_by(self.order)
        for key in getattr(self, "filters", []):
            val = request.query_params.get(key)
            if val:
                qs = qs.filter(**{key: val})
        return Response(self.serializer(qs, many=True).data)

    def post(self, request):
        _require_admin(request)
        ser = self.serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = self.model.objects.create(workspace_id=_ws(request), created_by=_uid(request),
                                        **ser.validated_data)
        return Response(self.serializer(obj).data, status=201)


class _CrudDetail(APIView):
    model = None
    serializer = None

    def _obj(self, request, pk):
        obj = self.model.objects.filter(workspace_id=_ws(request), id=pk).first()
        if obj is None:
            raise PermissionDenied("Not found.")
        return obj

    def get(self, request, pk):
        return Response(self.serializer(self._obj(request, pk)).data)

    def patch(self, request, pk):
        _require_admin(request)
        obj = self._obj(request, pk)
        ser = self.serializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save(updated_by=_uid(request))
        return Response(self.serializer(obj).data)


class CalendarList(_CrudList):
    model, serializer = PayrollCalendar, S.CalendarSerializer
class CalendarDetail(_CrudDetail):
    model, serializer = PayrollCalendar, S.CalendarSerializer
class StructureList(_CrudList):
    model, serializer = SalaryStructure, S.SalaryStructureSerializer
class StructureDetail(_CrudDetail):
    model, serializer = SalaryStructure, S.SalaryStructureSerializer
class ComponentList(_CrudList):
    model, serializer, filters = StructureComponent, S.StructureComponentSerializer, ["salary_structure_id"]
class ComponentDetail(_CrudDetail):
    model, serializer = StructureComponent, S.StructureComponentSerializer
class AssignmentList(_CrudList):
    model, serializer, filters = SalaryStructureAssignment, S.AssignmentSerializer, ["employee_record_id"]
class ProfileList(_CrudList):
    model, serializer, filters = EmployeePayrollProfile, S.ProfileSerializer, ["employee_record_id"]
class ContractList(_CrudList):
    model, serializer, filters = EmploymentContract, S.ContractSerializer, ["employee_record_id"]
class PeriodList(_CrudList):
    model, serializer = PayrollPeriod, S.PeriodSerializer
class PeriodDetail(_CrudDetail):
    model, serializer = PayrollPeriod, S.PeriodSerializer
class RunList(_CrudList):
    model, serializer, filters = PayrollRun, S.RunSerializer, ["payroll_period_id", "status"]
class RunDetail(_CrudDetail):
    model, serializer = PayrollRun, S.RunSerializer
class OvertimeList(_CrudList):
    model, serializer, filters = OvertimeRequest, S.OvertimeSerializer, ["employee_record_id", "status"]
class AdjustmentList(_CrudList):
    model, serializer, filters = PayrollAdjustment, S.AdjustmentSerializer, ["employee_record_id"]


# ── settings ──────────────────────────────────────────────────────────────────
class SettingsView(APIView):
    def get(self, request):
        return Response(S.SettingsSerializer(
            PayrollService.get_settings(_ws(request))).data)

    def patch(self, request):
        _require_admin(request)
        obj = PayrollService.get_settings(_ws(request))
        ser = S.SettingsSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save(updated_by=_uid(request))
        return Response(S.SettingsSerializer(obj).data)


class SetupView(APIView):
    def post(self, request):
        _require_admin(request)
        PayrollService.ensure_sequences(_ws(request), actor_id=_uid(request))
        return Response({"detail": "Payroll numbering ready."})


# ── period lifecycle ──────────────────────────────────────────────────────────
def _period_action(request, period_id, fn):
    _require_admin(request)
    try:
        period = fn(workspace_id=_ws(request), period_id=period_id, actor_id=_uid(request))
    except PayrollError as exc:
        return Response({"detail": str(exc)}, status=400)
    return Response(S.PeriodSerializer(period).data)


class PeriodOpen(APIView):
    def post(self, request, pk): return _period_action(request, pk, PayrollService.open_period)
class PeriodClose(APIView):
    def post(self, request, pk): return _period_action(request, pk, PayrollService.close_period)
class PeriodLock(APIView):
    def post(self, request, pk): return _period_action(request, pk, PayrollService.lock_period)
class PeriodReopen(APIView):
    def post(self, request, pk): return _period_action(request, pk, PayrollService.reopen_period)


# ── run lifecycle ─────────────────────────────────────────────────────────────
def _run_action(request, run_id, fn):
    _require_admin(request)
    try:
        run = fn(workspace_id=_ws(request), run_id=run_id, actor_id=_uid(request))
    except PayrollError as exc:
        return Response({"detail": str(exc)}, status=400)
    return Response(S.RunSerializer(run).data)


class RunCreate(APIView):
    def post(self, request):
        _require_admin(request)
        try:
            run = PayrollService.create_run(
                workspace_id=_ws(request), period_id=request.data.get("payroll_period_id"),
                actor_id=_uid(request))
        except PayrollError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(S.RunSerializer(run).data, status=201)


class RunCalculate(APIView):
    def post(self, request, pk): return _run_action(request, pk, PayrollService.calculate_run)
class RunApprove(APIView):
    def post(self, request, pk): return _run_action(request, pk, PayrollService.approve_run)
class RunPost(APIView):
    def post(self, request, pk): return _run_action(request, pk, PayrollService.post_run)
class RunLock(APIView):
    def post(self, request, pk): return _run_action(request, pk, PayrollService.lock_run)


class RunRegister(APIView):
    def get(self, request, pk):
        return Response(PayrollService.register(workspace_id=_ws(request), run_id=pk))
class RunSummary(APIView):
    def get(self, request, pk):
        try:
            return Response(PayrollService.summary(workspace_id=_ws(request), run_id=pk))
        except PayrollError:
            return Response({"detail": "Not found."}, status=404)


# ── payslips (read-only; immutable once posted) ──────────────────────────────
class PayslipList(APIView):
    def get(self, request):
        qs = Payslip.objects.filter(workspace_id=_ws(request))
        for key in ("payroll_run_id", "employee_record_id"):
            val = request.query_params.get(key)
            if val:
                qs = qs.filter(**{key: val})
        return Response(S.PayslipSerializer(qs.order_by("number"), many=True).data)


class PayslipDetail(APIView):
    def get(self, request, pk):
        slip = Payslip.objects.filter(workspace_id=_ws(request), id=pk).first()
        if slip is None:
            return Response({"detail": "Not found."}, status=404)
        lines = PayslipLine.objects.filter(
            workspace_id=_ws(request), payslip_id=slip.id).order_by("sequence")
        data = S.PayslipSerializer(slip).data
        data["lines"] = S.PayslipLineSerializer(lines, many=True).data
        return Response(data)


# ── loans / advances / overtime / adjustments / settlement ───────────────────
class LoanList(APIView):
    def get(self, request):
        qs = EmployeeLoan.objects.filter(workspace_id=_ws(request)).order_by("-created_at")
        emp = request.query_params.get("employee_record_id")
        if emp:
            qs = qs.filter(employee_record_id=emp)
        return Response(S.LoanSerializer(qs, many=True).data)

    def post(self, request):
        _require_admin(request)
        d = request.data
        loan = LoanService.create_loan(
            workspace_id=_ws(request), employee_record_id=d.get("employee_record_id"),
            amount=d.get("amount", 0), installment=d.get("installment", 0),
            reference=d.get("reference", ""), actor_id=_uid(request))
        return Response(S.LoanSerializer(loan).data, status=201)


class AdvanceList(APIView):
    def get(self, request):
        qs = SalaryAdvance.objects.filter(workspace_id=_ws(request)).order_by("-created_at")
        emp = request.query_params.get("employee_record_id")
        if emp:
            qs = qs.filter(employee_record_id=emp)
        return Response(S.AdvanceSerializer(qs, many=True).data)

    def post(self, request):
        _require_admin(request)
        d = request.data
        adv = AdvanceService.create_advance(
            workspace_id=_ws(request), employee_record_id=d.get("employee_record_id"),
            amount=d.get("amount", 0), installment=d.get("installment", 0),
            reference=d.get("reference", ""), actor_id=_uid(request))
        return Response(S.AdvanceSerializer(adv).data, status=201)


class OvertimeCreate(APIView):
    def post(self, request):
        _require_admin(request)
        d = request.data
        ot = OvertimeService.create(
            workspace_id=_ws(request), employee_record_id=d.get("employee_record_id"),
            hours=d.get("hours", 0), rate=d.get("rate", 0),
            multiplier=d.get("multiplier", 1), date=d.get("date"), actor_id=_uid(request))
        return Response(S.OvertimeSerializer(ot).data, status=201)


class OvertimeApprove(APIView):
    def post(self, request, pk):
        _require_admin(request)
        try:
            ot = OvertimeService.approve(
                workspace_id=_ws(request), overtime_id=pk, actor_id=_uid(request))
        except PayrollError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(S.OvertimeSerializer(ot).data)


class AdjustmentCreate(APIView):
    def post(self, request):
        _require_admin(request)
        d = request.data
        adj = AdjustmentService.create(
            workspace_id=_ws(request), employee_record_id=d.get("employee_record_id"),
            adj_type=d.get("adj_type", "bonus"), amount=d.get("amount", 0),
            name=d.get("name", ""), code=d.get("code", ""), reason=d.get("reason", ""),
            actor_id=_uid(request))
        return Response(S.AdjustmentSerializer(adj).data, status=201)


class FinalSettlementCreate(APIView):
    def post(self, request):
        _require_admin(request)
        d = request.data
        fs = SettlementService.compute_final_settlement(
            workspace_id=_ws(request), employee_record_id=d.get("employee_record_id"),
            salary=d.get("salary", 0), leave_encashment=d.get("leave_encashment", 0),
            bonus=d.get("bonus", 0), benefits=d.get("benefits", 0),
            penalties=d.get("penalties", 0), service_years=d.get("service_years", 0),
            last_basic=d.get("last_basic", 0), country=d.get("country", ""),
            actor_id=_uid(request))
        return Response(S.FinalSettlementSerializer(fs).data, status=201)
