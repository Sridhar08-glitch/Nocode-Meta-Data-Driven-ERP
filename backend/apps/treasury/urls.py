"""Treasury Platform URLs at /api/v1/treasury/ (F12)."""
from django.urls import path

from . import views

urlpatterns = [
    path("counterparties/", views.CounterpartyListView.as_view(), name="treasury-counterparties"),
    path("facilities/", views.FacilityListView.as_view(), name="treasury-facilities"),
    path("facilities/<uuid:facility_id>/<str:action>/", views.FacilityActionView.as_view(),
         name="treasury-facility-action"),
    path("investments/", views.InvestmentListView.as_view(), name="treasury-investments"),
    path("investments/<uuid:investment_id>/<str:action>/", views.InvestmentActionView.as_view(),
         name="treasury-investment-action"),
    path("transactions/", views.TransactionListView.as_view(), name="treasury-transactions"),
    path("pay-interest-due/", views.PayInterestDueView.as_view(), name="treasury-pay-interest"),
    # computed reports (no stored duplication)
    path("schedules/interest/<str:kind>/<uuid:deal_id>/", views.InterestScheduleView.as_view(),
         name="treasury-interest-schedule"),
    path("schedules/debt/", views.DebtScheduleView.as_view(), name="treasury-debt-schedule"),
    path("schedules/maturity/", views.MaturityScheduleView.as_view(),
         name="treasury-maturity-schedule"),
    path("liquidity/", views.LiquidityPositionView.as_view(), name="treasury-liquidity"),
    path("exposure/", views.CounterpartyExposureView.as_view(), name="treasury-exposure"),
    path("forecast/", views.ForecastView.as_view(), name="treasury-forecast"),
]
