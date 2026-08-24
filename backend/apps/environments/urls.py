from django.urls import path

from . import views as v

app_name = "environments"

urlpatterns = [
    path("", v.EnvironmentsView.as_view(), name="environments"),
    path("packages/", v.PackageList.as_view(), name="packages"),
    path("packages/<uuid:pk>/", v.PackageDetail.as_view(), name="package_detail"),
    path("packages/<uuid:pk>/approve/", v.PackageApprove.as_view(), name="package_approve"),
    path("packages/<uuid:pk>/execute/", v.PackageExecute.as_view(), name="package_execute"),
    path("packages/<uuid:pk>/rollback/", v.PackageRollback.as_view(), name="package_rollback"),
    path("dashboard/", v.PromotionDashboard.as_view(), name="dashboard"),
]
