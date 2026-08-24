"""
TenantMiddleware — resolves the active workspace for each request and activates
PostgreSQL Row-Level Security by setting the ``app.workspace_id`` session GUC.

Ordering note: this middleware runs *before* DRF authenticates the view, so it
authenticates the caller itself (reusing the existing DRF authenticators) in order
to verify workspace membership. The DB-layer RLS policy is the mandatory backstop;
this middleware is what makes the policy fire.

Behavior
--------
- Exempt paths and requests without an ``X-Workspace-Slug`` header pass through
  with no workspace context (``request.workspace_id is None``). On PostgreSQL an
  unset GUC means RLS returns zero rows — fail-closed.
- A slug for an unknown/inactive workspace → 404.
- A resolvable caller who is not an active member of the workspace → 403.
- A verified member → ``request.workspace`` / ``workspace_id`` / ``workspace_member``
  are attached and ``app.workspace_id`` is set for the request (PostgreSQL only),
  then reset on the way out so pooled connections never leak tenant context.
"""
import contextlib

from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

from apps.tenancy.rls import clear_workspace, set_workspace

RLS_FLAG = "_rls_activated"


class TenantMiddleware(MiddlewareMixin):
    EXEMPT_PREFIXES = (
        "/api/v1/auth/",
        "/api/v1/portal/",
        "/api/openapi/",
        "/api/schema/",
        "/static/",
        "/media/",
    )

    # ── request ───────────────────────────────────────────────────────────────
    def process_request(self, request):
        request.workspace = None
        request.workspace_id = None
        request.workspace_member = None

        if any(request.path.startswith(p) for p in self.EXEMPT_PREFIXES):
            return None

        slug = request.META.get("HTTP_X_WORKSPACE_SLUG", "").strip()
        if not slug:
            return None  # no workspace context requested

        from apps.tenancy.models import Workspace, WorkspaceMember

        try:
            workspace = Workspace.objects.get(slug=slug, is_active=True)
        except Workspace.DoesNotExist:
            return JsonResponse({"detail": "Workspace not found."}, status=404)

        user = self._resolve_user(request)
        if user is None:
            # Caller could not be authenticated; let the view's auth layer reject.
            # No workspace context is set, so RLS stays fail-closed.
            return None

        member = (
            WorkspaceMember.objects
            .filter(workspace=workspace, user=user, status="active")
            .first()
        )
        if member is None:
            return JsonResponse(
                {"detail": "You are not a member of this workspace."}, status=403)

        request.workspace = workspace
        request.workspace_id = workspace.id
        request.workspace_member = member
        self._activate_rls(request, workspace.id)
        return None

    # ── response / exception ────────────────────────────────────────────────────
    def process_response(self, request, response):
        self._deactivate_rls(request)
        return response

    def process_exception(self, request, exception):
        self._deactivate_rls(request)
        return None

    # ── helpers ──────────────────────────────────────────────────────────────
    @staticmethod
    def _resolve_user(request):
        """Authenticate the caller via the same authenticators DRF uses."""
        from apps.accounts.authentication import (
            ApiKeyAuthentication,
            NexusJWTAuthentication,
        )
        for auth_cls in (NexusJWTAuthentication, ApiKeyAuthentication):
            try:
                result = auth_cls().authenticate(request)
            except Exception:  # noqa: BLE001 — auth failure ⇒ treat as anonymous here
                result = None
            if result is not None:
                return result[0]
        return None

    @staticmethod
    def _activate_rls(request, workspace_id):
        # Delegates to the reusable RLS helper (no-op on SQLite). The flag marks
        # that a reset is owed on the way out.
        if set_workspace(workspace_id):
            setattr(request, RLS_FLAG, True)

    @staticmethod
    def _deactivate_rls(request):
        if not getattr(request, RLS_FLAG, False):
            return
        # Never let GUC cleanup break the response.
        with contextlib.suppress(Exception):
            clear_workspace()
        setattr(request, RLS_FLAG, False)
