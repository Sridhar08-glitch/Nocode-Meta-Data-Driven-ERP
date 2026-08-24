"""Approvals API routes (PROJECT_HANDBOOK.md §27.3)."""
from django.urls import path

from . import views

app_name = "approvals"

urlpatterns = [
    path("processes/", views.ProcessListCreateView.as_view(), name="process-list"),
    path("processes/<uuid:pk>/", views.ProcessDetailView.as_view(), name="process-detail"),
    path("requests/", views.RequestListView.as_view(), name="request-list"),
    path("requests/pending-for-me/", views.PendingForMeView.as_view(), name="pending-for-me"),
    path("requests/<uuid:pk>/", views.RequestDetailView.as_view(), name="request-detail"),
    path("requests/<uuid:pk>/approve/", views.RequestApproveView.as_view(), name="request-approve"),
    path("requests/<uuid:pk>/reject/", views.RequestRejectView.as_view(), name="request-reject"),
    path("requests/<uuid:pk>/cancel/", views.RequestCancelView.as_view(), name="request-cancel"),
]
