"""
Channels (WebSocket) JWT auth middleware.

Authenticates a WebSocket connection from a ``?token=<access JWT>`` query param,
decoding it with the same RS256 verifier as the HTTP auth path
(:func:`apps.accounts.tokens.decode_token`). On success ``scope["user"]`` and
``scope["user_id"]`` are populated; otherwise the connection stays anonymous and
the consumer is responsible for rejecting it.
"""
from __future__ import annotations

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser


@database_sync_to_async
def _resolve_user(token: str):
    from apps.accounts import tokens
    from apps.accounts.models import User
    try:
        payload = tokens.decode_token(token, expected_type="access")
    except Exception:  # noqa: BLE001 — any decode/verify failure → anonymous
        return None
    user_id = payload.get("user_id")
    if not user_id:
        return None
    return User.objects.filter(id=user_id, is_active=True).first()


class JWTAuthMiddleware:
    """ASGI middleware that attaches an authenticated user to the WS scope."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        scope["user"] = AnonymousUser()
        scope["user_id"] = None
        qs = parse_qs((scope.get("query_string") or b"").decode())
        token = (qs.get("token") or [None])[0]
        if token:
            user = await _resolve_user(token)
            if user is not None:
                scope["user"] = user
                scope["user_id"] = str(user.id)
        return await self.inner(scope, receive, send)


def JWTAuthMiddlewareStack(inner):  # noqa: N802 — Channels stack factory convention
    return JWTAuthMiddleware(inner)
