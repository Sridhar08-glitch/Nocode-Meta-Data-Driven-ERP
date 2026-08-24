"""Marketplace API routes (PROJECT_HANDBOOK.md §34.4)."""
from django.urls import path

from . import views

app_name = "marketplace"

urlpatterns = [
    # Public browse (no auth)
    path("plugins/", views.PluginBrowseView.as_view(), name="browse"),
    path("plugins/<uuid:plugin_id>/", views.PluginDetailView.as_view(), name="detail"),
    path("plugins/<uuid:plugin_id>/versions/<uuid:version_id>/",
         views.PluginVersionDetailView.as_view(), name="version-detail"),

    # Workspace install management (auth)
    path("installed/", views.InstalledListView.as_view(), name="installed-list"),
    path("installed/<uuid:pk>/", views.InstalledDetailView.as_view(), name="installed-detail"),
    path("plugins/<uuid:plugin_id>/install/",
         views.PluginInstallView.as_view(), name="install"),
    path("installed/<uuid:pk>/uninstall/",
         views.PluginUninstallView.as_view(), name="uninstall"),
    path("installed/<uuid:pk>/upgrade/", views.PluginUpgradeView.as_view(), name="upgrade"),
    path("installed/<uuid:pk>/rollback/", views.PluginRollbackView.as_view(), name="rollback"),

    # Publisher management (is_staff)
    path("manage/plugins/", views.ManagePluginListView.as_view(), name="manage-list"),
    path("manage/plugins/<uuid:pk>/",
         views.ManagePluginDetailView.as_view(), name="manage-detail"),
    path("manage/plugins/<uuid:pk>/publish/",
         views.ManagePluginPublishView.as_view(), name="manage-publish"),
    path("manage/plugins/<uuid:pk>/deprecate/",
         views.ManagePluginDeprecateView.as_view(), name="manage-deprecate"),
    path("manage/plugins/<uuid:pk>/versions/",
         views.ManagePluginVersionCreateView.as_view(), name="manage-version-create"),
]
