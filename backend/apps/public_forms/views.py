"""
Public Forms REST API (PROJECT_HANDBOOK.md §33.2) at /api/v1/public-forms/.

Two realms:
  * The public submit endpoint ``{form_id}/submit/`` — unauthenticated,
    rate-limited (5/hour/IP), honeypot-aware, never reveals validation detail.
  * Authenticated admin endpoints for form definitions + submission review,
    workspace-scoped and role-gated.
"""
import uuid

from django.core.cache import cache
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.metadata.models import FormDefinition

from .models import FormSubmission
from .serializers import FormDefinitionSerializer, FormSubmissionSerializer
from .services import PublicFormError, PublicFormService

_ADMIN_ROLES = {"owner", "admin"}
_WRITE_ROLES = {"owner", "admin", "member"}
HONEYPOT_FIELD = "_hp"
SUBMIT_RATE_LIMIT = 5  # submissions / hour / IP


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


def _require(request, roles):
    m = _member(request)
    if getattr(m, "role", "") not in roles:
        raise PermissionDenied("Insufficient role for this action.")
    return m


def _client_ip(request) -> str:
    fwd = request.META.get("HTTP_X_FORWARDED_FOR")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


# ── Public (unauthenticated) submit endpoint ─────────────────────────────────
class PublicFormSubmitView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, form_id):
        ip = _client_ip(request)
        bucket = f"form_submit:{form_id}:{ip}"
        count = cache.get(bucket, 0)
        if count >= SUBMIT_RATE_LIMIT:
            return Response({"detail": "rate limit exceeded"}, status=429)
        cache.set(bucket, count + 1, timeout=3600)

        payload = request.data if isinstance(request.data, dict) else {}
        raw = {k: v for k, v in payload.items() if k != HONEYPOT_FIELD}
        honeypot = str(payload.get(HONEYPOT_FIELD, "") or "")
        try:
            PublicFormService.submit(
                form_id=form_id, raw_data=raw, submitter_ip=ip or None,
                honeypot_value=honeypot,
                submitter_name=str(payload.get("_name", "") or "")[:255],
                submitter_email=str(payload.get("_email", "") or "")[:254])
        except PublicFormError:
            # Never reveal whether the form exists / is public to anonymous callers.
            return Response({"success": True})
        except Exception:  # noqa: BLE001 — internal errors must not leak to spammers
            return Response({"success": True})
        return Response({"success": True})


# ── Public (unauthenticated) form schema for rendering ───────────────────────
class PublicFormSchemaView(APIView):
    """
    Public, renderable schema for a form flagged ``is_public`` (Phase F3.8). Returns only the
    field layout + submit settings — never submissions or workspace internals — so the public
    runtime can render the fields it will POST to ``{form_id}/submit/``.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, form_id):
        from apps.metadata.services import FormSchemaError, FormSchemaService

        form = FormDefinition.objects.filter(id=form_id, is_public=True).select_related("entity").first()
        if form is None:
            raise NotFound("Form not found.")
        try:
            schema = FormSchemaService.resolve_schema(
                workspace_id=form.workspace_id, entity_slug=form.entity.slug,
                member=None, form_id=form.id)
        except FormSchemaError as exc:
            raise NotFound(str(exc)) from exc
        return Response({
            "form_id": str(form.id),
            "name": form.name,
            "entity_slug": form.entity.slug,
            "honeypot_field": HONEYPOT_FIELD,
            "settings": form.settings or {},
            "schema": schema,
        })


# ── Admin: form definitions ──────────────────────────────────────────────────
class FormListView(APIView):
    def get(self, request):
        _member(request)
        qs = FormDefinition.objects.filter(workspace_id=_ws(request)).order_by("-created_at")
        return Response({"results": FormDefinitionSerializer(qs, many=True).data})

    def post(self, request):
        member = _require(request, _ADMIN_ROLES)
        ws = _ws(request)
        ser = FormDefinitionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        entity = ser.validated_data["entity"]
        if entity.workspace_id != ws:
            raise ValidationError("Entity does not belong to this workspace.")
        obj = ser.save(workspace_id=ws, created_by=member.user_id)
        return Response(FormDefinitionSerializer(obj).data, status=201)


class FormDetailView(APIView):
    def _get(self, request, pk) -> FormDefinition:
        obj = FormDefinition.objects.filter(id=pk, workspace_id=_ws(request)).first()
        if obj is None:
            raise NotFound("Form not found")
        return obj

    def get(self, request, pk):
        _member(request)
        return Response(FormDefinitionSerializer(self._get(request, pk)).data)

    def patch(self, request, pk):
        _require(request, _ADMIN_ROLES)
        obj = self._get(request, pk)
        ser = FormDefinitionSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(FormDefinitionSerializer(obj).data)

    def delete(self, request, pk):
        _require(request, _ADMIN_ROLES)
        self._get(request, pk).delete()
        return Response(status=204)


# ── Admin: submissions ───────────────────────────────────────────────────────
class FormSubmissionListView(APIView):
    def get(self, request, pk):
        _member(request)
        ws = _ws(request)
        if not FormDefinition.objects.filter(id=pk, workspace_id=ws).exists():
            raise NotFound("Form not found")
        qs = FormSubmission.objects.filter(workspace_id=ws, form_id=pk).order_by("-created_at")
        if request.query_params.get("status"):
            qs = qs.filter(status=request.query_params["status"])
        qs = qs[:300]
        return Response({"results": FormSubmissionSerializer(qs, many=True).data,
                         "count": len(qs)})


class FormSubmissionDetailView(APIView):
    def _get(self, request, pk, sub_id) -> FormSubmission:
        sub = FormSubmission.objects.filter(
            id=sub_id, form_id=pk, workspace_id=_ws(request)).first()
        if sub is None:
            raise NotFound("Submission not found")
        return sub

    def get(self, request, pk, sub_id):
        _member(request)
        return Response(FormSubmissionSerializer(self._get(request, pk, sub_id)).data)


class FormSubmissionApproveView(APIView):
    def post(self, request, pk, sub_id):
        member = _require(request, _WRITE_ROLES)
        sub = FormSubmission.objects.filter(
            id=sub_id, form_id=pk, workspace_id=_ws(request)).first()
        if sub is None:
            raise NotFound("Submission not found")
        sub = PublicFormService.approve_submission(sub.id, member.user_id)
        return Response(FormSubmissionSerializer(sub).data)


class FormSubmissionRejectView(APIView):
    def post(self, request, pk, sub_id):
        member = _require(request, _WRITE_ROLES)
        sub = FormSubmission.objects.filter(
            id=sub_id, form_id=pk, workspace_id=_ws(request)).first()
        if sub is None:
            raise NotFound("Submission not found")
        reason = str(request.data.get("reason", "") or "")
        sub = PublicFormService.reject_submission(sub.id, member.user_id, reason)
        return Response(FormSubmissionSerializer(sub).data)
