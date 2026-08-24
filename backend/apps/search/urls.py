"""Search API routes (PROJECT_HANDBOOK.md §26.3)."""
from django.urls import path

from . import views

app_name = "search"

urlpatterns = [
    path("", views.SearchView.as_view(), name="search"),
    path("indexes/", views.IndexListCreateView.as_view(), name="index-list"),
    path("indexes/<uuid:pk>/", views.IndexDetailView.as_view(), name="index-detail"),
    path("indexes/<uuid:pk>/reindex/", views.IndexReindexView.as_view(), name="index-reindex"),
    path("saved/", views.SavedSearchListCreateView.as_view(), name="saved-list"),
    path("saved/<uuid:pk>/", views.SavedSearchDetailView.as_view(), name="saved-detail"),
    path("recent/", views.RecentSearchView.as_view(), name="recent"),
]
