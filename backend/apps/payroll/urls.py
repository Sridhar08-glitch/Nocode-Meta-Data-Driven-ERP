from django.urls import path

from . import views as v

app_name = "payroll"

urlpatterns = [
    path("settings/", v.SettingsView.as_view(), name="settings"),
    path("setup/", v.SetupView.as_view(), name="setup"),

    path("calendars/", v.CalendarList.as_view(), name="calendars"),
    path("calendars/<uuid:pk>/", v.CalendarDetail.as_view(), name="calendar_detail"),

    path("salary-structures/", v.StructureList.as_view(), name="structures"),
    path("salary-structures/<uuid:pk>/", v.StructureDetail.as_view(), name="structure_detail"),
    path("components/", v.ComponentList.as_view(), name="components"),
    path("components/<uuid:pk>/", v.ComponentDetail.as_view(), name="component_detail"),
    path("assignments/", v.AssignmentList.as_view(), name="assignments"),
    path("profiles/", v.ProfileList.as_view(), name="profiles"),
    path("contracts/", v.ContractList.as_view(), name="contracts"),

    path("periods/", v.PeriodList.as_view(), name="periods"),
    path("periods/<uuid:pk>/", v.PeriodDetail.as_view(), name="period_detail"),
    path("periods/<uuid:pk>/open/", v.PeriodOpen.as_view(), name="period_open"),
    path("periods/<uuid:pk>/close/", v.PeriodClose.as_view(), name="period_close"),
    path("periods/<uuid:pk>/lock/", v.PeriodLock.as_view(), name="period_lock"),
    path("periods/<uuid:pk>/reopen/", v.PeriodReopen.as_view(), name="period_reopen"),

    path("runs/", v.RunList.as_view(), name="runs"),
    path("runs/create/", v.RunCreate.as_view(), name="run_create"),
    path("runs/<uuid:pk>/", v.RunDetail.as_view(), name="run_detail"),
    path("runs/<uuid:pk>/calculate/", v.RunCalculate.as_view(), name="run_calculate"),
    path("runs/<uuid:pk>/approve/", v.RunApprove.as_view(), name="run_approve"),
    path("runs/<uuid:pk>/post/", v.RunPost.as_view(), name="run_post"),
    path("runs/<uuid:pk>/lock/", v.RunLock.as_view(), name="run_lock"),
    path("runs/<uuid:pk>/register/", v.RunRegister.as_view(), name="run_register"),
    path("runs/<uuid:pk>/summary/", v.RunSummary.as_view(), name="run_summary"),

    path("payslips/", v.PayslipList.as_view(), name="payslips"),
    path("payslips/<uuid:pk>/", v.PayslipDetail.as_view(), name="payslip_detail"),

    path("loans/", v.LoanList.as_view(), name="loans"),
    path("advances/", v.AdvanceList.as_view(), name="advances"),
    path("overtime/", v.OvertimeCreate.as_view(), name="overtime_create"),
    path("overtime/list/", v.OvertimeList.as_view(), name="overtime_list"),
    path("overtime/<uuid:pk>/approve/", v.OvertimeApprove.as_view(), name="overtime_approve"),
    path("adjustments/", v.AdjustmentCreate.as_view(), name="adjustment_create"),
    path("adjustments/list/", v.AdjustmentList.as_view(), name="adjustment_list"),
    path("final-settlements/", v.FinalSettlementCreate.as_view(), name="final_settlement"),
]
