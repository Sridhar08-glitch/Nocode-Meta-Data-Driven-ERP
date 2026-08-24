"""Integrations API routes (PROJECT_HANDBOOK.md §30.4) — mounted at /api/v1/integrations/."""
from django.urls import path

from . import views

app_name = "integrations"

urlpatterns = [
    # webhook subscriptions
    path("webhooks/subscriptions/", views.SubscriptionListCreateView.as_view(), name="sub-list"),
    path("webhooks/subscriptions/<uuid:pk>/", views.SubscriptionDetailView.as_view(), name="sub-detail"),
    path("webhooks/subscriptions/<uuid:pk>/test/", views.SubscriptionTestView.as_view(), name="sub-test"),
    path("webhooks/subscriptions/<uuid:pk>/deliveries/", views.SubscriptionDeliveriesView.as_view(), name="sub-deliveries"),
    path("webhooks/subscriptions/<uuid:pk>/enable/", views.SubscriptionEnableView.as_view(), name="sub-enable"),
    path("webhooks/subscriptions/<uuid:pk>/disable/", views.SubscriptionDisableView.as_view(), name="sub-disable"),
    # connectors
    path("connectors/", views.ConnectorListCreateView.as_view(), name="connector-list"),
    path("connectors/<uuid:pk>/", views.ConnectorDetailView.as_view(), name="connector-detail"),
    path("connectors/<uuid:pk>/test/", views.ConnectorTestView.as_view(), name="connector-test"),
    # oauth apps
    path("oauth-apps/", views.OAuthAppListCreateView.as_view(), name="oauth-list"),
    path("oauth-apps/<uuid:pk>/", views.OAuthAppDetailView.as_view(), name="oauth-detail"),
    # inbound webhooks
    path("inbound-webhooks/", views.InboundListCreateView.as_view(), name="inbound-list"),
    path("inbound-webhooks/<uuid:pk>/", views.InboundDetailView.as_view(), name="inbound-detail"),
    path("inbound-webhooks/<uuid:pk>/rotate-token/", views.InboundRotateTokenView.as_view(), name="inbound-rotate"),
]
