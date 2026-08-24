"""Public inbound webhook endpoint (PROJECT_HANDBOOK.md §30.3) — mounted at /api/v1/webhooks/."""
from django.urls import path

from . import views

app_name = "integrations_webhooks"

urlpatterns = [
    path("inbound/<str:token>/", views.InboundWebhookReceiveView.as_view(), name="inbound-receive"),
]
