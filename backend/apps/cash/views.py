"""
Cash Management & Bank Reconciliation REST API at /api/v1/cash/.

Configuration + operations (accounts, transfers, statement import, reconciliation, matching) are
owner/admin gated; cash-position + reconciliation reads available to any member. Workspace-scoped.
Package-independent — every package consumes this; none ships a cash module.
"""
import uuid

from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import BankAccount, BankReconciliation
from .services import CashError, CashService, MatchingService, ReconciliationService

_ADMIN_ROLES = {"owner", "admin"}


def _ws(request) -> uuid.UUID:
    ws = getattr(request, "workspace_id", None)
    if not ws:
        raise PermissionDenied("No active workspace. Send the X-Workspace-Slug header.")
    return ws if isinstance(ws, uuid.UUID) else uuid.UUID(str(ws))


def _require_admin(request):
    m = getattr(request, "workspace_member", None)
    if m is None or getattr(m, "role", "") not in _ADMIN_ROLES:
        raise PermissionDenied("Cash operations require an admin or owner role.")


def _uid(request):
    return getattr(request.user, "id", None)


def _call(fn, **kw):
    try:
        return fn(**kw)
    except CashError as exc:
        raise ValidationError(str(exc)) from exc


class AccountList(APIView):
    def get(self, request):
        qs = BankAccount.objects.filter(workspace_id=_ws(request)).order_by("code")
        return Response([{"id": str(a.id), "code": a.code, "name": a.name,
                          "account_type": a.account_type, "gl_account_code": a.gl_account_code,
                          "currency": a.currency, "is_active": a.is_active} for a in qs])

    def post(self, request):
        _require_admin(request)
        d = request.data or {}
        if not d.get("code"):
            raise ValidationError("code required.")
        acct = CashService.ensure_account(
            workspace_id=_ws(request), code=d["code"], name=d.get("name", ""),
            account_type=d.get("account_type", "bank"), gl_account_code=d.get("gl_account_code", ""),
            currency=d.get("currency", ""), bank_name=d.get("bank_name", ""),
            account_number=d.get("account_number", ""), actor_id=_uid(request))
        return Response({"id": str(acct.id), "code": acct.code}, status=201)


class CashPositionView(APIView):
    def get(self, request):
        return Response(CashService.cash_position(_ws(request)))


class TransferView(APIView):
    def post(self, request):
        _require_admin(request)
        d = request.data or {}
        xfer = _call(CashService.post_transfer, workspace_id=_ws(request),
                     from_account=d.get("from_account"), to_account=d.get("to_account"),
                     amount=d.get("amount"), transfer_date=d.get("transfer_date"),
                     memo=d.get("memo", ""), external_ref=d.get("external_ref", ""),
                     actor_id=_uid(request))
        return Response({"id": str(xfer.id), "number": xfer.number,
                         "journal_entry_id": str(xfer.journal_entry_id)
                         if xfer.journal_entry_id else None}, status=201)


class StatementImportView(APIView):
    def post(self, request):
        _require_admin(request)
        d = request.data or {}
        stmt = _call(ReconciliationService.import_statement, workspace_id=_ws(request),
                     bank_account=d.get("bank_account"), lines=d.get("lines", []),
                     statement_ref=d.get("statement_ref", ""),
                     statement_date=d.get("statement_date"),
                     opening_balance=d.get("opening_balance", 0),
                     closing_balance=d.get("closing_balance", 0),
                     external_ref=d.get("external_ref", ""), actor_id=_uid(request))
        return Response({"id": str(stmt.id), "lines": stmt.lines.count()}, status=201)


class ReconciliationList(APIView):
    def get(self, request):
        qs = BankReconciliation.objects.filter(workspace_id=_ws(request)).order_by("-created_at")[:200]
        return Response([{"id": str(r.id), "bank_account": str(r.bank_account_id),
                          "status": r.status, "book_balance": str(r.book_balance),
                          "statement_balance": str(r.statement_balance),
                          "difference": str(r.difference)} for r in qs])

    def post(self, request):
        _require_admin(request)
        d = request.data or {}
        rec = _call(ReconciliationService.open_reconciliation, workspace_id=_ws(request),
                    bank_account=d.get("bank_account"), statement=d.get("statement"),
                    reconciliation_date=d.get("reconciliation_date"), actor_id=_uid(request))
        return Response({"id": str(rec.id), "difference": str(rec.difference)}, status=201)


class ReconciliationDetail(APIView):
    def get(self, request, pk):
        rec = BankReconciliation.objects.filter(workspace_id=_ws(request), id=pk).first()
        if rec is None:
            raise PermissionDenied("Reconciliation not found.")
        return Response({"id": str(rec.id), "status": rec.status,
                         "book_balance": str(rec.book_balance),
                         "statement_balance": str(rec.statement_balance),
                         "reconciled_balance": str(rec.reconciled_balance),
                         "difference": str(rec.difference),
                         **ReconciliationService.outstanding_items(_ws(request), rec)})


class AutoMatchView(APIView):
    def post(self, request, pk):
        _require_admin(request)
        d = request.data or {}
        return Response(_call(MatchingService.auto_match, workspace_id=_ws(request),
                              reconciliation_id=pk,
                              amount_tolerance=d.get("amount_tolerance", 0),
                              date_tolerance_days=int(d.get("date_tolerance_days", 5)),
                              actor_id=_uid(request)))


class ManualMatchView(APIView):
    def post(self, request, pk):
        _require_admin(request)
        d = request.data or {}
        return Response(_call(MatchingService.match_group, workspace_id=_ws(request),
                              reconciliation_id=pk,
                              statement_line_ids=d.get("statement_line_ids", []),
                              journal_line_ids=d.get("journal_line_ids", []),
                              amount=d.get("amount"), tolerance=d.get("tolerance", 0),
                              actor_id=_uid(request)))


class CompleteView(APIView):
    def post(self, request, pk):
        _require_admin(request)
        d = request.data or {}
        rec = _call(ReconciliationService.complete, workspace_id=_ws(request),
                    reconciliation_id=pk, tolerance=d.get("tolerance", 0), actor_id=_uid(request))
        return Response({"id": str(rec.id), "status": rec.status})
