"""
Treasury Platform REST API at /api/v1/treasury/ (F12).

Masters (counterparties/facilities/investments) + every treasury EVENT as a ``TreasuryTransaction``
(posts via ``GLBus`` — no parallel accounting) + COMPUTED reports (interest/debt/maturity schedules,
liquidity position, counterparty exposure, treasury forecast). Admin-gated writes; member reads.
"""
import uuid

from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    TreasuryCounterparty,
    TreasuryFacility,
    TreasuryInvestment,
    TreasuryTransaction,
)
from .services import (
    LiquidityService,
    ScheduleService,
    TreasuryError,
    TreasuryForecastService,
    TreasuryService,
)

_ADMIN_ROLES = {"owner", "admin"}


def _ws(request) -> uuid.UUID:
    ws = getattr(request, "workspace_id", None)
    if not ws:
        raise PermissionDenied("No active workspace. Send the X-Workspace-Slug header.")
    return ws if isinstance(ws, uuid.UUID) else uuid.UUID(str(ws))


def _require_admin(request):
    m = getattr(request, "workspace_member", None)
    if m is None or getattr(m, "role", "") not in _ADMIN_ROLES:
        raise PermissionDenied("Treasury maintenance requires an admin or owner role.")


def _uid(request):
    return getattr(request.user, "id", None)


def _run(fn, *a, **k):
    try:
        return fn(*a, **k)
    except TreasuryError as exc:
        raise ValidationError(str(exc)) from exc


# ── masters ─────────────────────────────────────────────────────────────────────
class CounterpartyListView(APIView):
    def get(self, request):
        qs = TreasuryCounterparty.objects.filter(workspace_id=_ws(request)).order_by("code")
        return Response([{"id": str(c.id), "code": c.code, "name": c.name,
                          "counterparty_type": c.counterparty_type, "credit_rating": c.credit_rating,
                          "exposure_limit": str(c.exposure_limit), "is_active": c.is_active}
                         for c in qs])

    def post(self, request):
        _require_admin(request)
        d = request.data or {}
        if not d.get("code"):
            raise ValidationError("code required.")
        c = TreasuryCounterparty.objects.create(
            workspace_id=_ws(request), code=d["code"], name=d.get("name", ""),
            counterparty_type=d.get("counterparty_type", "bank"),
            credit_rating=d.get("credit_rating", ""), exposure_limit=d.get("exposure_limit", 0) or 0,
            created_by=_uid(request))
        return Response({"id": str(c.id), "code": c.code}, status=201)


def _deal_out(d, extra):
    base = {"id": str(d.id), "number": d.number, "principal": str(d.principal),
            "currency": d.currency, "interest_rate": str(d.interest_rate),
            "rate_type": d.rate_type, "payment_frequency": d.payment_frequency,
            "start_date": str(d.start_date) if d.start_date else None,
            "maturity_date": str(d.maturity_date) if d.maturity_date else None,
            "status": d.status, "counterparty": str(d.counterparty_id) if d.counterparty_id else None}
    base.update(extra)
    return base


class FacilityListView(APIView):
    def get(self, request):
        qs = TreasuryFacility.objects.filter(workspace_id=_ws(request)).order_by("-created_at")
        return Response([_deal_out(f, {"facility_type": f.facility_type,
                                       "facility_limit": str(f.facility_limit),
                                       "drawn_amount": str(f.drawn_amount),
                                       "outstanding": str(f.outstanding)}) for f in qs])

    def post(self, request):
        _require_admin(request)
        d = request.data or {}
        f = _run(TreasuryService.create_facility, workspace_id=_ws(request),
                 principal=d.get("principal"), facility_type=d.get("facility_type", "loan"),
                 counterparty_id=d.get("counterparty_id"), currency=d.get("currency", ""),
                 interest_rate=d.get("interest_rate", 0), rate_type=d.get("rate_type", "fixed"),
                 reference_rate=d.get("reference_rate", ""), spread=d.get("spread", 0),
                 compounding=d.get("compounding", "simple"),
                 payment_frequency=d.get("payment_frequency", "monthly"),
                 start_date=d.get("start_date"), maturity_date=d.get("maturity_date"),
                 company_id=d.get("company_id"), dimensions=d.get("dimensions"),
                 actor_id=_uid(request))
        return Response({"id": str(f.id), "number": f.number}, status=201)


class FacilityActionView(APIView):
    """POST /facilities/{id}/{action}/ where action ∈ drawdown | repay."""

    def post(self, request, facility_id, action):
        _require_admin(request)
        d = request.data or {}
        if action == "drawdown":
            txn = _run(TreasuryService.drawdown, workspace_id=_ws(request), facility_id=facility_id,
                       amount=d.get("amount"), date=d.get("date"), actor_id=_uid(request))
        elif action == "repay":
            txn = _run(TreasuryService.repay_principal, workspace_id=_ws(request),
                       facility_id=facility_id, amount=d.get("amount"), date=d.get("date"),
                       actor_id=_uid(request))
        else:
            raise ValidationError(f"Unknown facility action '{action}'.")
        return Response({"id": str(txn.id), "number": txn.number,
                         "transaction_type": txn.transaction_type, "amount": str(txn.amount),
                         "journal_entry_id": str(txn.journal_entry_id) if txn.journal_entry_id
                         else None}, status=201)


class InvestmentListView(APIView):
    def get(self, request):
        qs = TreasuryInvestment.objects.filter(workspace_id=_ws(request)).order_by("-created_at")
        return Response([_deal_out(i, {"investment_type": i.investment_type,
                                       "face_value": str(i.face_value),
                                       "outstanding": str(i.outstanding)}) for i in qs])

    def post(self, request):
        _require_admin(request)
        d = request.data or {}
        i = _run(TreasuryService.create_investment, workspace_id=_ws(request),
                 principal=d.get("principal"), investment_type=d.get("investment_type", "deposit"),
                 counterparty_id=d.get("counterparty_id"), currency=d.get("currency", ""),
                 interest_rate=d.get("interest_rate", 0), rate_type=d.get("rate_type", "fixed"),
                 compounding=d.get("compounding", "simple"),
                 payment_frequency=d.get("payment_frequency", "monthly"),
                 start_date=d.get("start_date"), maturity_date=d.get("maturity_date"),
                 company_id=d.get("company_id"), dimensions=d.get("dimensions"),
                 actor_id=_uid(request))
        return Response({"id": str(i.id), "number": i.number}, status=201)


class InvestmentActionView(APIView):
    """POST /investments/{id}/{action}/ where action ∈ place | mature."""

    def post(self, request, investment_id, action):
        _require_admin(request)
        d = request.data or {}
        if action == "place":
            txn = _run(TreasuryService.place_investment, workspace_id=_ws(request),
                       investment_id=investment_id, date=d.get("date"), actor_id=_uid(request))
        elif action == "mature":
            txn = _run(TreasuryService.mature_investment, workspace_id=_ws(request),
                       investment_id=investment_id, date=d.get("date"), actor_id=_uid(request))
        else:
            raise ValidationError(f"Unknown investment action '{action}'.")
        return Response({"id": str(txn.id), "number": txn.number,
                         "transaction_type": txn.transaction_type, "amount": str(txn.amount),
                         "journal_entry_id": str(txn.journal_entry_id) if txn.journal_entry_id
                         else None}, status=201)


# ── transactions + interest run ──────────────────────────────────────────────────
class TransactionListView(APIView):
    def get(self, request):
        qs = TreasuryTransaction.objects.filter(workspace_id=_ws(request)).order_by("-value_date",
                                                                                    "-created_at")
        ttype = request.query_params.get("transaction_type")
        if ttype:
            qs = qs.filter(transaction_type=ttype)
        return Response([{"id": str(t.id), "number": t.number,
                          "transaction_type": t.transaction_type, "amount": str(t.amount),
                          "currency": t.currency,
                          "value_date": str(t.value_date) if t.value_date else None,
                          "facility": str(t.facility_id) if t.facility_id else None,
                          "investment": str(t.investment_id) if t.investment_id else None,
                          "status": t.status,
                          "journal_entry_id": str(t.journal_entry_id) if t.journal_entry_id
                          else None} for t in qs[:500]])


class PayInterestDueView(APIView):
    def post(self, request):
        _require_admin(request)
        d = request.data or {}
        result = _run(TreasuryService.pay_interest_due, workspace_id=_ws(request),
                      as_of=d.get("as_of"), actor_id=_uid(request))
        return Response(result, status=201)


# ── computed reports ─────────────────────────────────────────────────────────────
class InterestScheduleView(APIView):
    def get(self, request, kind, deal_id):
        if kind not in ("facility", "investment"):
            raise ValidationError("kind must be 'facility' or 'investment'.")
        return Response(_run(ScheduleService.interest_schedule, _ws(request), kind, deal_id))


class DebtScheduleView(APIView):
    def get(self, request):
        return Response(ScheduleService.debt_schedule(_ws(request)))


class MaturityScheduleView(APIView):
    def get(self, request):
        return Response(ScheduleService.maturity_schedule(_ws(request)))


class LiquidityPositionView(APIView):
    def get(self, request):
        return Response(LiquidityService.position(_ws(request)))


class CounterpartyExposureView(APIView):
    def get(self, request):
        return Response(LiquidityService.counterparty_exposure(_ws(request)))


class ForecastView(APIView):
    def get(self, request):
        return Response(TreasuryForecastService.forecast(
            _ws(request), from_date=request.query_params.get("from"),
            to_date=request.query_params.get("to")))
