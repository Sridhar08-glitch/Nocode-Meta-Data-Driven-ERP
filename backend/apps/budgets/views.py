"""
Budgets & Forecasts REST API at /api/v1/budgets/.

Plan/version/line maintenance + approval/lock are admin-gated; budget-vs-actual / utilization reads
available to any member. Workspace-scoped. Package-independent — every package plans through this;
none ships a budget engine.
"""
import uuid

from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import FinancialPlan
from .services import BudgetError, BudgetService

_ADMIN_ROLES = {"owner", "admin"}


def _ws(request) -> uuid.UUID:
    ws = getattr(request, "workspace_id", None)
    if not ws:
        raise PermissionDenied("No active workspace. Send the X-Workspace-Slug header.")
    return ws if isinstance(ws, uuid.UUID) else uuid.UUID(str(ws))


def _require_admin(request):
    m = getattr(request, "workspace_member", None)
    if m is None or getattr(m, "role", "") not in _ADMIN_ROLES:
        raise PermissionDenied("Budget maintenance requires an admin or owner role.")


def _uid(request):
    return getattr(request.user, "id", None)


def _call(fn, **kw):
    try:
        return fn(**kw)
    except BudgetError as exc:
        raise ValidationError(str(exc)) from exc


class PlanList(APIView):
    def get(self, request):
        qs = FinancialPlan.objects.filter(workspace_id=_ws(request)).order_by("-created_at")[:200]
        ptype = request.query_params.get("plan_type")
        if ptype:
            qs = qs.filter(plan_type=ptype)
        return Response([{"id": str(p.id), "code": p.code, "name": p.name,
                          "plan_type": p.plan_type, "fiscal_year": p.fiscal_year,
                          "status": p.status} for p in qs])

    def post(self, request):
        _require_admin(request)
        d = request.data or {}
        if not d.get("code"):
            raise ValidationError("code required.")
        plan = _call(BudgetService.create_plan, workspace_id=_ws(request), code=d["code"],
                     name=d.get("name", ""), plan_type=d.get("plan_type", "budget"),
                     fiscal_year=d.get("fiscal_year", ""),
                     period_type=d.get("period_type", "monthly"),
                     currency=d.get("currency", ""), is_rolling=bool(d.get("is_rolling", False)),
                     actor_id=_uid(request))
        return Response({"id": str(plan.id), "code": plan.code}, status=201)


class VersionList(APIView):
    def post(self, request):
        _require_admin(request)
        d = request.data or {}
        v = _call(BudgetService.create_version, workspace_id=_ws(request),
                  plan_id=d.get("plan_id"), scenario=d.get("scenario", "baseline"),
                  revision_note=d.get("revision_note", ""),
                  copy_from_version=d.get("copy_from_version"), actor_id=_uid(request))
        return Response({"id": str(v.id), "version_no": v.version_no, "scenario": v.scenario},
                        status=201)


class LineView(APIView):
    def post(self, request, version_id):
        _require_admin(request)
        d = request.data or {}
        line = _call(BudgetService.add_line, workspace_id=_ws(request), version_id=version_id,
                     account_code=d.get("account_code"), amount=d.get("amount"),
                     dimensions=d.get("dimensions", {}), period=d.get("period", ""),
                     period_date=d.get("period_date"), notes=d.get("notes", ""),
                     actor_id=_uid(request))
        return Response({"id": str(line.id)}, status=201)


class AllocateView(APIView):
    def post(self, request, version_id):
        _require_admin(request)
        d = request.data or {}
        lines = _call(BudgetService.allocate, workspace_id=_ws(request), version_id=version_id,
                      account_code=d.get("account_code"), total=d.get("total"),
                      periods=d.get("periods", []), dimensions=d.get("dimensions", {}),
                      method=d.get("method", "even"), weights=d.get("weights"),
                      actor_id=_uid(request))
        return Response({"lines_created": len(lines)}, status=201)


class LifecycleView(APIView):
    action = None

    def post(self, request, version_id):
        _require_admin(request)
        fn = {"submit": BudgetService.submit, "approve": BudgetService.approve,
              "lock": BudgetService.lock}[self.action]
        v = _call(fn, workspace_id=_ws(request), version_id=version_id, actor_id=_uid(request))
        return Response({"id": str(v.id), "status": v.status})


class SubmitView(LifecycleView):
    action = "submit"


class ApproveView(LifecycleView):
    action = "approve"


class LockView(LifecycleView):
    action = "lock"


class BudgetVsActualView(APIView):
    def get(self, request, version_id):
        return Response(_call(BudgetService.budget_vs_actual, workspace_id=_ws(request),
                              version_id=version_id, from_date=request.query_params.get("from"),
                              to_date=request.query_params.get("to"),
                              group_by_dimension=request.query_params.get("group_by")))


class UtilizationView(APIView):
    def get(self, request, version_id):
        return Response(_call(BudgetService.utilization, workspace_id=_ws(request),
                              version_id=version_id))
