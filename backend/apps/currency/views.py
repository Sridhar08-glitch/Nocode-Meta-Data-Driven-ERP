"""
Multi-Currency REST API at /api/v1/currency/.

Currency + rate configuration is admin-gated; conversion + reads available to any member.
Workspace-scoped. Package-independent — packages transact in foreign currency purely by tagging a
journal line's currency; the platform records the base equivalent.
"""
import uuid

from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Currency, ExchangeRate
from .services import CurrencyError, CurrencyService

_ADMIN_ROLES = {"owner", "admin"}


def _ws(request) -> uuid.UUID:
    ws = getattr(request, "workspace_id", None)
    if not ws:
        raise PermissionDenied("No active workspace. Send the X-Workspace-Slug header.")
    return ws if isinstance(ws, uuid.UUID) else uuid.UUID(str(ws))


def _require_admin(request):
    m = getattr(request, "workspace_member", None)
    if m is None or getattr(m, "role", "") not in _ADMIN_ROLES:
        raise PermissionDenied("Currency configuration requires an admin or owner role.")


def _uid(request):
    return getattr(request.user, "id", None)


class CurrencyList(APIView):
    def get(self, request):
        qs = Currency.objects.filter(workspace_id=_ws(request)).order_by("code")
        return Response([{"id": str(c.id), "code": c.code, "name": c.name, "symbol": c.symbol,
                          "decimal_places": c.decimal_places, "is_base": c.is_base,
                          "is_active": c.is_active} for c in qs])

    def post(self, request):
        _require_admin(request)
        data = request.data or {}
        if not data.get("code"):
            raise ValidationError("code required.")
        cur = CurrencyService.ensure_currency(
            workspace_id=_ws(request), code=data["code"], name=data.get("name", ""),
            symbol=data.get("symbol", ""), decimal_places=int(data.get("decimal_places", 2)),
            is_base=bool(data.get("is_base", False)), actor_id=_uid(request))
        if data.get("is_base"):
            CurrencyService.set_base(workspace_id=_ws(request), code=data["code"],
                                     actor_id=_uid(request))
        return Response({"id": str(cur.id), "code": cur.code, "is_base": cur.is_base}, status=201)


class SetBaseView(APIView):
    def post(self, request):
        _require_admin(request)
        code = (request.data or {}).get("code")
        if not code:
            raise ValidationError("code required.")
        cur = CurrencyService.set_base(workspace_id=_ws(request), code=code, actor_id=_uid(request))
        return Response({"base": cur.code})


class RateList(APIView):
    def get(self, request):
        qs = ExchangeRate.objects.filter(workspace_id=_ws(request)).order_by(
            "from_currency", "to_currency", "-effective_date")[:500]
        return Response([{"id": str(r.id), "from": r.from_currency, "to": r.to_currency,
                          "rate": str(r.rate), "rate_type": r.rate_type,
                          "effective_date": str(r.effective_date) if r.effective_date else None}
                         for r in qs])

    def post(self, request):
        _require_admin(request)
        data = request.data or {}
        for f in ("from_currency", "to_currency", "rate"):
            if data.get(f) in (None, ""):
                raise ValidationError(f"{f} required.")
        r = CurrencyService.set_rate(
            workspace_id=_ws(request), from_currency=data["from_currency"],
            to_currency=data["to_currency"], rate=data["rate"],
            rate_type=data.get("rate_type", "spot"),
            effective_date=data.get("effective_date"), actor_id=_uid(request))
        return Response({"id": str(r.id), "rate": str(r.rate)}, status=201)


class ConvertView(APIView):
    def get(self, request):
        p = request.query_params
        for f in ("amount", "from", "to"):
            if not p.get(f):
                raise ValidationError(f"{f} required.")
        try:
            value = CurrencyService.convert(
                _ws(request), p["amount"], p["from"], p["to"], on_date=p.get("on_date"))
        except CurrencyError as exc:
            raise ValidationError(str(exc)) from exc
        return Response({"amount": p["amount"], "from": p["from"].upper(), "to": p["to"].upper(),
                         "converted": str(value)})
