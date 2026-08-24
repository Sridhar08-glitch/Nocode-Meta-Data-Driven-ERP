"""
DRF authenticators (Phase 1.5):

- ``NexusJWTAuthentication`` — RS256 Bearer access tokens.
- ``ApiKeyAuthentication`` — ``X-API-Key: nxk_<prefix>.<secret>`` keys.
"""
import hmac

import jwt
from django.conf import settings
from django.utils import timezone
from jwt.exceptions import InvalidTokenError
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


class NexusJWTAuthentication(BaseAuthentication):
    """
    Authenticates requests via Bearer RS256 JWT access tokens.
    Returns (user, token_payload) on success.
    """
    AUTH_HEADER_PREFIX = "Bearer"

    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith(f"{self.AUTH_HEADER_PREFIX} "):
            return None

        raw_token = auth_header.split(" ", 1)[1]
        return self._decode_and_authenticate(raw_token)

    def _decode_and_authenticate(self, raw_token: str):
        try:
            payload = jwt.decode(
                raw_token,
                settings.SIMPLE_JWT["VERIFYING_KEY"],
                algorithms=[settings.SIMPLE_JWT["ALGORITHM"]],
                options={"require": ["exp", "iat", "jti", "user_id", "token_type"]},
            )
        except InvalidTokenError as exc:
            raise AuthenticationFailed(f"Invalid token: {exc}") from exc

        if payload.get("token_type") != "access":
            raise AuthenticationFailed("Expected an access token.")

        from apps.accounts.models import User
        try:
            user = User.objects.get(pk=payload["user_id"], is_active=True)
        except User.DoesNotExist:
            raise AuthenticationFailed("User not found or inactive.") from None

        return (user, payload)

    def authenticate_header(self, request):
        return self.AUTH_HEADER_PREFIX


class ApiKeyAuthentication(BaseAuthentication):
    """
    Authenticates via the ``X-API-Key`` header.

    Key format: ``nxk_<prefix>.<secret>``. We look the key up by its visible
    prefix, then verify the SHA-256 hash of the *full* key in constant time.
    """

    def authenticate(self, request):
        raw_key = request.META.get("HTTP_X_API_KEY", "")
        if not raw_key:
            return None
        if "." not in raw_key:
            raise AuthenticationFailed("Malformed API key.")

        from apps.accounts.crypto import hash_token
        from apps.accounts.models import ApiKey

        prefix = raw_key.split(".", 1)[0]
        try:
            api_key = ApiKey.objects.select_related("user").get(key_prefix=prefix, is_active=True)
        except ApiKey.DoesNotExist as exc:
            raise AuthenticationFailed("Invalid API key.") from exc

        if not hmac.compare_digest(api_key.key_hash, hash_token(raw_key)):
            raise AuthenticationFailed("Invalid API key.")
        if api_key.expires_at is not None and api_key.expires_at <= timezone.now():
            raise AuthenticationFailed("API key has expired.")
        if not api_key.user.is_active:
            raise AuthenticationFailed("User is inactive.")

        ApiKey.objects.filter(pk=api_key.pk).update(last_used_at=timezone.now())
        return (api_key.user, api_key)

    def authenticate_header(self, request):
        return "X-API-Key"
