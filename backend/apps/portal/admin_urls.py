"""
Custom-admin Portal Builder routes (Phase F3.7) — mounted at /api/v1/portal-admin/.

Deliberately OUTSIDE the ``/api/v1/portal/`` prefix, which TenantMiddleware exempts for the portal
auth realm. These endpoints are workspace-member (owner/admin) authenticated, so they need the
middleware to resolve ``request.workspace_member``.
"""
from django.urls import path

from . import admin_views

app_name = "portal_admin"

urlpatterns = [
    path("config/", admin_views.PortalConfigView.as_view(), name="config"),
    path("users/", admin_views.PortalUserListCreateView.as_view(), name="user-list"),
    path("users/<uuid:pk>/", admin_views.PortalUserDetailView.as_view(), name="user-detail"),
    path("grants/", admin_views.PortalGrantListCreateView.as_view(), name="grant-list"),
    path("grants/<uuid:pk>/", admin_views.PortalGrantDetailView.as_view(), name="grant-detail"),
]
