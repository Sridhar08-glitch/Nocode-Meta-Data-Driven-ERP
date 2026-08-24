"""Activity feed routes (PROJECT_HANDBOOK.md §23.3). Per-record routes live in apps.records.urls."""
from django.urls import path

from . import views

app_name = "activity"

urlpatterns = [
    path("feed/", views.ActivityFeedView.as_view(), name="feed"),
]
