from django.urls import path

from . import views

app_name = "ledger"

urlpatterns = [
    # Chart of accounts
    path("accounts/", views.AccountListCreateView.as_view(), name="account-list"),
    path("accounts/<uuid:acct_id>/", views.AccountDetailView.as_view(), name="account-detail"),
    # Fiscal periods
    path("periods/", views.PeriodListCreateView.as_view(), name="period-list"),
    path("periods/<uuid:period_id>/", views.PeriodDetailView.as_view(), name="period-detail"),
    path("periods/<uuid:period_id>/close/", views.PeriodCloseView.as_view(), name="period-close"),
    path("periods/<uuid:period_id>/reopen/", views.PeriodReopenView.as_view(), name="period-reopen"),
    # Journal entries
    path("entries/", views.JournalEntryListCreateView.as_view(), name="entry-list"),
    path("entries/<uuid:entry_id>/", views.JournalEntryDetailView.as_view(), name="entry-detail"),
    path("entries/<uuid:entry_id>/post/", views.JournalEntryPostView.as_view(), name="entry-post"),
    path("entries/<uuid:entry_id>/reverse/", views.JournalEntryReverseView.as_view(), name="entry-reverse"),
    # Posting rules (event → journal template)
    path("posting-rules/", views.PostingRuleListCreateView.as_view(), name="rule-list"),
    path("posting-rules/<uuid:rule_id>/", views.PostingRuleDetailView.as_view(), name="rule-detail"),
    # Setup (Phase P2.3)
    path("seed-chart/", views.SeedChartView.as_view(), name="seed-chart"),
    path("fiscal-years/", views.GenerateFiscalYearView.as_view(), name="generate-fiscal-year"),
    # Financial reports (Phase P2.3)
    path("reports/trial-balance/", views.TrialBalanceView.as_view(), name="trial-balance"),
    path("reports/general-ledger/", views.GeneralLedgerView.as_view(), name="general-ledger"),
    path("reports/profit-loss/", views.ProfitLossView.as_view(), name="profit-loss"),
    path("reports/balance-sheet/", views.BalanceSheetView.as_view(), name="balance-sheet"),
]
