from django.urls import path

from . import views as v

app_name = "dependency"

urlpatterns = [
    path("object-types/", v.ObjectTypesView.as_view(), name="object_types"),
    path("analyze/", v.AnalyzeView.as_view(), name="analyze"),
    path("graph/", v.GraphView.as_view(), name="graph"),
    path("safe-delete/", v.SafeDeleteView.as_view(), name="safe_delete"),
    path("change-preview/", v.ChangePreviewView.as_view(), name="change_preview"),
    path("promotion-precheck/", v.PromotionPrecheckView.as_view(), name="promotion_precheck"),
    path("executive-summary/", v.ExecutiveSummaryView.as_view(), name="executive_summary"),
]
