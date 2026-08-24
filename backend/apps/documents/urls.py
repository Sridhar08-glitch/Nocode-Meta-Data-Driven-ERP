"""Documents API routes (PROJECT_HANDBOOK.md §24.4)."""
from django.urls import path

from . import views

app_name = "documents"

urlpatterns = [
    # signed local download (unauthenticated; signature is the capability)
    path("download/", views.SignedDownloadView.as_view(), name="signed-download"),
    # folders
    path("folders/", views.FolderListCreateView.as_view(), name="folder-list"),
    path("folders/<uuid:pk>/", views.FolderDetailView.as_view(), name="folder-detail"),
    path("folders/<uuid:pk>/contents/", views.FolderContentsView.as_view(), name="folder-contents"),
    # documents
    path("", views.DocumentListCreateView.as_view(), name="list-create"),
    path("<uuid:pk>/", views.DocumentDetailView.as_view(), name="detail"),
    path("<uuid:pk>/restore/", views.DocumentRestoreView.as_view(), name="restore"),
    path("<uuid:pk>/download-url/", views.DocumentDownloadUrlView.as_view(), name="download-url"),
    path("<uuid:pk>/versions/", views.DocumentVersionsView.as_view(), name="versions"),
    path("<uuid:pk>/attach/", views.DocumentAttachView.as_view(), name="attach"),
    path("<uuid:pk>/detach/", views.DocumentDetachView.as_view(), name="detach"),
]
