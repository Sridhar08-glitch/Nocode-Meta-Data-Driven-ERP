"""
Financial Statements REST API at /api/v1/financial-reports/.

Standard statements over the single GL — Trial Balance, Balance Sheet, P&L, Cash Flow, General
Ledger, AR/AP Aging, plus the Tax return (reuses the Tax Engine). Reads are available to any
workspace member (statements are read-only projections of posted books). Workspace-scoped.
"""
import datetime as _dt
import uuid

from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import StatementService


def _ws(request) -> uuid.UUID:
    ws = getattr(request, "workspace_id", None)
    if not ws:
        raise PermissionDenied("No active workspace. Send the X-Workspace-Slug header.")
    return ws if isinstance(ws, uuid.UUID) else uuid.UUID(str(ws))


def _date(request, key):
    raw = request.query_params.get(key)
    if not raw:
        return None
    try:
        return _dt.date.fromisoformat(raw)
    except ValueError:
        return None


class TrialBalanceView(APIView):
    def get(self, request):
        return Response(StatementService.trial_balance(_ws(request), as_of=_date(request, "as_of")))


class BalanceSheetView(APIView):
    def get(self, request):
        return Response(StatementService.balance_sheet(_ws(request), as_of=_date(request, "as_of")))


class ProfitAndLossView(APIView):
    def get(self, request):
        return Response(StatementService.profit_and_loss(
            _ws(request), from_date=_date(request, "from"), to_date=_date(request, "to")))


class CashFlowView(APIView):
    def get(self, request):
        return Response(StatementService.cash_flow(
            _ws(request), from_date=_date(request, "from"), to_date=_date(request, "to")))


class GeneralLedgerView(APIView):
    def get(self, request):
        code = request.query_params.get("account")
        if not code:
            raise PermissionDenied("account query param required.")
        return Response(StatementService.general_ledger(
            _ws(request), account_code=code,
            from_date=_date(request, "from"), to_date=_date(request, "to")))


class ArAgingView(APIView):
    def get(self, request):
        return Response(StatementService.ar_aging(_ws(request), as_of=_date(request, "as_of")))


class ApAgingView(APIView):
    def get(self, request):
        return Response(StatementService.ap_aging(_ws(request), as_of=_date(request, "as_of")))


class TaxSummaryView(APIView):
    def get(self, request):
        from apps.taxes.services import TaxService
        return Response(TaxService.tax_summary(
            _ws(request), from_date=request.query_params.get("from"),
            to_date=request.query_params.get("to")))
