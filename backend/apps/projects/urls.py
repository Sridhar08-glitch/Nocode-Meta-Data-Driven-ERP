from django.urls import path

from . import views as v

app_name = "projects"

urlpatterns = [
    path("setup/", v.SetupView.as_view(), name="setup"),

    path("projects/<uuid:pk>/start/", v.ProjectStart.as_view(), name="project_start"),
    path("projects/<uuid:pk>/complete/", v.ProjectComplete.as_view(), name="project_complete"),
    path("projects/<uuid:pk>/budget/approve/",
         v.ProjectBudgetApprove.as_view(), name="budget_approve"),
    path("projects/<uuid:pk>/baseline/", v.ProjectBaselineView.as_view(), name="baseline"),
    path("projects/<uuid:pk>/rollup/", v.ProjectRollup.as_view(), name="rollup"),
    path("projects/<uuid:pk>/financials/", v.ProjectFinancials.as_view(), name="financials"),
    path("projects/<uuid:pk>/schedule/", v.ProjectScheduleView.as_view(), name="schedule"),

    path("tasks/<uuid:pk>/complete/", v.TaskComplete.as_view(), name="task_complete"),
    path("milestones/<uuid:pk>/complete/",
         v.MilestoneComplete.as_view(), name="milestone_complete"),
    path("timesheets/<uuid:pk>/approve/", v.TimesheetApprove.as_view(), name="timesheet_approve"),
    path("expenses/<uuid:pk>/approve/", v.ExpenseApprove.as_view(), name="expense_approve"),
    path("change-requests/<uuid:pk>/approve/",
         v.ChangeRequestApprove.as_view(), name="cr_approve"),
    path("deliverables/<uuid:pk>/approve/",
         v.DeliverableApprove.as_view(), name="deliverable_approve"),

    path("cost-entries/", v.CostEntryView.as_view(), name="cost_entries"),
    path("resources/utilization/", v.ResourceUtilization.as_view(), name="utilization"),
    path("resources/capacity/", v.ResourceCapacity.as_view(), name="capacity"),

    path("<slug:entity_slug>/", v.DocumentCreate.as_view(), name="create_document"),
]
