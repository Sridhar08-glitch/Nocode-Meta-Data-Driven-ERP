"""Branding API routes (PROJECT_HANDBOOK.md §32.3)."""
from django.urls import path

from . import views

app_name = "branding"

urlpatterns = [
    path("", views.BrandingView.as_view(), name="branding"),
    path("smtp/", views.SMTPConfigView.as_view(), name="smtp"),
    path("smtp/test/", views.SMTPTestView.as_view(), name="smtp-test"),
]
