"""Localization API routes (PROJECT_HANDBOOK.md §32.3)."""
from django.urls import path

from . import views

app_name = "localization"

urlpatterns = [
    path("locale/", views.LocaleView.as_view(), name="locale"),
    path("translations/", views.TranslationsView.as_view(), name="translations"),
    path("translations/<uuid:key_id>/", views.TranslationOverrideView.as_view(),
         name="translation-override"),
    path("entity-labels/", views.EntityLabelListCreateView.as_view(), name="entity-label-list"),
    path("entity-labels/<uuid:pk>/", views.EntityLabelDetailView.as_view(),
         name="entity-label-detail"),
    path("keys/", views.KeyListView.as_view(), name="keys"),
]
