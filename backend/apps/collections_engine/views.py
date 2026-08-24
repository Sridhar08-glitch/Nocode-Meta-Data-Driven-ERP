"""
Collections Engine REST API (F2) at /api/v1/collections/.

Plan creation, payment recording, and late-fee charging are financial writes → owner/admin
gated; reads (plan/installment lists, dashboard) are open to any workspace member. The engine is
package-independent: School/Membership/etc. call it (or the ``action_create_installment_plan`` /
``action_charge_late_fee`` workflow steps) without shipping collections code.
"""
import uuid

from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import InstallmentPlan
from .serializers import (
    InstallmentPlanSerializer,
    InstallmentSerializer,
    PaymentSerializer,
    PlanCreateSerializer,
)
from .services import CollectionsError, CollectionsService

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
        raise PermissionDenied("Collections management requires an admin or owner role.")


def _uid(request):
    return getattr(request.user, "id", None)


class SetupView(APIView):
    def post(self, request):
        _require_admin(request)
        CollectionsService.ensure_sequences(_ws(request), actor_id=_uid(request))
        return Response({"detail": "Collections numbering ready."})


class PlanList(APIView):
    def get(self, request):
        qs = InstallmentPlan.objects.filter(workspace_id=_ws(request))
        status = request.query_params.get("status")
        if status:
            qs = qs.filter(status=status)
        subject = request.query_params.get("subject_ref")
        if subject:
            qs = qs.filter(subject_ref=subject)
        return Response(InstallmentPlanSerializer(qs.order_by("-created_at")[:500], many=True).data)

    def post(self, request):
        _require_admin(request)
        ser = PlanCreateSerializer(data=request.data or {})
        ser.is_valid(raise_exception=True)
        try:
            plan = CollectionsService.create_plan(
                workspace_id=_ws(request), actor_id=_uid(request), **ser.validated_data)
        except CollectionsError as exc:
            raise ValidationError(str(exc)) from exc
        data = InstallmentPlanSerializer(plan).data
        data["installments"] = InstallmentSerializer(
            CollectionsService.plan_installments(_ws(request), plan.id), many=True).data
        return Response(data, status=201)


class PlanDetail(APIView):
    def get(self, request, pk):
        plan = InstallmentPlan.objects.filter(workspace_id=_ws(request), id=pk).first()
        if plan is None:
            raise PermissionDenied("Plan not found.")
        data = InstallmentPlanSerializer(plan).data
        data["installments"] = InstallmentSerializer(
            CollectionsService.plan_installments(_ws(request), plan.id), many=True).data
        return Response(data)


class PlanRecordPayment(APIView):
    def post(self, request, pk):
        _require_admin(request)
        ser = PaymentSerializer(data=request.data or {})
        ser.is_valid(raise_exception=True)
        try:
            result = CollectionsService.record_payment(
                workspace_id=_ws(request), plan_id=pk, amount=ser.validated_data["amount"],
                installment_id=ser.validated_data.get("installment_id"), actor_id=_uid(request))
        except CollectionsError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(result)


class InstallmentChargeLateFee(APIView):
    def post(self, request, pk):
        _require_admin(request)
        inst = CollectionsService.charge_late_fee(
            workspace_id=_ws(request), installment_id=pk, actor_id=_uid(request))
        if inst is None:
            return Response({"charged": False, "reason": "not_applicable"})
        return Response({"charged": True, **InstallmentSerializer(inst).data})


class RunLateFees(APIView):
    def post(self, request):
        _require_admin(request)
        n = CollectionsService.run_late_fees(workspace_id=_ws(request), actor_id=_uid(request))
        return Response({"charged": n})


class RunReminders(APIView):
    def post(self, request):
        _require_admin(request)
        n = CollectionsService.run_reminders(workspace_id=_ws(request), actor_id=_uid(request))
        return Response({"reminders_sent": n})


class Dashboard(APIView):
    def get(self, request):
        return Response(CollectionsService.dashboard(_ws(request)))
