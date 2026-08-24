"""Email-template routes (Phase 1.33) — mounted at /api/v1/templates/email/."""
from django.urls import path

from . import views

app_name = "email_templates"

urlpatterns = [
    path("", views.EmailTemplateListCreateView.as_view(), name="list-create"),
    path("<uuid:pk>/", views.EmailTemplateDetailView.as_view(), name="detail"),
    path("<uuid:pk>/render/", views.EmailTemplateRenderView.as_view(), name="render"),
    path("<uuid:pk>/test-send/", views.EmailTemplateTestSendView.as_view(), name="test-send"),
]
