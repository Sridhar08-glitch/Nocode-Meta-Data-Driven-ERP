"""System-Entity Adapter (B0) URLs at /api/v1/system-entities/."""
from django.urls import path

from . import views

urlpatterns = [
    path("", views.EntityListView.as_view(), name="system-entities-list"),
    path("<slug:slug>/", views.EntityDescriptorView.as_view(), name="system-entity-descriptor"),
    path("<slug:slug>/records/", views.RecordListView.as_view(), name="system-entity-records"),
    path("<slug:slug>/records/<uuid:record_id>/", views.RecordDetailView.as_view(),
         name="system-entity-record-detail"),
]
