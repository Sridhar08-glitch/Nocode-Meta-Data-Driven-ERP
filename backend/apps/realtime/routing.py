"""WebSocket URL routing for realtime streams (merged into config/asgi.py)."""
from django.urls import re_path

from .consumers import (
    DashboardStreamConsumer,
    PresenceConsumer,
    RecordStreamConsumer,
    WorkflowStreamConsumer,
)

websocket_urlpatterns = [
    re_path(r"^ws/records/(?P<entity_slug>[a-z][a-z0-9_]*)/$", RecordStreamConsumer.as_asgi()),
    re_path(r"^ws/records/$", RecordStreamConsumer.as_asgi()),
    re_path(r"^ws/workflows/$", WorkflowStreamConsumer.as_asgi()),
    re_path(r"^ws/dashboards/$", DashboardStreamConsumer.as_asgi()),
    re_path(r"^ws/presence/$", PresenceConsumer.as_asgi()),
]
