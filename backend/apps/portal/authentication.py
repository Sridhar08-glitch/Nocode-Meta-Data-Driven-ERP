"""
PortalJWTAuthentication — authenticates portal users in their own realm.

Only accepts ``token_type == "portal_access"`` tokens and resolves them to a
``PortalUser`` (never an accounts.User). Workspace-realm Bearer tokens are
ignored here, and portal tokens are rejected by the workspace authenticator
because their ``token_type`` differs.
"""
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .tokens import decode_portal_token


class PortalJWTAuthentication(BaseAuthentication):
    AUTH_HEADER_PREFIX = "Bearer"

    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith(f"{self.AUTH_HEADER_PREFIX} "):
            return None
        raw_token = auth_header.split(" ", 1)[1]
        payload = decode_portal_token(raw_token)
        if payload.get("token_type") != "portal_access":
            raise AuthenticationFailed("Expected a portal access token.")

        from .models import PortalUser
        try:
            portal_user = PortalUser.objects.get(pk=payload["portal_user_id"], is_active=True)
        except (PortalUser.DoesNotExist, KeyError) as exc:
            raise AuthenticationFailed("Portal user not found or inactive.") from exc
        return (portal_user, payload)

    def authenticate_header(self, request):
        return self.AUTH_HEADER_PREFIX
