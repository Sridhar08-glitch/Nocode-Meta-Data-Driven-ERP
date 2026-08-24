from django.urls import path

from . import data_views, views

app_name = "portal"

urlpatterns = [
    path("auth/login/", views.PortalLoginView.as_view(), name="login"),
    path("auth/refresh/", views.PortalRefreshView.as_view(), name="refresh"),
    path("auth/logout/", views.PortalLogoutView.as_view(), name="logout"),
    path("auth/me/", views.PortalMeView.as_view(), name="me"),
    # Scoped data (Phase 1.34)
    path("data/<slug:entity_slug>/", data_views.PortalRecordListCreateView.as_view(),
         name="data-list"),
    path("data/<slug:entity_slug>/<uuid:record_id>/", data_views.PortalRecordDetailView.as_view(),
         name="data-detail"),
]
