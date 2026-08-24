"""
WebSocket consumer for real-time in-app notifications (PROJECT_HANDBOOK.md §22.4).

Authenticated via the JWT Channels middleware (``?token=``). Each connected user
joins the group ``user_{user_id}_notifications``; the in-app delivery task pushes
``notification.message`` events to that group.
"""
from __future__ import annotations

import json

from channels.generic.websocket import AsyncWebsocketConsumer


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user_id = self.scope.get("user_id")
        if not self.user_id:
            await self.close(code=4401)   # unauthenticated
            return
        self.group = f"user_{self.user_id}_notifications"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        group = getattr(self, "group", None)
        if group:
            await self.channel_layer.group_discard(group, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # Server-push only; ignore any client payloads.
        return

    async def notification_message(self, event):
        await self.send(text_data=json.dumps(event["notification"]))
