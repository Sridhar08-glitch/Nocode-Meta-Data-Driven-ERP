"""
Business Rules management API (frontend F2.4) — /api/v1/rules/.

CRUD over `BusinessRule`. Reads = any member; writes = owner/admin (rules are automation
config). Workspace-scoped; the rule ENGINE (evaluation on record save) is unchanged.
"""
import uuid

from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import BusinessRule
from .serializers import BusinessRuleSerializer

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
        raise PermissionDenied("Managing rules requires an admin or owner role.")


def _get(request, pk) -> BusinessRule:
    rule = BusinessRule.objects.filter(id=pk, workspace_id=_ws(request)).first()
    if rule is None:
        raise NotFound("Rule not found.")
    return rule


class RuleListCreateView(APIView):
    def get(self, request):
        _member(request)
        qs = BusinessRule.objects.filter(workspace_id=_ws(request))
        entity_id = request.query_params.get("entity_id")
        if entity_id:
            qs = qs.filter(entity_id=entity_id)
        qs = qs.order_by("priority", "name")
        return Response({"results": BusinessRuleSerializer(qs, many=True).data, "count": qs.count()})

    def post(self, request):
        _require_admin(request)
        ser = BusinessRuleSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ws = _ws(request)
        if BusinessRule.objects.filter(workspace_id=ws, slug=ser.validated_data["slug"]).exists():
            raise ValidationError("A rule with this slug already exists.")
        rule = ser.save(workspace_id=ws)
        return Response(BusinessRuleSerializer(rule).data, status=status.HTTP_201_CREATED)


class RuleDetailView(APIView):
    def get(self, request, pk):
        _member(request)
        return Response(BusinessRuleSerializer(_get(request, pk)).data)

    def patch(self, request, pk):
        _require_admin(request)
        rule = _get(request, pk)
        ser = BusinessRuleSerializer(rule, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(BusinessRuleSerializer(rule).data)

    def delete(self, request, pk):
        _require_admin(request)
        _get(request, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
