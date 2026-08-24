"""
Schema Registry URL configuration.

Mount under ``/api/schema/`` in the root urlconf:

    path("api/schema/", include("apps.schema_registry.urls")),
"""
from django.urls import path

from apps.schema_registry.views import (
    EntityDetailView,
    EntityListView,
    FieldDetailView,
    FieldListView,
    SchemaDiffView,
    SchemaRollbackView,
    SchemaVersionListView,
)

app_name = "schema_registry"

urlpatterns = [
    # Entity
    path("entities/", EntityListView.as_view(), name="entity-list"),
    path("entities/<slug:slug>/", EntityDetailView.as_view(), name="entity-detail"),

    # Fields
    path("entities/<slug:slug>/fields/", FieldListView.as_view(), name="field-list"),
    path(
        "entities/<slug:slug>/fields/<slug:field_slug>/",
        FieldDetailView.as_view(),
        name="field-detail",
    ),

    # Schema versions
    path(
        "entities/<slug:slug>/versions/",
        SchemaVersionListView.as_view(),
        name="version-list",
    ),
    path(
        "entities/<slug:slug>/diff/",
        SchemaDiffView.as_view(),
        name="version-diff",
    ),
    path(
        "entities/<slug:slug>/rollback/",
        SchemaRollbackView.as_view(),
        name="schema-rollback",
    ),
]
