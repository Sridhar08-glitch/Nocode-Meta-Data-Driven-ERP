"""Consolidation REST API at /api/v1/consolidation/. Admin-gated writes; member reads."""
import uuid

from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ConsolidationRun, ConsolidationWorksheetLine
from .services import ConsolidationError, ConsolidationService, IntercompanyService

_ADMIN_ROLES = {"owner", "admin"}


def _ws(request) -> uuid.UUID:
    ws = getattr(request, "workspace_id", None)
    if not ws:
        raise PermissionDenied("No active workspace. Send the X-Workspace-Slug header.")
    return ws if isinstance(ws, uuid.UUID) else uuid.UUID(str(ws))


def _require_admin(request):
    m = getattr(request, "workspace_member", None)
    if m is None or getattr(m, "role", "") not in _ADMIN_ROLES:
        raise PermissionDenied("Consolidation requires an admin or owner role.")


def _uid(request):
    return getattr(request.user, "id", None)


class IntercompanyView(APIView):
    def post(self, request):
        _require_admin(request)
        d = request.data or {}
        try:
            out = IntercompanyService.post_transaction(
                workspace_id=_ws(request), from_company=d.get("from_company"),
                to_company=d.get("to_company"), amount=d.get("amount"),
                from_account=d.get("from_account", "6900"), to_account=d.get("to_account", "4000"),
                description=d.get("description", ""), date=d.get("date"),
                external_ref=d.get("external_ref", ""), actor_id=_uid(request))
        except ConsolidationError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(out, status=201)


class RunView(APIView):
    def get(self, request):
        qs = ConsolidationRun.objects.filter(workspace_id=_ws(request)).order_by("-created_at")[:100]
        return Response([{"id": str(r.id), "group": r.group_code, "as_of": str(r.as_of),
                          "version_no": r.version_no, "status": r.status, "balanced": r.balanced,
                          "cta": str(r.cta),
                          "total_minority_interest": str(r.total_minority_interest)} for r in qs])

    def post(self, request):
        _require_admin(request)
        d = request.data or {}
        try:
            run = ConsolidationService.run(
                workspace_id=_ws(request), group_id=d.get("group_id"), as_of=d.get("as_of"),
                presentation_currency=d.get("presentation_currency"),
                status=d.get("status", "final"), actor_id=_uid(request))
        except ConsolidationError as exc:
            raise ValidationError(str(exc)) from exc
        return Response({"id": str(run.id), "version_no": run.version_no,
                         "balanced": run.balanced}, status=201)


class RunDetail(APIView):
    def get(self, request, pk):
        run = ConsolidationRun.objects.filter(workspace_id=_ws(request), id=pk).first()
        if run is None:
            raise PermissionDenied("Consolidation run not found.")
        return Response({"id": str(run.id), "group": run.group_code, "status": run.status,
                         "version_no": run.version_no, "balanced": run.balanced,
                         "worksheet": run.worksheet})


class RunWorksheetView(APIView):
    """The queryable worksheet DETAIL (first-class rows). Filter by ``?company=`` (blank/CONS for the
    consolidated group total) and ``?account=``."""
    def get(self, request, pk):
        run = ConsolidationRun.objects.filter(workspace_id=_ws(request), id=pk).first()
        if run is None:
            raise PermissionDenied("Consolidation run not found.")
        qs = ConsolidationWorksheetLine.objects.filter(workspace_id=_ws(request), run=run)
        company = request.query_params.get("company")
        if company is not None:
            qs = qs.filter(company_code="" if company.upper() in ("", "CONS") else company)
        account = request.query_params.get("account")
        if account:
            qs = qs.filter(account_code=account)
        return Response([{"company_code": ln.company_code or "CONS", "account_code": ln.account_code,
                          "account_type": ln.account_type,
                          "functional_balance": str(ln.functional_balance),
                          "translated_balance": str(ln.translated_balance),
                          "eliminated_amount": str(ln.eliminated_amount), "is_cta": ln.is_cta}
                         for ln in qs.order_by("company_code", "account_code")[:5000]])
