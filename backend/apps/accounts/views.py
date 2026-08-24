"""
Authentication API views (Phase 1.5).

All endpoints live under /api/v1/auth/ and operate on the existing
``accounts`` identity models — no duplicate identity system is introduced.
"""
import base64
import hashlib
import secrets
import urllib.parse

import pyotp
import requests
from django.conf import settings
from django.contrib.auth import authenticate
from django.core import signing
from django.core.cache import cache
from django.db import transaction
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services, sessions, tokens, webauthn_service
from .crypto import decrypt_secret, encrypt_secret, hash_token
from .models import OAuthAccount, User
from .serializers import (
    ChangeEmailSerializer,
    ChangePasswordSerializer,
    LoginSerializer,
    MfaConfirmSerializer,
    MfaDisableSerializer,
    MfaLoginSerializer,
    PasskeyAuthenticateBeginSerializer,
    PasskeyAuthenticateCompleteSerializer,
    PasskeyRegisterCompleteSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RefreshSerializer,
    RegisterSerializer,
    ResendVerificationSerializer,
    RevokeAllSessionsSerializer,
    SessionSerializer,
    VerifyEmailSerializer,
)

WEBAUTHN_CHALLENGE_TTL = 300  # seconds


def _reg_challenge_key(user_id):
    return f"webauthn:reg:{user_id}"


def _auth_challenge_key(user_id):
    return f"webauthn:auth:{user_id}"

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
OAUTH_STATE_SALT = "nexus.google.oauth"

MS_USERINFO_URL = "https://graph.microsoft.com/oidc/userinfo"
MS_STATE_SALT = "nexus.microsoft.oauth"


def _ms_authorize_url():
    return f"https://login.microsoftonline.com/{settings.MICROSOFT_OAUTH_TENANT}/oauth2/v2.0/authorize"


def _ms_token_url():
    return f"https://login.microsoftonline.com/{settings.MICROSOFT_OAUTH_TENANT}/oauth2/v2.0/token"


def _lockout_key(email, ip):
    return f"login_lockout:{(email or '').lower()}:{ip or '-'}"


def _rate_limited(request):
    return getattr(request, "limited", False)


def _too_many():
    return Response({"detail": "Too many requests. Try again later."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS)


def _email_key(group, request):
    return (request.data.get("email") or "").lower() or "anon"


def _mfa_user_key(group, request):
    try:
        return tokens.decode_token(request.data.get("mfa_token", ""))["user_id"]
    except Exception:  # noqa: BLE001 — fall back to a shared bucket on bad token
        return "anon"


def _token_response(user, request, workspace_id=None, *, mfa_used=False, http_status=status.HTTP_200_OK):
    access, refresh, _ = tokens.issue_token_pair(
        user,
        workspace_id,
        user_agent=services.get_user_agent(request),
        ip=services.get_client_ip(request),
    )
    return Response(
        {
            "access": access,
            "refresh": refresh,
            "user": {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "mfa_enabled": user.mfa_enabled,
            },
        },
        status=http_status,
    )


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        s = RegisterSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        email = s.validated_data["email"].lower()
        if User.objects.filter(email=email).exists():
            # Do not reveal which emails exist beyond a generic conflict.
            return Response({"detail": "Registration could not be completed."},
                            status=status.HTTP_409_CONFLICT)
        user = User.objects.create_user(
            email=email,
            password=s.validated_data["password"],
            full_name=s.validated_data.get("full_name", ""),
            is_verified=False,
        )
        user.password_changed_at = timezone.now()
        user.save(update_fields=["password_changed_at"])
        raw, _ = services.create_email_verification_token(user)
        services.send_verification_email(user, raw)
        return Response({"detail": "Verification email sent"}, status=status.HTTP_201_CREATED)


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        s = VerifyEmailSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        obj = services.consume_email_verification_token(s.validated_data["token"])
        if obj is None:
            return Response({"detail": "Invalid or expired token."},
                            status=status.HTTP_400_BAD_REQUEST)
        user = obj.user
        # Email-change verification: the token carries the new address.
        if obj.new_email:
            if User.objects.filter(email=obj.new_email).exclude(id=user.id).exists():
                return Response({"detail": "That email address is no longer available."},
                                status=status.HTTP_400_BAD_REQUEST)
            with transaction.atomic():
                user.email = obj.new_email
                user.is_verified = True
                user.save(update_fields=["email", "is_verified"])
                obj.is_used = True
                obj.save(update_fields=["is_used"])
                # Force re-auth everywhere after an identity change.
                tokens.revoke_all_for_user(user, reason="email_change")
            return Response({"detail": "Email address updated. Please sign in again."})
        # Initial account verification.
        with transaction.atomic():
            user.is_verified = True
            user.save(update_fields=["is_verified"])
            obj.is_used = True
            obj.save(update_fields=["is_used"])
        return _token_response(user, request)


@method_decorator(ratelimit(key="ip", rate="5/m", method="POST", block=False), name="post")
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if _rate_limited(request):
            return _too_many()
        s = LoginSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        email = s.validated_data["email"].lower()
        password = s.validated_data["password"]

        lock_on = getattr(settings, "LOGIN_LOCKOUT_ENABLED", True)
        lkey = _lockout_key(email, services.get_client_ip(request))
        if lock_on and cache.get(lkey, 0) >= settings.LOGIN_LOCKOUT_THRESHOLD:
            services.record_login(request, email=email, success=False, failure_reason="locked_out")
            return Response(
                {"detail": "Account temporarily locked after repeated failed attempts."},
                status=status.HTTP_429_TOO_MANY_REQUESTS)

        user = authenticate(request, username=email, password=password)
        if user is None:
            if lock_on:
                cache.set(lkey, cache.get(lkey, 0) + 1, settings.LOGIN_LOCKOUT_SECONDS)
            services.record_login(request, email=email, success=False,
                                  failure_reason="invalid_credentials")
            return Response({"detail": "Invalid credentials."},
                            status=status.HTTP_401_UNAUTHORIZED)
        if lock_on:
            cache.delete(lkey)  # valid password clears the failure counter
        if not user.is_active:
            services.record_login(request, email=email, success=False, user=user,
                                  failure_reason="inactive")
            return Response({"detail": "Account is inactive."},
                            status=status.HTTP_403_FORBIDDEN)
        if not user.is_verified:
            services.record_login(request, email=email, success=False, user=user,
                                  failure_reason="unverified")
            return Response({"detail": "Email not verified."},
                            status=status.HTTP_403_FORBIDDEN)

        if user.mfa_enabled:
            services.record_login(request, email=email, success=False, user=user,
                                  failure_reason="mfa_required")
            return Response(
                {"mfa_required": True, "mfa_token": tokens.issue_mfa_challenge_token(user)},
                status=status.HTTP_200_OK,
            )

        user.last_login_at = timezone.now()
        user.last_login_ip = services.get_client_ip(request)
        user.save(update_fields=["last_login_at", "last_login_ip"])
        services.record_login(request, email=email, success=True, user=user)
        return _token_response(user, request)


@method_decorator(ratelimit(key=_mfa_user_key, rate="5/10m", method="POST", block=False), name="post")
class MfaLoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if _rate_limited(request):
            return _too_many()
        s = MfaLoginSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            payload = tokens.decode_token(s.validated_data["mfa_token"], expected_type="mfa_challenge")
        except AuthenticationFailed as exc:
            return Response({"detail": str(exc.detail)}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            user = User.objects.get(pk=payload["user_id"], is_active=True)
        except User.DoesNotExist:
            return Response({"detail": "Invalid challenge."}, status=status.HTTP_401_UNAUTHORIZED)
        if not user.mfa_enabled or not user.mfa_secret:
            return Response({"detail": "MFA not enabled."}, status=status.HTTP_400_BAD_REQUEST)

        code = s.validated_data["code"]
        if not _verify_totp_or_backup(user, code):
            services.record_login(request, email=user.email, success=False, user=user,
                                  failure_reason="mfa_invalid", mfa_used=True)
            return Response({"detail": "Invalid MFA code."}, status=status.HTTP_401_UNAUTHORIZED)

        user.last_login_at = timezone.now()
        user.last_login_ip = services.get_client_ip(request)
        user.save(update_fields=["last_login_at", "last_login_ip"])
        services.record_login(request, email=user.email, success=True, user=user, mfa_used=True)
        return _token_response(user, request, mfa_used=True)


def _verify_totp_or_backup(user, code: str) -> bool:
    secret = decrypt_secret(user.mfa_secret)
    if pyotp.TOTP(secret).verify(code, valid_window=1):
        return True
    # Fallback: one-time backup code
    hashed = hash_token(code)
    if hashed in user.mfa_backup_codes:
        remaining = [c for c in user.mfa_backup_codes if c != hashed]
        user.mfa_backup_codes = remaining
        user.save(update_fields=["mfa_backup_codes"])
        return True
    return False


class RefreshView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        s = RefreshSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            access, refresh = tokens.rotate_refresh_token(
                s.validated_data["refresh"],
                user_agent=services.get_user_agent(request),
                ip=services.get_client_ip(request),
            )
        except AuthenticationFailed as exc:
            return Response({"detail": str(exc.detail)}, status=status.HTTP_401_UNAUTHORIZED)
        return Response({"access": access, "refresh": refresh}, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        raw = request.data.get("refresh")
        if raw:
            try:
                payload = tokens.decode_token(raw, expected_type="refresh")
                tokens.revoke_family(payload.get("family_id"), reason="logout")
            except Exception:  # noqa: BLE001 — logout is best-effort/idempotent
                pass
        return Response({"detail": "Logged out."}, status=status.HTTP_200_OK)


@method_decorator(ratelimit(key=_email_key, rate="3/h", method="POST", block=False), name="post")
class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if _rate_limited(request):
            return _too_many()
        s = PasswordResetRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        email = s.validated_data["email"].lower()
        user = User.objects.filter(email=email, is_active=True).first()
        if user is not None:
            raw, _ = services.create_password_reset_token(user)
            services.send_password_reset_email(user, raw)
        # Always 200 — never reveal whether the email exists.
        return Response({"detail": "If the email exists, a reset link has been sent."},
                        status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        s = PasswordResetConfirmSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        obj = services.consume_password_reset_token(s.validated_data["token"])
        if obj is None:
            return Response({"detail": "Invalid or expired token."},
                            status=status.HTTP_400_BAD_REQUEST)
        user = obj.user
        with transaction.atomic():
            user.set_password(s.validated_data["password"])
            user.password_changed_at = timezone.now()
            user.save(update_fields=["password", "password_changed_at"])
            obj.is_used = True
            obj.save(update_fields=["is_used"])
            tokens.revoke_all_for_user(user, reason="password_reset")
        return Response({"detail": "Password has been reset."}, status=status.HTTP_200_OK)


# ── MFA setup ───────────────────────────────────────────────────────────────
class MfaSetupInitiateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        secret = pyotp.random_base32()
        user.mfa_secret = encrypt_secret(secret)
        user.save(update_fields=["mfa_secret"])
        uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="Sridhar ERP")
        return Response({"secret": secret, "qr_uri": uri}, status=status.HTTP_200_OK)


class MfaSetupConfirmView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = MfaConfirmSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = request.user
        if not user.mfa_secret:
            return Response({"detail": "Start MFA setup first."}, status=status.HTTP_400_BAD_REQUEST)
        secret = decrypt_secret(user.mfa_secret)
        if not pyotp.TOTP(secret).verify(s.validated_data["code"], valid_window=1):
            return Response({"detail": "Invalid code."}, status=status.HTTP_400_BAD_REQUEST)
        raw_codes, hashed_codes = services.generate_backup_codes()
        user.mfa_enabled = True
        user.mfa_backup_codes = hashed_codes
        user.save(update_fields=["mfa_enabled", "mfa_backup_codes"])
        return Response({"detail": "MFA enabled", "backup_codes": raw_codes},
                        status=status.HTTP_200_OK)


class MfaDisableView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = MfaDisableSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(s.validated_data["password"]):
            return Response({"detail": "Invalid password."}, status=status.HTTP_400_BAD_REQUEST)
        user.mfa_enabled = False
        user.mfa_secret = ""
        user.mfa_backup_codes = []
        user.save(update_fields=["mfa_enabled", "mfa_secret", "mfa_backup_codes"])
        return Response({"detail": "MFA disabled."}, status=status.HTTP_200_OK)


# ── Account self-service (Phase P2.17) ───────────────────────────────────────
class ChangePasswordView(APIView):
    """Authenticated password change: verify current password, rotate, revoke other
    sessions (keep the caller's if its refresh token is supplied), email a notice."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = ChangePasswordSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(s.validated_data["current_password"]):
            return Response({"detail": "Current password is incorrect."},
                            status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            user.set_password(s.validated_data["password"])
            user.password_changed_at = timezone.now()
            user.save(update_fields=["password", "password_changed_at"])
        keep = None
        raw = s.validated_data.get("refresh")
        if raw:
            try:
                keep = tokens.decode_token(raw, expected_type="refresh").get("family_id")
            except AuthenticationFailed:
                keep = None
        sessions.revoke_all_sessions(user, keep_family_id=keep)
        services.send_password_changed_notice(user)
        return Response({"detail": "Password changed."}, status=status.HTTP_200_OK)


class ChangeEmailView(APIView):
    """Authenticated email change: confirm with password, then send a verification
    link to the NEW address. The change only applies once that link is confirmed."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = ChangeEmailSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(s.validated_data["password"]):
            return Response({"detail": "Password is incorrect."},
                            status=status.HTTP_400_BAD_REQUEST)
        new_email = s.validated_data["new_email"].lower()
        if new_email == user.email:
            return Response({"detail": "That is already your email address."},
                            status=status.HTTP_400_BAD_REQUEST)
        # Don't reveal whether the address is taken — respond the same either way.
        if not User.objects.filter(email=new_email).exists():
            raw, _ = services.create_email_change_token(user, new_email)
            services.send_email_change_verification(new_email, raw)
        return Response({"detail": "A confirmation link has been sent to the new address."},
                        status=status.HTTP_200_OK)


@method_decorator(ratelimit(key=_email_key, rate="3/h", method="POST", block=False), name="post")
class ResendVerificationView(APIView):
    """Re-send the account verification email for an unverified user. Always 200."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if _rate_limited(request):
            return _too_many()
        s = ResendVerificationSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        email = s.validated_data["email"].lower()
        user = User.objects.filter(email=email, is_verified=False).first()
        if user is not None:
            raw, _ = services.create_email_verification_token(user)
            services.send_verification_email(user, raw)
        return Response(
            {"detail": "If the account exists and is unverified, a verification email was sent."},
            status=status.HTTP_200_OK)


# ── Google OAuth2 (PKCE) ────────────────────────────────────────────────────
class GoogleAuthorizeView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        code_verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).decode().rstrip("=")
        state = secrets.token_urlsafe(16)
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "response_type": "code",
            "scope": "openid email profile",
            "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
            "access_type": "offline",
        }
        url = f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"
        resp = redirect(url)
        # Persist verifier+state server-side via a signed, http-only cookie (NOT the DB).
        cookie_val = signing.dumps({"code_verifier": code_verifier, "state": state},
                                   salt=OAUTH_STATE_SALT)
        resp.set_cookie("g_oauth", cookie_val, max_age=600, httponly=True,
                        samesite="Lax", secure=not settings.DEBUG)
        return resp


class GoogleCallbackView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        cookie = request.COOKIES.get("g_oauth")
        if not code or not cookie:
            return Response({"detail": "Missing code or state."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            stored = signing.loads(cookie, salt=OAUTH_STATE_SALT, max_age=600)
        except signing.BadSignature:
            return Response({"detail": "Invalid OAuth state."}, status=status.HTTP_400_BAD_REQUEST)
        if not state or state != stored.get("state"):
            return Response({"detail": "State mismatch."}, status=status.HTTP_400_BAD_REQUEST)

        token_resp = requests.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
            "grant_type": "authorization_code",
            "code_verifier": stored["code_verifier"],
        }, timeout=10)
        if token_resp.status_code != 200:
            return Response({"detail": "Token exchange failed."}, status=status.HTTP_400_BAD_REQUEST)
        access_token = token_resp.json().get("access_token")

        userinfo = requests.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if userinfo.status_code != 200:
            return Response({"detail": "Failed to fetch userinfo."}, status=status.HTTP_400_BAD_REQUEST)
        info = userinfo.json()
        email = (info.get("email") or "").lower()
        sub = info.get("sub")
        if not email or not sub:
            return Response({"detail": "Incomplete Google profile."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            user, _ = User.objects.get_or_create(
                email=email,
                defaults={"full_name": info.get("name", ""), "is_verified": True},
            )
            if not user.is_verified:
                user.is_verified = True
                user.save(update_fields=["is_verified"])
            OAuthAccount.objects.update_or_create(
                provider="google",
                provider_user_id=sub,
                defaults={
                    "user": user,
                    "email": email,
                    # Reference only — never persist the raw OAuth token (hard constraint).
                    "access_token_ref": f"google:{sub}",
                    "raw_data": {"sub": sub, "email": email, "name": info.get("name", "")},
                },
            )

        access, refresh, _ = tokens.issue_token_pair(
            user, user_agent=services.get_user_agent(request), ip=services.get_client_ip(request))
        frontend = f"{settings.FRONTEND_URL}/oauth/callback#access={access}&refresh={refresh}"
        resp = redirect(frontend)
        resp.delete_cookie("g_oauth")
        return resp


# ── Microsoft OAuth2 (Azure AD v2.0, PKCE) ──────────────────────────────────
class MicrosoftAuthorizeView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        code_verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).decode().rstrip("=")
        state = secrets.token_urlsafe(16)
        params = {
            "client_id": settings.MICROSOFT_CLIENT_ID,
            "response_type": "code",
            "scope": "openid email profile",
            "redirect_uri": settings.MICROSOFT_OAUTH_REDIRECT_URI,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
            "response_mode": "query",
        }
        url = f"{_ms_authorize_url()}?{urllib.parse.urlencode(params)}"
        resp = redirect(url)
        cookie_val = signing.dumps({"code_verifier": code_verifier, "state": state},
                                   salt=MS_STATE_SALT)
        resp.set_cookie("ms_oauth", cookie_val, max_age=600, httponly=True,
                        samesite="Lax", secure=not settings.DEBUG)
        return resp


class MicrosoftCallbackView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        cookie = request.COOKIES.get("ms_oauth")
        if not code or not cookie:
            return Response({"detail": "Missing code or state."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            stored = signing.loads(cookie, salt=MS_STATE_SALT, max_age=600)
        except signing.BadSignature:
            return Response({"detail": "Invalid OAuth state."}, status=status.HTTP_400_BAD_REQUEST)
        if not state or state != stored.get("state"):
            return Response({"detail": "State mismatch."}, status=status.HTTP_400_BAD_REQUEST)

        token_resp = requests.post(_ms_token_url(), data={
            "code": code,
            "client_id": settings.MICROSOFT_CLIENT_ID,
            "client_secret": settings.MICROSOFT_CLIENT_SECRET,
            "redirect_uri": settings.MICROSOFT_OAUTH_REDIRECT_URI,
            "grant_type": "authorization_code",
            "code_verifier": stored["code_verifier"],
        }, timeout=10)
        if token_resp.status_code != 200:
            return Response({"detail": "Token exchange failed."}, status=status.HTTP_400_BAD_REQUEST)
        access_token = token_resp.json().get("access_token")

        userinfo = requests.get(
            MS_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
        if userinfo.status_code != 200:
            return Response({"detail": "Failed to fetch userinfo."}, status=status.HTTP_400_BAD_REQUEST)
        info = userinfo.json()
        email = (info.get("email") or info.get("preferred_username") or "").lower()
        sub = info.get("sub")
        if not email or not sub:
            return Response({"detail": "Incomplete Microsoft profile."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            user, _ = User.objects.get_or_create(
                email=email, defaults={"full_name": info.get("name", ""), "is_verified": True})
            if not user.is_verified:
                user.is_verified = True
                user.save(update_fields=["is_verified"])
            OAuthAccount.objects.update_or_create(
                provider="microsoft", provider_user_id=sub,
                defaults={
                    "user": user, "email": email,
                    "access_token_ref": f"microsoft:{sub}",  # reference only — never the raw token
                    "raw_data": {"sub": sub, "email": email, "name": info.get("name", "")},
                },
            )

        access, refresh, _ = tokens.issue_token_pair(
            user, user_agent=services.get_user_agent(request), ip=services.get_client_ip(request))
        frontend = f"{settings.FRONTEND_URL}/oauth/callback#access={access}&refresh={refresh}"
        resp = redirect(frontend)
        resp.delete_cookie("ms_oauth")
        return resp


# ── Session management (Phase 1.27) ──────────────────────────────────────────
class SessionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = sessions.list_sessions(request.user)
        return Response(SessionSerializer(qs, many=True).data)


class SessionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, family_id):
        if not sessions.revoke_session(request.user, family_id):
            return Response({"detail": "Session not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SessionRevokeAllView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = RevokeAllSessionsSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        keep = None
        raw = s.validated_data.get("refresh")
        if raw:
            try:
                keep = tokens.decode_token(raw, expected_type="refresh").get("family_id")
            except AuthenticationFailed:
                keep = None
        count = sessions.revoke_all_sessions(request.user, keep_family_id=keep)
        return Response({"revoked": count}, status=status.HTTP_200_OK)


# ── Passkey / WebAuthn (Phase 1.27) ──────────────────────────────────────────
class PasskeyListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(webauthn_service.list_passkeys(request.user))


class PasskeyDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, credential_id):
        if not webauthn_service.delete_passkey(request.user, credential_id):
            return Response({"detail": "Passkey not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasskeyRegisterBeginView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        options, state = webauthn_service.register_begin(request.user)
        cache.set(_reg_challenge_key(request.user.id), state, WEBAUTHN_CHALLENGE_TTL)
        return Response(webauthn_service.options_to_dict(options))


class PasskeyRegisterCompleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = PasskeyRegisterCompleteSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        state = cache.get(_reg_challenge_key(request.user.id))
        if state is None:
            return Response({"detail": "No registration in progress or challenge expired."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            cred = webauthn_service.register_complete(
                request.user, state, s.validated_data["credential"],
                name=s.validated_data.get("name", ""))
        except webauthn_service.WebAuthnError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        cache.delete(_reg_challenge_key(request.user.id))
        return Response({"detail": "Passkey registered", "credential": cred},
                        status=status.HTTP_201_CREATED)


class PasskeyAuthenticateBeginView(APIView):
    """Begin a passkey assertion as the second factor after password (mfa_token)."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        s = PasskeyAuthenticateBeginSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            payload = tokens.decode_token(s.validated_data["mfa_token"], expected_type="mfa_challenge")
        except AuthenticationFailed as exc:
            return Response({"detail": str(exc.detail)}, status=status.HTTP_401_UNAUTHORIZED)
        user = User.objects.filter(pk=payload.get("user_id"), is_active=True).first()
        if user is None:
            return Response({"detail": "Invalid challenge."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            options, state = webauthn_service.authenticate_begin(user)
        except webauthn_service.WebAuthnError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        cache.set(_auth_challenge_key(user.id), state, WEBAUTHN_CHALLENGE_TTL)
        return Response(webauthn_service.options_to_dict(options))


class PasskeyAuthenticateCompleteView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        s = PasskeyAuthenticateCompleteSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            payload = tokens.decode_token(s.validated_data["mfa_token"], expected_type="mfa_challenge")
        except AuthenticationFailed as exc:
            return Response({"detail": str(exc.detail)}, status=status.HTTP_401_UNAUTHORIZED)
        user = User.objects.filter(pk=payload.get("user_id"), is_active=True).first()
        if user is None:
            return Response({"detail": "Invalid challenge."}, status=status.HTTP_401_UNAUTHORIZED)
        state = cache.get(_auth_challenge_key(user.id))
        if state is None:
            return Response({"detail": "No authentication in progress or challenge expired."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            webauthn_service.authenticate_complete(user, state, s.validated_data["credential"])
        except webauthn_service.WebAuthnError as exc:
            services.record_login(request, email=user.email, success=False, user=user,
                                  failure_reason="passkey_invalid", mfa_used=True)
            return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)
        cache.delete(_auth_challenge_key(user.id))
        user.last_login_at = timezone.now()
        user.last_login_ip = services.get_client_ip(request)
        user.save(update_fields=["last_login_at", "last_login_ip"])
        services.record_login(request, email=user.email, success=True, user=user, mfa_used=True)
        return _token_response(user, request, mfa_used=True)
