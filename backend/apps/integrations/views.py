"""
Integrations REST API (PROJECT_HANDBOOK.md §30.3 / §30.4).

Workspace-scoped CRUD for webhook subscriptions, HTTP connectors, OAuth apps and
inbound webhooks, plus the **public, unauthenticated inbound webhook endpoint**
(token-hash lookup, rate-limited, raw body never stored). Writes are role-gated.
"""
import hashlib
import secrets
import uuid

from django.core.cache import cache
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.eventstore.events import DomainEventData, DomainEventFactory

from .models import (
    HTTPConnector,
    InboundWebhook,
    OAuthApp,
    WebhookDelivery,
    WebhookSubscription,
)
from .serializers import (
    HTTPConnectorSerializer,
    InboundWebhookSerializer,
    OAuthAppSerializer,
    WebhookDeliverySerializer,
    WebhookSubscriptionSerializer,
)
from .services import HTTPConnectorService

_WRITE_ROLES = {"owner", "admin", "member"}
INBOUND_RATE_LIMIT = 60  # requests / minute / token


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


def _require_write(request):
    m = _member(request)
    if getattr(m, "role", "") not in _WRITE_ROLES:
        raise PermissionDenied("Insufficient role for this action.")
    return m


def _new_token():
    token = secrets.token_urlsafe(32)
    return token, hashlib.sha256(token.encode()).hexdigest()


# ── webhook subscriptions ─────────────────────────────────────────────────────
class SubscriptionListCreateView(APIView):
    def get(self, request):
        _member(request)
        qs = WebhookSubscription.objects.filter(
            workspace_id=_ws(request), deleted_at__isnull=True)
        return Response({"results": WebhookSubscriptionSerializer(qs, many=True).data,
                         "count": qs.count()})

    def post(self, request):
        _require_write(request)
        ser = WebhookSubscriptionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = ser.save(workspace_id=_ws(request))
        return Response(WebhookSubscriptionSerializer(obj).data, status=status.HTTP_201_CREATED)


class SubscriptionDetailView(APIView):
    def _get(self, request, pk):
        obj = WebhookSubscription.objects.filter(id=pk, workspace_id=_ws(request)).first()
        if obj is None:
            raise NotFound("Subscription not found")
        return obj

    def get(self, request, pk):
        _member(request)
        return Response(WebhookSubscriptionSerializer(self._get(request, pk)).data)

    def patch(self, request, pk):
        _require_write(request)
        obj = self._get(request, pk)
        ser = WebhookSubscriptionSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(WebhookSubscriptionSerializer(obj).data)

    def delete(self, request, pk):
        member = _require_write(request)
        self._get(request, pk).soft_delete(member.user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SubscriptionTestView(APIView):
    def post(self, request, pk):
        _require_write(request)
        sub = WebhookSubscription.objects.filter(id=pk, workspace_id=_ws(request)).first()
        if sub is None:
            raise NotFound("Subscription not found")
        from .tasks import deliver_webhook
        deliver_webhook(str(sub.id), "webhook.test", {"test": True})
        latest = WebhookDelivery.objects.filter(subscription_id=sub.id).order_by("-id").first()
        return Response({"delivered": latest is not None,
                         "delivery": WebhookDeliverySerializer(latest).data if latest else None})


class SubscriptionDeliveriesView(APIView):
    def get(self, request, pk):
        _member(request)
        qs = WebhookDelivery.objects.filter(
            subscription_id=pk, workspace_id=_ws(request)).order_by("-id")[:100]
        return Response({"results": WebhookDeliverySerializer(qs, many=True).data, "count": len(qs)})


class SubscriptionToggleView(APIView):
    enable = True

    def post(self, request, pk):
        _require_write(request)
        sub = WebhookSubscription.objects.filter(id=pk, workspace_id=_ws(request)).first()
        if sub is None:
            raise NotFound("Subscription not found")
        sub.status = "active" if self.enable else "paused"
        if self.enable:
            sub.consecutive_failures = 0
        sub.save(update_fields=["status", "consecutive_failures"])
        return Response(WebhookSubscriptionSerializer(sub).data)


class SubscriptionEnableView(SubscriptionToggleView):
    enable = True


class SubscriptionDisableView(SubscriptionToggleView):
    enable = False


# ── HTTP connectors ───────────────────────────────────────────────────────────
class ConnectorListCreateView(APIView):
    def get(self, request):
        _member(request)
        qs = HTTPConnector.objects.filter(workspace_id=_ws(request), deleted_at__isnull=True)
        return Response({"results": HTTPConnectorSerializer(qs, many=True).data, "count": qs.count()})

    def post(self, request):
        _require_write(request)
        ser = HTTPConnectorSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ws = _ws(request)
        if HTTPConnector.objects.filter(workspace_id=ws, slug=ser.validated_data["slug"]).exists():
            raise ValidationError("A connector with this slug already exists")
        obj = ser.save(workspace_id=ws)
        return Response(HTTPConnectorSerializer(obj).data, status=status.HTTP_201_CREATED)


class ConnectorDetailView(APIView):
    def _get(self, request, pk):
        obj = HTTPConnector.objects.filter(id=pk, workspace_id=_ws(request)).first()
        if obj is None:
            raise NotFound("Connector not found")
        return obj

    def get(self, request, pk):
        _member(request)
        return Response(HTTPConnectorSerializer(self._get(request, pk)).data)

    def patch(self, request, pk):
        _require_write(request)
        obj = self._get(request, pk)
        ser = HTTPConnectorSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(HTTPConnectorSerializer(obj).data)

    def delete(self, request, pk):
        member = _require_write(request)
        self._get(request, pk).soft_delete(member.user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ConnectorTestView(APIView):
    def post(self, request, pk):
        _require_write(request)
        connector = HTTPConnector.objects.filter(id=pk, workspace_id=_ws(request)).first()
        if connector is None:
            raise NotFound("Connector not found")
        result = HTTPConnectorService.request(
            connector, request.data.get("method", "GET"), request.data.get("path", ""))
        return Response({"status": result.get("status")})


# ── OAuth apps ────────────────────────────────────────────────────────────────
class OAuthAppListCreateView(APIView):
    def get(self, request):
        _member(request)
        qs = OAuthApp.objects.filter(workspace_id=_ws(request), deleted_at__isnull=True)
        return Response({"results": OAuthAppSerializer(qs, many=True).data, "count": qs.count()})

    def post(self, request):
        _require_write(request)
        ser = OAuthAppSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = ser.save(workspace_id=_ws(request))
        return Response(OAuthAppSerializer(obj).data, status=status.HTTP_201_CREATED)


class OAuthAppDetailView(APIView):
    def _get(self, request, pk):
        obj = OAuthApp.objects.filter(id=pk, workspace_id=_ws(request)).first()
        if obj is None:
            raise NotFound("OAuth app not found")
        return obj

    def get(self, request, pk):
        _member(request)
        return Response(OAuthAppSerializer(self._get(request, pk)).data)

    def patch(self, request, pk):
        _require_write(request)
        obj = self._get(request, pk)
        ser = OAuthAppSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(OAuthAppSerializer(obj).data)

    def delete(self, request, pk):
        member = _require_write(request)
        self._get(request, pk).soft_delete(member.user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── inbound webhooks ──────────────────────────────────────────────────────────
class InboundListCreateView(APIView):
    def get(self, request):
        _member(request)
        qs = InboundWebhook.objects.filter(workspace_id=_ws(request), deleted_at__isnull=True)
        return Response({"results": InboundWebhookSerializer(qs, many=True).data, "count": qs.count()})

    def post(self, request):
        _require_write(request)
        ser = InboundWebhookSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ws = _ws(request)
        if InboundWebhook.objects.filter(workspace_id=ws, slug=ser.validated_data["slug"]).exists():
            raise ValidationError("An inbound webhook with this slug already exists")
        token, token_hash = _new_token()
        obj = ser.save(workspace_id=ws, token_hash=token_hash)
        data = InboundWebhookSerializer(obj).data
        data["token"] = token  # shown once
        data["url"] = f"/api/v1/webhooks/inbound/{token}/"
        return Response(data, status=status.HTTP_201_CREATED)


class InboundDetailView(APIView):
    def _get(self, request, pk):
        obj = InboundWebhook.objects.filter(id=pk, workspace_id=_ws(request)).first()
        if obj is None:
            raise NotFound("Inbound webhook not found")
        return obj

    def get(self, request, pk):
        _member(request)
        return Response(InboundWebhookSerializer(self._get(request, pk)).data)

    def patch(self, request, pk):
        _require_write(request)
        obj = self._get(request, pk)
        ser = InboundWebhookSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(InboundWebhookSerializer(obj).data)

    def delete(self, request, pk):
        member = _require_write(request)
        self._get(request, pk).soft_delete(member.user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class InboundRotateTokenView(APIView):
    def post(self, request, pk):
        _require_write(request)
        obj = InboundWebhook.objects.filter(id=pk, workspace_id=_ws(request)).first()
        if obj is None:
            raise NotFound("Inbound webhook not found")
        token, token_hash = _new_token()
        obj.token_hash = token_hash
        obj.save(update_fields=["token_hash"])
        return Response({"token": token, "url": f"/api/v1/webhooks/inbound/{token}/"})


# ── public inbound endpoint ───────────────────────────────────────────────────
class InboundWebhookReceiveView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, token):
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        hook = InboundWebhook.objects.filter(token_hash=token_hash, is_active=True).first()
        if hook is None:
            raise NotFound("Unknown webhook")
        # rate limit: 60/min per token
        bucket = f"inbound_wh:{token_hash}"
        count = cache.get(bucket, 0)
        if count >= INBOUND_RATE_LIMIT:
            return Response({"detail": "rate limit exceeded"}, status=429)
        cache.set(bucket, count + 1, timeout=60)

        from django.utils import timezone
        body_hash = hashlib.sha256(
            request.body or b"").hexdigest()  # raw body never stored
        InboundWebhook.objects.filter(id=hook.id).update(
            call_count=hook.call_count + 1, last_called_at=timezone.now())
        DomainEventFactory.persist_one(DomainEventData(
            event_type="inbound_webhook.received", workspace_id=hook.workspace_id,
            aggregate_type="inbound_webhook", aggregate_id=hook.id, version=hook.call_count + 1,
            payload={"slug": hook.slug, "body_hash": body_hash}, actor_id=uuid.UUID(int=0)))
        if hook.workflow_id:
            try:
                from apps.workflows.services import WorkflowService
                WorkflowService.trigger_workflow(
                    workflow_id=hook.workflow_id, context={"webhook": request.data},
                    workspace_id=hook.workspace_id, trigger_type="webhook")
            except Exception:  # noqa: BLE001 — never block the inbound 200
                pass
        return Response({"received": True})
