"""
Notifications REST API (PROJECT_HANDBOOK.md §22.5).

Recipient endpoints act on the authenticated user's own notifications (scoped by
``recipient_id == user.id`` within the active workspace). Template endpoints are
workspace-scoped CRUD, gated to owner/admin/member for writes.
"""
import uuid

from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification, NotificationPreference, NotificationTemplate
from .serializers import (
    NotificationPreferenceSerializer,
    NotificationSerializer,
    NotificationTemplateSerializer,
)
from .services import NotificationService

_WRITE_ROLES = {"owner", "admin", "member"}


def _ws(request) -> uuid.UUID:
    ws = getattr(request, "workspace_id", None)
    if not ws:
        raise PermissionDenied("No active workspace. Send the X-Workspace-Slug header.")
    return ws if isinstance(ws, uuid.UUID) else uuid.UUID(str(ws))


def _user_id(request):
    uid = getattr(request.user, "id", None)
    if uid is None:
        raise PermissionDenied("Authentication required.")
    return uid


def _require_write(request):
    m = getattr(request, "workspace_member", None)
    if m is None or getattr(m, "role", "") not in _WRITE_ROLES:
        raise PermissionDenied("Insufficient role for this action.")
    return m


class NotificationListView(APIView):
    def get(self, request):
        ws, uid = _ws(request), _user_id(request)
        qs = Notification.objects.filter(workspace_id=ws, recipient_id=uid)
        if request.query_params.get("unread") in ("1", "true", "True"):
            qs = qs.filter(read_at__isnull=True)
        if request.query_params.get("channel"):
            qs = qs.filter(channel=request.query_params["channel"])
        if request.query_params.get("date_from"):
            qs = qs.filter(created_at__gte=request.query_params["date_from"])
        qs = qs.order_by("-created_at")[:200]
        return Response({"results": NotificationSerializer(qs, many=True).data,
                         "count": len(qs)})


class NotificationReadView(APIView):
    def post(self, request, pk):
        ws, uid = _ws(request), _user_id(request)
        n = NotificationService.mark_read(pk, uid)
        if n is None or n.workspace_id != ws:
            raise NotFound("Notification not found")
        return Response(NotificationSerializer(n).data)


class NotificationReadAllView(APIView):
    def post(self, request):
        count = NotificationService.mark_all_read(_user_id(request), _ws(request))
        return Response({"updated": count})


class NotificationUnreadCountView(APIView):
    def get(self, request):
        count = NotificationService.get_unread_count(_user_id(request), _ws(request))
        return Response({"count": count})


class TemplateListCreateView(APIView):
    def get(self, request):
        qs = NotificationTemplate.objects.filter(workspace_id=_ws(request)).order_by("slug")
        return Response({"results": NotificationTemplateSerializer(qs, many=True).data,
                         "count": qs.count()})

    def post(self, request):
        _require_write(request)
        ser = NotificationTemplateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ws = _ws(request)
        if NotificationTemplate.objects.filter(
                workspace_id=ws, slug=ser.validated_data["slug"],
                channel=ser.validated_data["channel"]).exists():
            raise ValidationError("A template with this slug+channel already exists")
        tpl = ser.save(workspace_id=ws)
        return Response(NotificationTemplateSerializer(tpl).data,
                        status=status.HTTP_201_CREATED)


class TemplateDetailView(APIView):
    def _get(self, request, pk):
        tpl = NotificationTemplate.objects.filter(id=pk, workspace_id=_ws(request)).first()
        if tpl is None:
            raise NotFound("Template not found")
        return tpl

    def get(self, request, pk):
        return Response(NotificationTemplateSerializer(self._get(request, pk)).data)

    def patch(self, request, pk):
        _require_write(request)
        tpl = self._get(request, pk)
        ser = NotificationTemplateSerializer(tpl, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(NotificationTemplateSerializer(tpl).data)

    def delete(self, request, pk):
        _require_write(request)
        self._get(request, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TemplateTestView(APIView):
    """Send a test notification rendered from this template to the caller."""
    def post(self, request, pk):
        ws, uid = _ws(request), _user_id(request)
        tpl = NotificationTemplate.objects.filter(id=pk, workspace_id=ws).first()
        if tpl is None:
            raise NotFound("Template not found")
        context = request.data.get("context") if isinstance(request.data, dict) else None
        notifications = NotificationService.send(
            recipient_id=uid, recipient_type="member", template_slug=tpl.slug,
            context=context or {"actor_name": "Test"}, workspace_id=ws,
            channels=[tpl.channel])
        return Response({"sent": len(notifications),
                         "notifications": NotificationSerializer(notifications, many=True).data},
                        status=status.HTTP_201_CREATED)


class PreferenceView(APIView):
    """The caller's own per-event-type/per-channel notification preferences.

    Preferences are keyed by ``member_id == user.id`` to match the send-time lookup
    (``NotificationService`` filters ``member_id=recipient_id`` where recipient is the user id).
    """

    def get(self, request):
        ws, uid = _ws(request), _user_id(request)
        qs = NotificationPreference.objects.filter(workspace_id=ws, member_id=uid).order_by(
            "event_type", "channel")
        return Response({"results": NotificationPreferenceSerializer(qs, many=True).data,
                         "count": len(qs)})

    def put(self, request):
        """Upsert a single preference keyed on (event_type, channel)."""
        ws, uid = _ws(request), _user_id(request)
        data = request.data if isinstance(request.data, dict) else {}
        event_type = (data.get("event_type") or "").strip()
        channel = (data.get("channel") or "").strip()
        if not event_type or not channel:
            raise ValidationError("event_type and channel are required.")
        enabled = bool(data.get("enabled", True))
        pref, _ = NotificationPreference.objects.update_or_create(
            workspace_id=ws, member_id=uid, event_type=event_type, channel=channel,
            defaults={"enabled": enabled})
        return Response(NotificationPreferenceSerializer(pref).data)
