from django.urls import path

from . import views

app_name = "metadata"

urlpatterns = [
    path("modules/", views.ModuleListCreateView.as_view(), name="module-list"),
    path("modules/<uuid:module_id>/", views.ModuleDetailView.as_view(), name="module-detail"),
    path("entities/", views.EntityListCreateView.as_view(), name="entity-list"),
    path("entities/<slug:slug>/", views.EntityDetailView.as_view(), name="entity-detail"),
    path("entities/<slug:slug>/fields/", views.FieldListCreateView.as_view(), name="field-list"),
    path("entities/<slug:slug>/fields/<slug:field_slug>/", views.FieldDetailView.as_view(), name="field-detail"),
    path("entities/<slug:slug>/impact/", views.EntityImpactView.as_view(), name="entity-impact"),
    path("entities/<slug:slug>/fields/<slug:field_slug>/impact/", views.FieldImpactView.as_view(), name="field-impact"),
    path("entities/<slug:slug>/promote-field/", views.PromoteFieldView.as_view(), name="promote-field"),
    path("entities/<slug:slug>/demote-field/", views.DemoteFieldView.as_view(), name="demote-field"),
    path("entities/<slug:slug>/schema-versions/", views.SchemaVersionListView.as_view(), name="version-list"),
    path("entities/<slug:slug>/schema-versions/<int:version>/rollback/",
         views.SchemaRollbackView.as_view(), name="version-rollback"),
    # Form Schema API (Phase 1.26)
    path("entities/<slug:slug>/form-schema/", views.FormSchemaView.as_view(), name="form-schema"),
    path("entities/<slug:slug>/forms/", views.FormListCreateView.as_view(), name="form-list"),
    path("entities/<slug:slug>/forms/<uuid:form_id>/", views.FormDetailView.as_view(), name="form-detail"),
]
