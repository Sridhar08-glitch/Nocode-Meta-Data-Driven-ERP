"""
Credit Engine REST API (F3) at /api/v1/credits/.

Issuing/voiding a credit is a financial operation → owner/admin gated. Reads are available to
any workspace member. Everything is workspace-scoped (RLS applies); the engine itself is
package-independent — School/Hospital/etc. call it (or the ``action_apply_credit`` /
``action_issue_refund`` workflow steps) without shipping their own crediting code.
"""
import uuid

from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CreditNote
from .serializers import CreditIssueSerializer, CreditNoteSerializer
from .services import CreditError, CreditService

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
        raise PermissionDenied("Credit management requires an admin or owner role.")


def _uid(request):
    return getattr(request.user, "id", None)


class SetupView(APIView):
    def post(self, request):
        _require_admin(request)
        CreditService.ensure_sequences(_ws(request), actor_id=_uid(request))
        return Response({"detail": "Credit numbering ready."})


class CreditList(APIView):
    def get(self, request):
        qs = CreditNote.objects.filter(workspace_id=_ws(request))
        kind = request.query_params.get("kind")
        if kind:
            qs = qs.filter(kind=kind)
        applies_to = request.query_params.get("applies_to_ref")
        if applies_to:
            qs = qs.filter(applies_to_ref=applies_to)
        subject = request.query_params.get("subject_ref")
        if subject:
            qs = qs.filter(subject_ref=subject)
        qs = qs.order_by("-created_at")[:500]
        return Response(CreditNoteSerializer(qs, many=True).data)

    def post(self, request):
        _require_admin(request)
        ser = CreditIssueSerializer(data=request.data or {})
        ser.is_valid(raise_exception=True)
        try:
            note = CreditService.issue(
                workspace_id=_ws(request), actor_id=_uid(request), **ser.validated_data)
        except CreditError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(CreditNoteSerializer(note).data, status=201)


class CreditDetail(APIView):
    def get(self, request, pk):
        note = CreditNote.objects.filter(workspace_id=_ws(request), id=pk).first()
        if note is None:
            raise PermissionDenied("Credit not found.")
        return Response(CreditNoteSerializer(note).data)


class CreditVoid(APIView):
    def post(self, request, pk):
        _require_admin(request)
        try:
            note = CreditService.void(
                workspace_id=_ws(request), credit_id=pk,
                reason=(request.data or {}).get("reason", ""), actor_id=_uid(request))
        except CreditError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(CreditNoteSerializer(note).data)
