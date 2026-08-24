from django.urls import path

from . import views as v

app_name = "collections"

urlpatterns = [
    path("setup/", v.SetupView.as_view(), name="setup"),
    path("plans/", v.PlanList.as_view(), name="plan_list"),
    path("plans/<uuid:pk>/", v.PlanDetail.as_view(), name="plan_detail"),
    path("plans/<uuid:pk>/record-payment/", v.PlanRecordPayment.as_view(), name="record_payment"),
    path("installments/<uuid:pk>/charge-late-fee/",
         v.InstallmentChargeLateFee.as_view(), name="charge_late_fee"),
    path("run/late-fees/", v.RunLateFees.as_view(), name="run_late_fees"),
    path("run/reminders/", v.RunReminders.as_view(), name="run_reminders"),
    path("dashboard/", v.Dashboard.as_view(), name="dashboard"),
]
