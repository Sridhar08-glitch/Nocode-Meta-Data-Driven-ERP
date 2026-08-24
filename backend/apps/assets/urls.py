from django.urls import path

from . import views as v

app_name = "assets"

urlpatterns = [
    path("setup/", v.SetupView.as_view(), name="setup"),

    path("assets/", v.AssetCreate.as_view(), name="asset_create"),
    path("assets/<uuid:pk>/assign/", v.AssetAssign.as_view(), name="asset_assign"),
    path("assets/<uuid:pk>/return/", v.AssetReturn.as_view(), name="asset_return"),
    path("assets/<uuid:pk>/transfer/", v.AssetTransfer.as_view(), name="asset_transfer"),
    path("assets/<uuid:pk>/inspect/", v.AssetInspect.as_view(), name="asset_inspect"),
    path("assets/<uuid:pk>/retire/", v.AssetRetire.as_view(), name="asset_retire"),
    path("work-orders/<uuid:pk>/complete/", v.WorkOrderComplete.as_view(), name="wo_complete"),

    path("depreciation/schedules/", v.ScheduleList.as_view(), name="schedules"),
    path("depreciation/schedules/<uuid:pk>/run/", v.ScheduleRun.as_view(), name="schedule_run"),
    path("depreciation/schedules/<uuid:pk>/entries/",
         v.ScheduleEntries.as_view(), name="schedule_entries"),
    path("depreciation/run-all/", v.DepreciationRunAll.as_view(), name="depreciation_run_all"),
    path("depreciation/preview/", v.DepreciationPreview.as_view(), name="depreciation_preview"),

    path("disposals/", v.DisposalCreate.as_view(), name="disposal_create"),
    path("disposals/list/", v.DisposalList.as_view(), name="disposal_list"),
]
