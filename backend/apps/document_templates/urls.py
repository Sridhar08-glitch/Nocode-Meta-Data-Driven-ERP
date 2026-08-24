"""Document-template routes (Phase 1.33) — mounted at /api/v1/templates/documents/."""
from django.urls import path

from . import views

app_name = "document_templates"

urlpatterns = [
    path("", views.DocumentTemplateListCreateView.as_view(), name="list-create"),
    path("<uuid:pk>/", views.DocumentTemplateDetailView.as_view(), name="detail"),
    path("<uuid:pk>/render/", views.DocumentTemplateRenderView.as_view(), name="render"),
]
