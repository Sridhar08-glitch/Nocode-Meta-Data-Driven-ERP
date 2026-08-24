from django.urls import path

from . import views

app_name = "hr"

urlpatterns = [
    path("setup/", views.SetupView.as_view(), name="setup"),
    path("interviews/<uuid:record_id>/complete/",
         views.InterviewCompleteView.as_view(), name="complete_interview"),
    path("offers/<uuid:record_id>/accept/",
         views.OfferAcceptView.as_view(), name="accept_offer"),
    path("candidates/<uuid:record_id>/hire/",
         views.CandidateHireView.as_view(), name="hire_candidate"),
    path("leave-requests/<uuid:record_id>/approve/",
         views.LeaveApproveView.as_view(), name="approve_leave"),
    path("leave-requests/<uuid:record_id>/reject/",
         views.LeaveRejectView.as_view(), name="reject_leave"),
    path("performance-reviews/<uuid:record_id>/complete/",
         views.PerformanceCompleteView.as_view(), name="complete_performance"),
    path("employees/<uuid:record_id>/promote/",
         views.EmployeePromoteView.as_view(), name="promote_employee"),
    path("employees/<uuid:record_id>/transfer/",
         views.EmployeeTransferView.as_view(), name="transfer_employee"),
    path("employees/<uuid:record_id>/offboard/",
         views.EmployeeOffboardView.as_view(), name="offboard_employee"),
    path("<slug:entity_slug>/", views.DocumentCreateView.as_view(), name="create_document"),
]
