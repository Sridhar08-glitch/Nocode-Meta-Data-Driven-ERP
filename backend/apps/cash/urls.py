"""Cash Management & Bank Reconciliation URLs at /api/v1/cash/."""
from django.urls import path

from . import views

urlpatterns = [
    path("accounts/", views.AccountList.as_view(), name="cash-accounts"),
    path("position/", views.CashPositionView.as_view(), name="cash-position"),
    path("transfers/", views.TransferView.as_view(), name="cash-transfers"),
    path("statements/import/", views.StatementImportView.as_view(), name="cash-statement-import"),
    path("reconciliations/", views.ReconciliationList.as_view(), name="cash-reconciliations"),
    path("reconciliations/<uuid:pk>/", views.ReconciliationDetail.as_view(), name="cash-recon"),
    path("reconciliations/<uuid:pk>/auto-match/", views.AutoMatchView.as_view(),
         name="cash-auto-match"),
    path("reconciliations/<uuid:pk>/manual-match/", views.ManualMatchView.as_view(),
         name="cash-manual-match"),
    path("reconciliations/<uuid:pk>/complete/", views.CompleteView.as_view(), name="cash-complete"),
]
