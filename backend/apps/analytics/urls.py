from django.urls import path

from . import views as v

app_name = "analytics"

urlpatterns = [
    path("setup/", v.SetupView.as_view(), name="setup"),
    path("kpis/", v.KPIList.as_view(), name="kpis"),
    path("kpis/evaluate/", v.KPIEvaluateAll.as_view(), name="kpi_evaluate_all"),
    path("kpis/<uuid:pk>/", v.KPIDetail.as_view(), name="kpi_detail"),
    path("kpis/<slug:code>/value/", v.KPIEvaluate.as_view(), name="kpi_value"),
    path("kpis/<slug:code>/trend/", v.TrendView.as_view(), name="kpi_trend"),
    path("scorecards/<slug:role>/", v.Scorecard.as_view(), name="scorecard"),
    path("snapshot/", v.SnapshotView.as_view(), name="snapshot"),
    path("alerts/check/", v.AlertsCheck.as_view(), name="alerts_check"),
]
