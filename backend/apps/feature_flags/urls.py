from django.urls import path

from . import views

app_name = "feature_flags"

urlpatterns = [
    path("active/", views.ActiveFlagsView.as_view(), name="active"),
    path("", views.FlagListCreateView.as_view(), name="flag-list"),
    path("<uuid:flag_id>/", views.FlagDetailView.as_view(), name="flag-detail"),
    path("<uuid:flag_id>/overrides/", views.OverrideListCreateView.as_view(), name="override-list"),
    path("<uuid:flag_id>/overrides/<uuid:override_id>/", views.OverrideDetailView.as_view(),
         name="override-detail"),
]
