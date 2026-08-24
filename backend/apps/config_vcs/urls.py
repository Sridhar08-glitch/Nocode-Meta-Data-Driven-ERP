from django.urls import path

from . import views

app_name = "config_vcs"

urlpatterns = [
    path("commit/", views.CommitView.as_view(), name="commit"),
    path("commits/", views.CommitListView.as_view(), name="commits"),
    path("diff/", views.DiffView.as_view(), name="diff"),
    path("rollback/", views.RollbackView.as_view(), name="rollback"),
    # Branches + merge requests (Phase 1.28)
    path("branches/", views.BranchListCreateView.as_view(), name="branches"),
    path("merge-requests/", views.MergeRequestListCreateView.as_view(), name="merge-requests"),
    path("merge-requests/<uuid:mr_id>/", views.MergeRequestDetailView.as_view(),
         name="merge-request-detail"),
    path("merge-requests/<uuid:mr_id>/merge/", views.MergeRequestMergeView.as_view(),
         name="merge-request-merge"),
    path("merge-requests/<uuid:mr_id>/resolve/", views.MergeRequestResolveView.as_view(),
         name="merge-request-resolve"),
]
