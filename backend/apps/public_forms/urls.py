"""Public Forms API routes (PROJECT_HANDBOOK.md §33.2)."""
from django.urls import path

from . import views

app_name = "public_forms"

urlpatterns = [
    # Authenticated admin endpoints
    path("forms/", views.FormListView.as_view(), name="form-list"),
    path("forms/<uuid:pk>/", views.FormDetailView.as_view(), name="form-detail"),
    path("forms/<uuid:pk>/submissions/",
         views.FormSubmissionListView.as_view(), name="submission-list"),
    path("forms/<uuid:pk>/submissions/<uuid:sub_id>/",
         views.FormSubmissionDetailView.as_view(), name="submission-detail"),
    path("forms/<uuid:pk>/submissions/<uuid:sub_id>/approve/",
         views.FormSubmissionApproveView.as_view(), name="submission-approve"),
    path("forms/<uuid:pk>/submissions/<uuid:sub_id>/reject/",
         views.FormSubmissionRejectView.as_view(), name="submission-reject"),
    # Public, unauthenticated (schema for rendering + submission)
    path("<uuid:form_id>/schema/", views.PublicFormSchemaView.as_view(), name="public-schema"),
    path("<uuid:form_id>/submit/", views.PublicFormSubmitView.as_view(), name="submit"),
]
