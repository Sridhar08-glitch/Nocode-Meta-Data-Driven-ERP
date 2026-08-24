"""Financial Statements URLs at /api/v1/financial-reports/."""
from django.urls import path

from . import views

urlpatterns = [
    path("trial-balance/", views.TrialBalanceView.as_view(), name="fr-trial-balance"),
    path("balance-sheet/", views.BalanceSheetView.as_view(), name="fr-balance-sheet"),
    path("profit-and-loss/", views.ProfitAndLossView.as_view(), name="fr-pnl"),
    path("cash-flow/", views.CashFlowView.as_view(), name="fr-cash-flow"),
    path("general-ledger/", views.GeneralLedgerView.as_view(), name="fr-gl"),
    path("ar-aging/", views.ArAgingView.as_view(), name="fr-ar-aging"),
    path("ap-aging/", views.ApAgingView.as_view(), name="fr-ap-aging"),
    path("tax-summary/", views.TaxSummaryView.as_view(), name="fr-tax-summary"),
]
