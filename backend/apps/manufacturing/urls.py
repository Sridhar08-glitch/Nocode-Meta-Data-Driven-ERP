from django.urls import path

from . import views as v

app_name = "manufacturing"

urlpatterns = [
    path("setup/", v.SetupView.as_view(), name="setup"),

    path("work-centers/", v.WorkCenterList.as_view(), name="work_centers"),
    path("boms/", v.BomList.as_view(), name="boms"),
    path("boms/<uuid:pk>/approve/", v.BomApprove.as_view(), name="bom_approve"),
    path("boms/explode/", v.BomExplode.as_view(), name="bom_explode"),
    path("components/", v.ComponentList.as_view(), name="components"),
    path("routings/", v.RoutingList.as_view(), name="routings"),
    path("routing-steps/", v.RoutingStepList.as_view(), name="routing_steps"),

    path("orders/", v.OrderList.as_view(), name="orders"),
    path("orders/create/", v.OrderCreate.as_view(), name="order_create"),
    path("orders/<uuid:pk>/release/", v.OrderRelease.as_view(), name="order_release"),
    path("orders/<uuid:pk>/issue/", v.OrderIssue.as_view(), name="order_issue"),
    path("orders/<uuid:pk>/complete/", v.OrderComplete.as_view(), name="order_complete"),
    path("orders/<uuid:pk>/close/", v.OrderClose.as_view(), name="order_close"),
    path("orders/<uuid:pk>/oee/", v.OrderOEE.as_view(), name="order_oee"),
    path("operations/", v.OperationList.as_view(), name="operations"),
    path("operations/<uuid:pk>/complete/", v.OperationComplete.as_view(), name="operation_complete"),
    path("reservations/", v.ReservationList.as_view(), name="reservations"),

    path("mrp/run/", v.MRPRunView.as_view(), name="mrp_run"),
    path("costing/standard/", v.StandardCostView.as_view(), name="standard_cost"),
    path("lots/<uuid:pk>/trace/", v.LotTrace.as_view(), name="lot_trace"),
    path("quality-checks/", v.QualityCheckCreate.as_view(), name="quality_check"),
    path("ncrs/", v.NcrCreate.as_view(), name="ncr_create"),
]
