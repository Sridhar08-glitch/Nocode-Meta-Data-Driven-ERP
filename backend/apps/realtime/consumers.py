"""
Realtime WebSocket consumers (Phase 1.30).

Live record / workflow / dashboard streams + presence, over Django Channels. Each
connection is JWT-authenticated by ``apps.accounts.middleware.JWTAuthMiddleware``
(``?token=``) and must name a workspace it belongs to (``?workspace=<slug>``); the
consumer verifies active membership before joining the workspace-scoped group, so a
client can only ever subscribe to its own tenant's stream.

Close codes: 4401 unauthenticated · 4403 not a member / unknown workspace.
"""
from __future__ import annotations

import json
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from . import broadcast


@database_sync_to_async
def _resolve_workspace(user_id, slug):
    if not user_id or not slug:
        return None
    from apps.tenancy.models import Workspace, WorkspaceMember
    ws = Workspace.objects.filter(slug=slug, is_active=True).first()
    if ws is None:
        return None
    is_member = WorkspaceMember.objects.filter(
        workspace=ws, user_id=user_id, status="active").exists()
    return ws.id if is_member else None


class _BaseConsumer(AsyncWebsocketConsumer):
    """Auth + workspace-membership gate, then join one workspace-scoped group."""

    def group_name(self) -> str:  # overridden per stream
        raise NotImplementedError

    async def connect(self):
        self.user_id = self.scope.get("user_id")
        if not self.user_id:
            await self.close(code=4401)
            return
        qs = parse_qs((self.scope.get("query_string") or b"").decode())
        slug = (qs.get("workspace") or [None])[0]
        self.workspace_id = await _resolve_workspace(self.user_id, slug)
        if self.workspace_id is None:
            await self.close(code=4403)
            return
        self.group = self.group_name()
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
        await self.on_connected()

    async def on_connected(self):
        return

    async def disconnect(self, code):
        group = getattr(self, "group", None)
        if group:
            await self.channel_layer.group_discard(group, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        return  # push-only by default


class RecordStreamConsumer(_BaseConsumer):
    async def connect(self):
        self.entity_slug = (self.scope.get("url_route", {}) or {}).get(
            "kwargs", {}).get("entity_slug")
        await super().connect()

    def group_name(self):
        return broadcast.group_records(self.workspace_id)

    async def record_event(self, event):
        ev = event["event"]
        # entity-scoped subscribers only see their entity's events
        if self.entity_slug and ev.get("entity_slug") != self.entity_slug:
            return
        await self.send(text_data=json.dumps(ev))


class WorkflowStreamConsumer(_BaseConsumer):
    def group_name(self):
        return broadcast.group_workflows(self.workspace_id)

    async def workflow_event(self, event):
        await self.send(text_data=json.dumps(event["event"]))


class DashboardStreamConsumer(_BaseConsumer):
    def group_name(self):
        return broadcast.group_dashboards(self.workspace_id)

    async def dashboard_event(self, event):
        await self.send(text_data=json.dumps(event["event"]))


class PresenceConsumer(_BaseConsumer):
    def group_name(self):
        return broadcast.group_presence(self.workspace_id)

    async def on_connected(self):
        await self._announce("join")

    async def disconnect(self, code):
        if getattr(self, "group", None):
            await self._announce("leave")
        await super().disconnect(code)

    async def receive(self, text_data=None, bytes_data=None):
        # any client message is treated as a heartbeat keep-alive
        await self._announce("heartbeat")

    async def _announce(self, action):
        await self.channel_layer.group_send(self.group, {
            "type": "presence.event",
            "event": {"action": action, "user_id": str(self.user_id)},
        })

    async def presence_event(self, event):
        await self.send(text_data=json.dumps(event["event"]))
