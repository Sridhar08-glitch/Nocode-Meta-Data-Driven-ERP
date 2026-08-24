"""
Branding REST API (PROJECT_HANDBOOK.md §32.3) at /api/v1/branding/.

Workspace-scoped white-label branding + SMTP config + connection test. Writes are
role-gated (owner/admin); the SMTP password is held by reference only and never
returned.
"""
import uuid

from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import EmailSMTPConfigSerializer, WorkspaceBrandingSerializer
from .services import BrandingError, BrandingService

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
    m = _member(request)
    if getattr(m, "role", "") not in _ADMIN_ROLES:
        raise PermissionDenied("Admin role required.")
    return m


class BrandingView(APIView):
    def get(self, request):
        _member(request)
        obj = BrandingService.get_or_create(_ws(request))
        return Response(WorkspaceBrandingSerializer(obj).data)

    def patch(self, request):
        _require_admin(request)
        try:
            obj = BrandingService.update_branding(_ws(request), request.data)
        except BrandingError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(WorkspaceBrandingSerializer(obj).data)


class SMTPConfigView(APIView):
    def get(self, request):
        _member(request)
        obj = BrandingService.get_smtp(_ws(request))
        return Response(EmailSMTPConfigSerializer(obj).data if obj else {})

    def patch(self, request):
        _require_admin(request)
        obj = BrandingService.save_smtp_config(_ws(request), request.data)
        return Response(EmailSMTPConfigSerializer(obj).data)


class SMTPTestView(APIView):
    def post(self, request):
        _require_admin(request)
        try:
            result = BrandingService.test_smtp(_ws(request))
        except BrandingError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(result)
