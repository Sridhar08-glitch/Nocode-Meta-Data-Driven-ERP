"""Revenue Recognition URLs at /api/v1/revenue/."""
from django.urls import path

from . import views

urlpatterns = [
    path("schedules/", views.ScheduleList.as_view(), name="revenue-schedules"),
    path("schedules/<uuid:pk>/", views.ScheduleDetail.as_view(), name="revenue-schedule"),
    path("schedules/<uuid:pk>/cancel/", views.ScheduleCancel.as_view(), name="revenue-cancel"),
    path("recognize/", views.RecognizeView.as_view(), name="revenue-recognize"),
]
