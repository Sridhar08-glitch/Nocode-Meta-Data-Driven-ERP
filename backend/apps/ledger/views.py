"""
General Ledger REST API (Phase P2.2) at /api/v1/ledger/.

Finance is sensitive: all writes (accounts, periods, journal posting/reversal, posting rules)
require owner/admin; any member may read. Posted entries are immutable — there is no edit/delete,
only ``/post/`` (from draft) and ``/reverse/``.
"""
import uuid

from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from . import reports as report_svc
from . import seeding
from .models import AccountingPeriod, JournalEntry, LedgerAccount, PostingRule
from .serializers import (
    AccountingPeriodSerializer,
    JournalEntrySerializer,
    LedgerAccountSerializer,
    PostingRuleSerializer,
)
from .services import GLBus, LedgerError


def _parse_date(value):
    import datetime as _dt
    if not value:
        return None
    try:
        return _dt.date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValidationError(f"Invalid date {value!r} (use YYYY-MM-DD).") from exc

_ADMIN_ROLES = {"owner", "admin"}


def _ws(request) -> uuid.UUID:
    ws = getattr(request, "workspace_id", None)
    if not ws:
        raise PermissionDenied("No active workspace. Send the X-Workspace-Slug header.")
    return ws if isinstance(ws, uuid.UUID) else uuid.UUID(str(ws))


def _member(request):
    m = getattr(request, "workspace_member", None)
    if m is None:
        raise PermissionDenied("No workspace membership for this request.")
    return m


def _require_admin(request):
    if getattr(_member(request), "role", "") not in _ADMIN_ROLES:
        raise PermissionDenied("General-ledger management requires an admin or owner role.")


def _uid(request):
    return getattr(request.user, "id", None)


# ── Accounts ──────────────────────────────────────────────────────────────────
class AccountListCreateView(APIView):
    def get(self, request):
        _member(request)
        qs = LedgerAccount.objects.filter(workspace_id=_ws(request)).order_by("code")
        if request.query_params.get("type"):
            qs = qs.filter(account_type=request.query_params["type"])
        return Response(LedgerAccountSerializer(qs, many=True).data)

    def post(self, request):
        _require_admin(request)
        ws = _ws(request)
        ser = LedgerAccountSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if LedgerAccount.objects.filter(workspace_id=ws, code=ser.validated_data["code"]).exists():
            raise ValidationError(f"Account {ser.validated_data['code']!r} already exists.")
        obj = ser.save(workspace_id=ws, created_by=_uid(request))
        return Response(LedgerAccountSerializer(obj).data, status=201)


class AccountDetailView(APIView):
    def _get(self, request, acct_id) -> LedgerAccount:
        obj = LedgerAccount.objects.filter(workspace_id=_ws(request), id=acct_id).first()
        if obj is None:
            raise NotFound("Account not found.")
        return obj

    def get(self, request, acct_id):
        _member(request)
        return Response(LedgerAccountSerializer(self._get(request, acct_id)).data)

    def patch(self, request, acct_id):
        _require_admin(request)
        obj = self._get(request, acct_id)
        ser = LedgerAccountSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(LedgerAccountSerializer(obj).data)

    def delete(self, request, acct_id):
        _require_admin(request)
        obj = self._get(request, acct_id)
        if obj.lines.exists():
            raise ValidationError("Account has postings; deactivate it instead of deleting.")
        obj.delete()
        return Response(status=204)


# ── Periods ───────────────────────────────────────────────────────────────────
class PeriodListCreateView(APIView):
    def get(self, request):
        _member(request)
        qs = AccountingPeriod.objects.filter(workspace_id=_ws(request)).order_by("-start_date")
        return Response(AccountingPeriodSerializer(qs, many=True).data)

    def post(self, request):
        _require_admin(request)
        ws = _ws(request)
        ser = AccountingPeriodSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if AccountingPeriod.objects.filter(workspace_id=ws, code=ser.validated_data["code"]).exists():
            raise ValidationError(f"Period {ser.validated_data['code']!r} already exists.")
        obj = ser.save(workspace_id=ws)
        return Response(AccountingPeriodSerializer(obj).data, status=201)


class PeriodDetailView(APIView):
    def _get(self, request, period_id) -> AccountingPeriod:
        obj = AccountingPeriod.objects.filter(workspace_id=_ws(request), id=period_id).first()
        if obj is None:
            raise NotFound("Period not found.")
        return obj

    def get(self, request, period_id):
        _member(request)
        return Response(AccountingPeriodSerializer(self._get(request, period_id)).data)

    def patch(self, request, period_id):
        _require_admin(request)
        obj = self._get(request, period_id)
        ser = AccountingPeriodSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(AccountingPeriodSerializer(obj).data)


class PeriodCloseView(APIView):
    def post(self, request, period_id):
        from django.utils import timezone
        _require_admin(request)
        obj = AccountingPeriod.objects.filter(workspace_id=_ws(request), id=period_id).first()
        if obj is None:
            raise NotFound("Period not found.")
        lock = bool(request.data.get("lock")) if isinstance(request.data, dict) else False
        obj.status = AccountingPeriod.LOCKED if lock else AccountingPeriod.CLOSED
        obj.closed_at = timezone.now()
        obj.closed_by = _uid(request)
        obj.save(update_fields=["status", "closed_at", "closed_by", "updated_at"])
        return Response(AccountingPeriodSerializer(obj).data)


class PeriodReopenView(APIView):
    def post(self, request, period_id):
        _require_admin(request)
        obj = AccountingPeriod.objects.filter(workspace_id=_ws(request), id=period_id).first()
        if obj is None:
            raise NotFound("Period not found.")
        if obj.status == AccountingPeriod.LOCKED:
            raise ValidationError("Locked periods cannot be reopened.")
        obj.status = AccountingPeriod.OPEN
        obj.closed_at = None
        obj.closed_by = None
        obj.save(update_fields=["status", "closed_at", "closed_by", "updated_at"])
        return Response(AccountingPeriodSerializer(obj).data)


# ── Journal entries ─────────────────────────────────────────────────────────────
class JournalEntryListCreateView(APIView):
    def get(self, request):
        _member(request)
        qs = JournalEntry.objects.filter(workspace_id=_ws(request))
        if request.query_params.get("status"):
            qs = qs.filter(status=request.query_params["status"])
        if request.query_params.get("source_module"):
            qs = qs.filter(source_module=request.query_params["source_module"])
        qs = qs.order_by("-date", "-created_at")[:500]
        return Response(JournalEntrySerializer(qs, many=True).data)

    def post(self, request):
        """Create a draft entry. Pass ``post=true`` to create-and-post in one step."""
        _require_admin(request)
        ws = _ws(request)
        data = request.data if isinstance(request.data, dict) else {}
        date = data.get("date")
        if not date:
            raise ValidationError("date is required.")
        lines = data.get("lines") or []
        try:
            if data.get("post"):
                entry = GLBus.post(
                    ws, date=date, lines=lines, memo=data.get("memo", ""),
                    currency=data.get("currency", ""), source_module=data.get("source_module", "manual"),
                    source_ref=data.get("source_ref", ""), actor_id=_uid(request))
            else:
                entry = GLBus.create_draft(
                    ws, date=date, lines=lines, memo=data.get("memo", ""),
                    currency=data.get("currency", ""), source_module=data.get("source_module", "manual"),
                    source_ref=data.get("source_ref", ""), actor_id=_uid(request))
        except LedgerError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(JournalEntrySerializer(entry).data, status=201)


class JournalEntryDetailView(APIView):
    def _get(self, request, entry_id) -> JournalEntry:
        obj = JournalEntry.objects.filter(workspace_id=_ws(request), id=entry_id).first()
        if obj is None:
            raise NotFound("Journal entry not found.")
        return obj

    def get(self, request, entry_id):
        _member(request)
        return Response(JournalEntrySerializer(self._get(request, entry_id)).data)

    def patch(self, request, entry_id):
        """Edit a DRAFT entry's header/lines. Posted entries are immutable."""
        _require_admin(request)
        ws = _ws(request)
        obj = self._get(request, entry_id)
        if obj.status != JournalEntry.DRAFT:
            raise ValidationError("Only draft entries can be edited; posted entries are immutable.")
        data = request.data if isinstance(request.data, dict) else {}
        for f in ("date", "memo", "currency", "source_module", "source_ref"):
            if f in data:
                setattr(obj, f, data[f])
        obj.save()
        if "lines" in data:
            try:
                GLBus._write_lines(ws, obj, data["lines"], validate=False)
            except LedgerError as exc:
                raise ValidationError(str(exc)) from exc
        return Response(JournalEntrySerializer(obj).data)

    def delete(self, request, entry_id):
        _require_admin(request)
        obj = self._get(request, entry_id)
        if obj.status != JournalEntry.DRAFT:
            raise ValidationError("Only draft entries can be deleted; posted entries are immutable.")
        obj.delete()
        return Response(status=204)


class JournalEntryPostView(APIView):
    def post(self, request, entry_id):
        _require_admin(request)
        try:
            entry = GLBus.post_draft(_ws(request), entry_id, actor_id=_uid(request))
        except LedgerError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(JournalEntrySerializer(entry).data)


class JournalEntryReverseView(APIView):
    def post(self, request, entry_id):
        _require_admin(request)
        data = request.data if isinstance(request.data, dict) else {}
        try:
            entry = GLBus.reverse(_ws(request), entry_id, date=data.get("date"),
                                  memo=data.get("memo", ""), actor_id=_uid(request))
        except LedgerError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(JournalEntrySerializer(entry).data, status=201)


# ── Posting rules ───────────────────────────────────────────────────────────────
class PostingRuleListCreateView(APIView):
    def get(self, request):
        _member(request)
        qs = PostingRule.objects.filter(workspace_id=_ws(request)).order_by("event_type")
        return Response(PostingRuleSerializer(qs, many=True).data)

    def post(self, request):
        _require_admin(request)
        ws = _ws(request)
        ser = PostingRuleSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if PostingRule.objects.filter(workspace_id=ws, event_type=ser.validated_data["event_type"]).exists():
            raise ValidationError("A rule for this event type already exists.")
        obj = ser.save(workspace_id=ws, created_by=_uid(request))
        return Response(PostingRuleSerializer(obj).data, status=201)


class PostingRuleDetailView(APIView):
    def _get(self, request, rule_id) -> PostingRule:
        obj = PostingRule.objects.filter(workspace_id=_ws(request), id=rule_id).first()
        if obj is None:
            raise NotFound("Posting rule not found.")
        return obj

    def get(self, request, rule_id):
        _member(request)
        return Response(PostingRuleSerializer(self._get(request, rule_id)).data)

    def patch(self, request, rule_id):
        _require_admin(request)
        obj = self._get(request, rule_id)
        ser = PostingRuleSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(PostingRuleSerializer(obj).data)

    def delete(self, request, rule_id):
        _require_admin(request)
        self._get(request, rule_id).delete()
        return Response(status=204)


# ── Setup: seed standard chart + generate fiscal year (Phase P2.3) ───────────────
class SeedChartView(APIView):
    def post(self, request):
        _require_admin(request)
        result = seeding.seed_standard_chart(_ws(request), created_by=_uid(request))
        return Response(result, status=201)


class GenerateFiscalYearView(APIView):
    def post(self, request):
        _require_admin(request)
        data = request.data if isinstance(request.data, dict) else {}
        try:
            year = int(data.get("year"))
        except (TypeError, ValueError) as exc:
            raise ValidationError("year is required (integer).") from exc
        start_month = int(data.get("start_month", 1) or 1)
        result = seeding.generate_fiscal_year(_ws(request), year=year, start_month=start_month)
        return Response(result, status=201)


# ── Financial reports (Phase P2.3) ────────────────────────────────────────────
class TrialBalanceView(APIView):
    def get(self, request):
        _member(request)
        as_of = _parse_date(request.query_params.get("as_of"))
        return Response(report_svc.trial_balance(_ws(request), as_of=as_of))


class GeneralLedgerView(APIView):
    def get(self, request):
        _member(request)
        account_id = request.query_params.get("account")
        if not account_id:
            raise ValidationError("account query parameter is required.")
        return Response(report_svc.general_ledger(
            _ws(request), account_id,
            date_from=_parse_date(request.query_params.get("date_from")),
            date_to=_parse_date(request.query_params.get("date_to"))))


class ProfitLossView(APIView):
    def get(self, request):
        _member(request)
        return Response(report_svc.profit_and_loss(
            _ws(request),
            date_from=_parse_date(request.query_params.get("date_from")),
            date_to=_parse_date(request.query_params.get("date_to"))))


class BalanceSheetView(APIView):
    def get(self, request):
        _member(request)
        return Response(report_svc.balance_sheet(
            _ws(request), as_of=_parse_date(request.query_params.get("as_of"))))
