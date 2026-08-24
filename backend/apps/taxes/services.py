"""
Tax Engine services (Financial Platform — Gap G1).

``TaxService`` is the single reusable entry point every ERP package calls (via the workflow actions
``action_calculate_tax`` / ``action_post_tax`` / ``action_reverse_tax``, or REST) to compute and
account for indirect + withholding tax. It REUSES the platform engines and adds NO accounting of its
own:
  * account codes → ``apps.ledger.provisioning.ensure_accounting_settings`` (no hardcoded codes)
  * balanced post → ``apps.ledger.GLBus`` (the single double-entry engine)
  * domain events → ``apps.eventstore`` (via ``emit_event``)

``calculate`` is a PURE, deterministic function (no AI): exclusive/inclusive pricing, compound /
cascading groups, per-partner exemptions, and temporal rate resolution. ``post`` records an IMMUTABLE
tax subledger (``TaxTransaction``, for tax returns) and posts a balanced GL entry; a correction is a
``reverse`` (a GL reversal), never an edit.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.ledger.provisioning import ensure_accounting_settings
from apps.solution_templates.documents import emit_event

from .models import (
    OUTPUT,
    TaxCode,
    TaxExemption,
    TaxGroup,
    TaxRate,
    TaxTransaction,
)
from .money import money
from .money import rate as _rate

HUNDRED = Decimal("100")


class TaxError(Exception):  # noqa: N818 — domain error
    pass


def _uid(actor_id):
    return uuid.UUID(str(actor_id)) if actor_id else None


def _today(on_date):
    return on_date or timezone.now().date()


class TaxService:
    # ── resolution ────────────────────────────────────────────────────────────
    @staticmethod
    def _resolve_codes(workspace_id, tax_code, tax_group) -> list[TaxCode]:
        """Return the ordered TaxCode list to apply (a single code or a group's members)."""
        if tax_group:
            group = (TaxGroup.objects.filter(workspace_id=workspace_id)
                     .filter(_pk_or_code(tax_group)).first())
            if group is None:
                raise TaxError(f"Unknown tax group: {tax_group!r}")
            members = (group.members.select_related("tax_code")
                       .order_by("sequence", "created_at"))
            return [m.tax_code for m in members if m.tax_code and m.tax_code.is_active]
        if tax_code:
            code = (TaxCode.objects.filter(workspace_id=workspace_id, is_active=True)
                    .filter(_pk_or_code(tax_code)).first())
            if code is None:
                raise TaxError(f"Unknown tax code: {tax_code!r}")
            return [code]
        return []

    @staticmethod
    def resolve_rate(workspace_id, code: TaxCode, on_date) -> Decimal:
        """The rate (percent) of ``code`` effective on ``on_date`` — the most-specific active
        ``TaxRate`` whose window covers the date (open-ended bounds allowed). 0 if none."""
        day = _today(on_date)
        qs = TaxRate.objects.filter(workspace_id=workspace_id, tax_code=code, is_active=True)
        best = None
        for r in qs:
            if r.effective_from and r.effective_from > day:
                continue
            if r.effective_to and r.effective_to < day:
                continue
            # prefer the latest effective_from that still covers the date
            if best is None or (r.effective_from or _MIN) >= (best.effective_from or _MIN):
                best = r
        return _rate(best.rate) if best is not None else Decimal("0")

    @staticmethod
    def is_exempt(workspace_id, partner_ref, code: TaxCode, on_date) -> bool:
        if not partner_ref:
            return False
        day = _today(on_date)
        qs = TaxExemption.objects.filter(
            workspace_id=workspace_id, partner_ref=str(partner_ref), is_active=True)
        for ex in qs:
            if ex.tax_code_id not in (None, code.id):
                continue
            # a group-scoped exemption only applies if the code belongs to that group
            if (ex.tax_code_id is None and ex.tax_group_id is not None
                    and not code.group_members.filter(tax_group_id=ex.tax_group_id).exists()):
                continue
            if ex.effective_from and ex.effective_from > day:
                continue
            if ex.effective_to and ex.effective_to < day:
                continue
            return True
        return False

    # ── the pure calculation ───────────────────────────────────────────────────
    @staticmethod
    def calculate(workspace_id, *, amount, tax_code=None, tax_group=None, on_date=None,
                  partner_ref="", inclusive=None, quantity=1) -> dict:
        """Compute tax for ``amount`` (× ``quantity``). Deterministic — no AI.

        Returns ``{taxable_base, net, total_tax, gross, inclusive, exempt, currency?, components:[
        {code, type, rate, base, amount, is_compound, exempt}]}``. Handles exclusive/inclusive
        pricing, compound (cascading) groups and per-partner exemptions; the effective rate is
        resolved from ``TaxRate`` on ``on_date``.
        """
        gross_or_net = money(amount) * Decimal(str(quantity or 1))
        gross_or_net = money(gross_or_net)
        codes = TaxService._resolve_codes(workspace_id, tax_code, tax_group)
        if not codes or gross_or_net == 0:
            return {"taxable_base": gross_or_net, "net": gross_or_net, "total_tax": money(0),
                    "gross": gross_or_net, "inclusive": bool(inclusive), "exempt": not codes,
                    "components": []}

        # per-code (rate, exempt) resolved once
        specs = []
        for c in codes:
            r = TaxService.resolve_rate(workspace_id, c, on_date)
            ex = TaxService.is_exempt(workspace_id, partner_ref, c, on_date)
            specs.append((c, (Decimal("0") if ex else r), ex))

        # inclusive default: if any code is inclusive and caller didn't say, treat as inclusive
        if inclusive is None:
            inclusive = any(c.is_inclusive for c in codes)

        if inclusive:
            factor = _unit_factor(specs)                 # total tax per 1.0 of net (exact)
            net = money(gross_or_net / (Decimal("1") + factor))
            components = _components_on(specs, net)
            total_tax = gross_or_net - net
            _reconcile(components, total_tax)            # ensure Σ components == total_tax
            gross = gross_or_net
        else:
            net = gross_or_net
            components = _components_on(specs, net)
            total_tax = sum((c["amount"] for c in components), money(0))
            gross = net + total_tax

        return {"taxable_base": net, "net": net, "total_tax": money(total_tax),
                "gross": money(gross), "inclusive": bool(inclusive),
                "exempt": all(s[2] for s in specs), "components": components}

    # ── recording + posting (the tax subledger + GL) ────────────────────────────
    @staticmethod
    def post(workspace_id, *, amount=None, calculation=None, tax_code=None, tax_group=None,
             direction=OUTPUT, source_module="", source_ref="", external_ref="", partner_ref="",
             currency="", on_date=None, offset_account=None, post_gl=None, actor_id=None) -> dict:
        """Record the IMMUTABLE tax subledger (``TaxTransaction`` rows, for the tax return) and —
        when an ``offset_account`` is supplied — post a balanced GL entry through ``GLBus``.

        The dominant billing pattern is ``action_calculate_tax`` → ``action_post_journal`` (the full
        invoice incl. tax lines); ``post`` here owns the tax SUBLEDGER + optional standalone tax
        journal (e.g. reverse-charge, remittance, adjustment). Idempotent on ``external_ref``.
        """
        day = _today(on_date)
        calc = calculation or TaxService.calculate(
            workspace_id, amount=amount, tax_code=tax_code, tax_group=tax_group,
            on_date=day, partner_ref=partner_ref)
        components = calc.get("components", [])
        settings = ensure_accounting_settings(workspace_id, actor_id=actor_id)
        do_gl = bool(offset_account) if post_gl is None else bool(post_gl)

        with transaction.atomic():
            if external_ref:
                existing = list(TaxTransaction.objects.select_for_update().filter(
                    workspace_id=workspace_id, external_ref=external_ref
                ).exclude(status=TaxTransaction.REVERSED))
                if existing:
                    return {"posted": False, "reason": "already_recorded",
                            "transactions": [str(t.id) for t in existing]}

            rows = []
            for comp in components:
                code = comp["_code"]
                rows.append(TaxTransaction.objects.create(
                    workspace_id=workspace_id, source_module=str(source_module),
                    source_ref=str(source_ref), tax_code=code, tax_code_str=code.code,
                    direction=direction, taxable_amount=comp["base"], tax_rate=comp["rate"],
                    tax_amount=comp["amount"], is_recoverable=code.is_recoverable,
                    is_exempt=comp["exempt"], currency=currency, partner_ref=str(partner_ref or ""),
                    jurisdiction=(code.authority.code if code.authority_id else ""),
                    external_ref=str(external_ref or ""),
                    status=TaxTransaction.POSTED if do_gl else TaxTransaction.COMPUTED,
                    created_by=_uid(actor_id)))

            journal_id = None
            if do_gl and offset_account:
                journal_id = TaxService._post_gl(
                    workspace_id, components, direction, offset_account, settings,
                    source_module, source_ref, currency, day, actor_id)
                if journal_id is not None:
                    for t in rows:
                        t.journal_entry_id = journal_id
                    TaxTransaction.objects.bulk_update(rows, ["journal_entry_id"])

        emit_event(workspace_id, "tax_transaction", rows[0].id if rows else uuid.uuid4(),
                   f"tax.{direction}.posted",
                   {"source_ref": str(source_ref), "total_tax": str(calc.get("total_tax")),
                    "count": len(rows)}, actor_id)
        return {"posted": bool(rows), "total_tax": str(calc.get("total_tax")),
                "journal_entry_id": str(journal_id) if journal_id else None,
                "transactions": [str(t.id) for t in rows]}

    @staticmethod
    def _post_gl(workspace_id, components, direction, offset_account, settings,
                 source_module, source_ref, currency, day, actor_id):
        from apps.ledger.services import GLBus, LedgerError, emit_post_failure
        eligible = [c for c in components
                    if c["amount"] > 0 and not c["exempt"]
                    and (direction == OUTPUT or c["_code"].is_recoverable)]
        gl_total = sum((c["amount"] for c in eligible), money(0))
        if gl_total <= 0:
            return None
        lines = []
        for c in eligible:
            code = c["_code"]
            if direction == OUTPUT:
                acct = code.output_account_code or settings.default_output_tax_account
                lines.append({"account_code": acct, "credit": str(c["amount"]),
                              "memo": f"Output tax {code.code}", "partner_ref": ""})
            else:
                acct = code.input_account_code or settings.default_input_tax_account
                lines.append({"account_code": acct, "debit": str(c["amount"]),
                              "memo": f"Input tax {code.code}", "partner_ref": ""})
        if direction == OUTPUT:
            lines.append({"account_code": str(offset_account), "debit": str(gl_total),
                          "memo": "Tax offset"})
        else:
            lines.append({"account_code": str(offset_account), "credit": str(gl_total),
                          "memo": "Tax offset"})
        try:
            entry = GLBus.post(
                workspace_id, date=day, lines=lines, memo=f"Tax {direction} {source_ref}",
                currency=currency, source_module=str(source_module or "taxes"),
                source_ref=f"tax:{source_ref}", actor_id=actor_id)
            return entry.id if entry is not None else None
        except LedgerError as exc:
            emit_post_failure(workspace_id, module="taxes", source_ref=str(source_ref),
                              error=str(exc), actor_id=actor_id)
            raise

    @staticmethod
    def reverse(workspace_id, *, source_module="", source_ref="", external_ref="",
                reason="", actor_id=None) -> dict:
        """Reverse a document's tax: post a reversing GL entry (once) and mark the tax subledger
        rows reversed. Idempotent. Books stay immutable."""
        from apps.ledger.services import GLBus, LedgerError, emit_post_failure
        with transaction.atomic():
            qs = TaxTransaction.objects.select_for_update().filter(workspace_id=workspace_id)
            if external_ref:
                qs = qs.filter(external_ref=external_ref)
            else:
                qs = qs.filter(source_module=str(source_module), source_ref=str(source_ref))
            rows = list(qs.exclude(status=TaxTransaction.REVERSED))
            if not rows:
                return {"reversed": 0, "reason": "nothing_to_reverse"}
            journals = {t.journal_entry_id for t in rows if t.journal_entry_id}
            rev_id = None
            for jid in journals:
                try:
                    rev = GLBus.reverse(workspace_id, jid,
                                        memo=reason or "Tax reversal", actor_id=actor_id)
                    rev_id = rev.id if rev is not None else None
                except LedgerError as exc:
                    emit_post_failure(workspace_id, module="taxes",
                                      source_ref=str(source_ref or external_ref),
                                      error=str(exc), actor_id=actor_id)
                    raise
            for t in rows:
                t.status = TaxTransaction.REVERSED
                t.reversal_entry_id = rev_id
            TaxTransaction.objects.bulk_update(rows, ["status", "reversal_entry_id", "updated_at"])
        emit_event(workspace_id, "tax_transaction", rows[0].id, "tax.reversed",
                   {"source_ref": str(source_ref or external_ref), "count": len(rows)}, actor_id)
        return {"reversed": len(rows)}

    # ── the tax return summary ──────────────────────────────────────────────────
    @staticmethod
    def tax_summary(workspace_id, *, from_date=None, to_date=None) -> dict:
        """Aggregate the tax subledger into a return: output tax (payable) vs recoverable input tax,
        net payable, and a per-code breakdown. Excludes reversed rows."""
        qs = TaxTransaction.objects.filter(workspace_id=workspace_id).exclude(
            status=TaxTransaction.REVERSED)
        if from_date:
            qs = qs.filter(created_at__date__gte=from_date)
        if to_date:
            qs = qs.filter(created_at__date__lte=to_date)
        output_total = money(0)
        input_recoverable = money(0)
        by_code: dict[str, dict] = {}
        for t in qs:
            slot = by_code.setdefault(t.tax_code_str or "?", {
                "output": money(0), "input": money(0), "type": ""})
            if t.direction == OUTPUT:
                output_total += t.tax_amount
                slot["output"] += t.tax_amount
            elif t.is_recoverable:
                input_recoverable += t.tax_amount
                slot["input"] += t.tax_amount
        return {
            "output_tax": str(output_total),
            "input_tax_recoverable": str(input_recoverable),
            "net_payable": str(money(output_total - input_recoverable)),
            "by_code": {k: {"output": str(v["output"]), "input": str(v["input"])}
                        for k, v in by_code.items()},
        }


# ── pure helpers (no DB) ───────────────────────────────────────────────────────
_MIN = __import__("datetime").date.min


def _pk_or_code(value):
    """A Q matching either the UUID pk or the natural ``code`` (callers pass whichever)."""
    from django.db.models import Q
    value = str(value)
    try:
        uuid.UUID(value)
        return Q(id=value)
    except (ValueError, AttributeError):
        return Q(code=value)


def _components_on(specs, net) -> list[dict]:
    """Compute money-rounded tax components on a fixed ``net`` (exclusive). Compound codes apply on
    net + all prior taxes; non-compound apply on net only."""
    components = []
    prior = money(0)
    for code, rate, exempt in specs:
        base = money(net + prior) if code.is_compound else money(net)
        amount = money(base * rate / HUNDRED)
        components.append({
            "code": code.code, "type": code.tax_type, "rate": rate, "base": base,
            "amount": amount, "is_compound": code.is_compound, "exempt": exempt, "_code": code})
        prior = money(prior + amount)
    return components


def _unit_factor(specs) -> Decimal:
    """Total tax generated per 1.0 of net (exact, unrounded) — used to invert inclusive pricing."""
    prior = Decimal("0")
    total = Decimal("0")
    one = Decimal("1")
    for code, rate, _exempt in specs:
        base = (one + prior) if code.is_compound else one
        amt = base * rate / HUNDRED
        total += amt
        prior += amt
    return total


def _reconcile(components, target_total):
    """Nudge the last non-exempt component so Σ amounts == target_total (inclusive rounding)."""
    current = sum((c["amount"] for c in components), money(0))
    diff = money(target_total) - current
    if diff == 0:
        return
    for c in reversed(components):
        if not c["exempt"] and c["amount"] > 0:
            c["amount"] = money(c["amount"] + diff)
            return
    if components:
        components[-1]["amount"] = money(components[-1]["amount"] + diff)
