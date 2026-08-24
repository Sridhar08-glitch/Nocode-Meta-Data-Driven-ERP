"""
Portal authentication views — a separate realm from workspace users.

Endpoints live under /api/v1/portal/auth/. They authenticate ``PortalUser``
records (scoped by workspace) and issue portal-namespaced JWTs.
"""
from django.contrib.auth.hashers import check_password
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenancy.models import Workspace

from . import tokens
from .authentication import PortalJWTAuthentication
from .models import PortalUser
from .serializers import PortalLoginSerializer, PortalRefreshSerializer


def _client_ip(request):
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or None


def _user_agent(request):
    return request.META.get("HTTP_USER_AGENT", "")[:500]


class PortalLoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        s = PortalLoginSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        workspace = Workspace.objects.filter(
            slug=s.validated_data["workspace_slug"], is_active=True
        ).first()
        generic_error = Response({"detail": "Invalid credentials."},
                                 status=status.HTTP_401_UNAUTHORIZED)
        if workspace is None:
            return generic_error

        portal_user = PortalUser.objects.filter(
            workspace_id=workspace.id, email=s.validated_data["email"].lower()
        ).first()
        if portal_user is None or not portal_user.is_active:
            return generic_error
        if not check_password(s.validated_data["password"], portal_user.password_hash):
            return generic_error
        if not portal_user.is_verified:
            return Response({"detail": "Email not verified."}, status=status.HTTP_403_FORBIDDEN)

        portal_user.last_login_at = timezone.now()
        portal_user.last_login_ip = _client_ip(request)
        portal_user.save(update_fields=["last_login_at", "last_login_ip"])

        access, refresh, _ = tokens.issue_portal_pair(
            portal_user, user_agent=_user_agent(request), ip=_client_ip(request))
        return Response(
            {
                "access": access,
                "refresh": refresh,
                "portal_user": {
                    "id": str(portal_user.id),
                    "email": portal_user.email,
                    "full_name": portal_user.full_name,
                    "workspace_id": str(portal_user.workspace_id),
                },
            },
            status=status.HTTP_200_OK,
        )


class PortalRefreshView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        s = PortalRefreshSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            access, refresh = tokens.rotate_portal_refresh(
                s.validated_data["refresh"],
                user_agent=_user_agent(request), ip=_client_ip(request))
        except AuthenticationFailed as exc:
            return Response({"detail": str(exc.detail)}, status=status.HTTP_401_UNAUTHORIZED)
        return Response({"access": access, "refresh": refresh}, status=status.HTTP_200_OK)


class PortalLogoutView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        raw = request.data.get("refresh")
        if raw:
            try:
                payload = tokens.decode_portal_token(raw, expected_type="portal_refresh")
                tokens.revoke_portal_session(payload.get("family_id"), reason="logout")
            except Exception:  # noqa: BLE001 — best-effort logout
                pass
        return Response({"detail": "Logged out."}, status=status.HTTP_200_OK)


class PortalMeView(APIView):
    """Demonstrates the portal realm: only a portal_access token is accepted."""
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pu = request.user
        return Response(
            {"id": str(pu.id), "email": pu.email, "workspace_id": str(pu.workspace_id),
             "realm": "portal"},
            status=status.HTTP_200_OK,
        )
