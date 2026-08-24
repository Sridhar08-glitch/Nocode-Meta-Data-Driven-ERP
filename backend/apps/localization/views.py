"""
Localization REST API (PROJECT_HANDBOOK.md §32.3) at /api/v1/localization/.

Workspace-scoped locale settings, translations (system defaults merged with
workspace overrides), and entity/field label translations. Writes are role-gated.
"""
import uuid

from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import EntityLabelTranslation, TranslationKey
from .serializers import (
    EntityLabelTranslationSerializer,
    TranslationKeySerializer,
    WorkspaceLocaleSerializer,
)
from .services import LocalizationError, LocalizationService

_WRITE_ROLES = {"owner", "admin", "member"}
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


def _require(request, roles):
    m = _member(request)
    if getattr(m, "role", "") not in roles:
        raise PermissionDenied("Insufficient role for this action.")
    return m


class LocaleView(APIView):
    def get(self, request):
        _member(request)
        return Response(WorkspaceLocaleSerializer(
            LocalizationService.get_locale(_ws(request))).data)

    def patch(self, request):
        _require(request, _ADMIN_ROLES)
        try:
            obj = LocalizationService.set_locale(_ws(request), request.data)
        except LocalizationError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(WorkspaceLocaleSerializer(obj).data)


class TranslationsView(APIView):
    def get(self, request):
        _member(request)
        locale = request.query_params.get("locale")
        if not locale:
            raise ValidationError("locale query param is required")
        translations = LocalizationService.get_translations(
            _ws(request), locale, request.query_params.get("namespace"))
        return Response({"locale": locale, "translations": translations})


class TranslationOverrideView(APIView):
    def patch(self, request, key_id):
        member = _require(request, _WRITE_ROLES)
        locale = request.data.get("locale")
        if not locale or "value" not in request.data:
            raise ValidationError("locale and value are required")
        try:
            LocalizationService.set_override(_ws(request), key_id, locale,
                                             request.data["value"], member.user_id)
        except LocalizationError as exc:
            raise ValidationError(str(exc)) from exc
        return Response({"updated": True})

    def delete(self, request, key_id):
        _require(request, _WRITE_ROLES)
        locale = request.query_params.get("locale") or request.data.get("locale")
        if not locale:
            raise ValidationError("locale is required")
        removed = LocalizationService.remove_override(_ws(request), key_id, locale)
        return Response({"removed": removed})


class EntityLabelListCreateView(APIView):
    def get(self, request):
        _member(request)
        qs = LocalizationService.list_entity_labels(
            _ws(request), request.query_params.get("locale"))
        return Response({"results": EntityLabelTranslationSerializer(qs, many=True).data,
                         "count": qs.count()})

    def post(self, request):
        _require(request, _WRITE_ROLES)
        d = request.data
        try:
            obj = LocalizationService.set_entity_label(
                _ws(request), entity_id=d.get("entity_id"), field_id=d.get("field_id"),
                locale=d.get("locale"), singular=d.get("singular", ""),
                plural=d.get("plural", ""))
        except LocalizationError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(EntityLabelTranslationSerializer(obj).data,
                        status=status.HTTP_201_CREATED)


class EntityLabelDetailView(APIView):
    def _get(self, request, pk):
        obj = EntityLabelTranslation.objects.filter(id=pk, workspace_id=_ws(request)).first()
        if obj is None:
            raise NotFound("Entity label not found")
        return obj

    def patch(self, request, pk):
        _require(request, _WRITE_ROLES)
        obj = self._get(request, pk)
        for field in ("singular", "plural"):
            if field in request.data:
                setattr(obj, field, request.data[field])
        obj.save()
        return Response(EntityLabelTranslationSerializer(obj).data)

    def delete(self, request, pk):
        _require(request, _WRITE_ROLES)
        self._get(request, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class KeyListView(APIView):
    def get(self, request):
        _member(request)
        qs = TranslationKey.objects.all()
        if request.query_params.get("namespace"):
            qs = qs.filter(namespace=request.query_params["namespace"])
        qs = qs.order_by("namespace", "key")
        return Response({"results": TranslationKeySerializer(qs, many=True).data,
                         "count": qs.count()})
