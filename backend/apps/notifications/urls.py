"""Notifications API routes (PROJECT_HANDBOOK.md §22.5)."""
from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.NotificationListView.as_view(), name="list"),
    path("read-all/", views.NotificationReadAllView.as_view(), name="read-all"),
    path("unread-count/", views.NotificationUnreadCountView.as_view(), name="unread-count"),
    path("preferences/", views.PreferenceView.as_view(), name="preferences"),
    path("<uuid:pk>/read/", views.NotificationReadView.as_view(), name="read"),
    path("templates/", views.TemplateListCreateView.as_view(), name="template-list"),
    path("templates/<uuid:pk>/", views.TemplateDetailView.as_view(), name="template-detail"),
    path("templates/<uuid:pk>/test/", views.TemplateTestView.as_view(), name="template-test"),
]
