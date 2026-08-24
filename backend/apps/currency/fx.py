"""
Foreign-Exchange gain/loss (Financial Platform — multi-currency).

``FxService`` handles the two FX P&L effects, both posting through the single GLBus:
  * REALIZED — the difference in base value between when a foreign item was booked and when it was
    settled. This is naturally part of the caller's SETTLEMENT/payment journal (the payment entry
    carries an FX line); ``realized_gain_loss`` computes the base difference + the target account so a
    caller can add that line. (A convenience ``post_realized`` posts a standalone adjustment when a
    package prefers the platform to own it.)
  * UNREALIZED — period-end REVALUATION of an open foreign-currency monetary balance to the closing
    rate. ``revalue_account`` posts a BASE-currency adjusting entry (Dr/Cr the account / Cr/Dr the
    unrealized FX account) so the account's base carrying value equals foreign × closing rate. It is
    convergent (a second run at the same rate posts nothing).

Reuses ``apps.ledger`` (GLBus) + ``AccountingSettings`` — no new accounting.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone

from apps.ledger.models import JournalEntry, JournalLine, LedgerAccount
from apps.ledger.provisioning import ensure_accounting_settings

CENTS = Decimal("0.01")
_POSTED = [JournalEntry.POSTED, JournalEntry.REVERSED]


def _m(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(CENTS, rounding=ROUND_HALF_UP)


class FxService:
    @staticmethod
    def realized_gain_loss(*, booked_base, settled_base) -> dict:
        """Base-currency FX result of settling something booked at ``booked_base`` for ``settled_base``.
        Positive ``gain`` = FX gain. Pure — the caller posts it as a line in the payment journal."""
        diff = _m(Decimal(str(settled_base)) - Decimal(str(booked_base)))
        return {"gain": str(diff), "is_gain": diff >= 0, "amount": str(abs(diff))}

    @staticmethod
    def _reval_ref(account_code, currency):
        return f"reval:{account_code}:{str(currency).upper()}"

    @staticmethod
    def _foreign_and_base(workspace_id, account, currency, as_of):
        """(foreign_balance, current_base_carrying_value) of the ``currency`` position on ``account``.

        foreign = Σ transaction amounts of lines in that currency. current_base = their base value PLUS
        the base of any prior FX-revaluation adjustments already booked against this account+currency
        (those adjustments are posted in the base currency, so they must be added back for the
        revaluation to converge)."""
        cur = str(currency).upper()
        foreign = Decimal("0")
        base = Decimal("0")
        fx_lines = JournalLine.objects.filter(
            workspace_id=workspace_id, account_id=account.id, currency=cur,
            entry__status__in=_POSTED)
        reval_lines = JournalLine.objects.filter(
            workspace_id=workspace_id, account_id=account.id,
            entry__source_module="fx_revaluation",
            entry__source_ref=FxService._reval_ref(account.code, cur),
            entry__status__in=_POSTED)
        if as_of is not None:
            fx_lines = fx_lines.filter(entry__date__lte=as_of)
            reval_lines = reval_lines.filter(entry__date__lte=as_of)
        for ln in fx_lines.values("debit", "credit", "base_debit", "base_credit"):
            foreign += ln["debit"] - ln["credit"]
            base += ln["base_debit"] - ln["base_credit"]
        for ln in reval_lines.values("base_debit", "base_credit"):
            base += ln["base_debit"] - ln["base_credit"]
        return _m(foreign), _m(base)

    @staticmethod
    def revalue_account(*, workspace_id, account_code, currency, closing_rate, as_of=None,
                        actor_id=None) -> dict:
        """Revalue an open foreign-currency monetary balance to ``closing_rate`` (foreign→base). Posts
        the unrealized-FX adjusting entry in BASE currency. Idempotent/convergent per rate."""
        from apps.ledger.services import GLBus, LedgerError, emit_post_failure
        as_of = as_of or timezone.now().date()
        acct = LedgerAccount.objects.filter(
            workspace_id=workspace_id, code=str(account_code)).first()
        if acct is None:
            return {"revalued": False, "reason": "unknown_account"}
        foreign, current_base = FxService._foreign_and_base(
            workspace_id, acct, currency, as_of)
        if foreign == 0:
            return {"revalued": False, "reason": "no_open_balance"}
        target_base = _m(foreign * Decimal(str(closing_rate)))
        adjustment = _m(target_base - current_base)
        if adjustment == 0:
            return {"revalued": False, "reason": "no_change", "adjustment": "0.00"}
        settings = ensure_accounting_settings(workspace_id, actor_id=actor_id)
        gain_acct = settings.default_fx_gain_account
        loss_acct = settings.default_fx_loss_account
        amt = abs(adjustment)
        if adjustment > 0:
            # asset gained base value → Dr account / Cr FX gain
            lines = [{"account_code": acct.code, "debit": str(amt), "memo": "FX revaluation"},
                     {"account_code": gain_acct, "credit": str(amt), "memo": "Unrealized FX gain"}]
        else:
            lines = [{"account_code": loss_acct, "debit": str(amt), "memo": "Unrealized FX loss"},
                     {"account_code": acct.code, "credit": str(amt), "memo": "FX revaluation"}]
        try:
            entry = GLBus.post(
                workspace_id, date=as_of, lines=lines,
                memo=f"FX revaluation {account_code} {currency}@{closing_rate}",
                source_module="fx_revaluation",
                source_ref=FxService._reval_ref(account_code, currency), actor_id=actor_id)
        except LedgerError as exc:
            emit_post_failure(workspace_id, module="fx_revaluation", source_ref=str(account_code),
                              error=str(exc), actor_id=actor_id)
            raise
        return {"revalued": True, "adjustment": str(adjustment),
                "foreign_balance": str(foreign), "target_base": str(target_base),
                "journal_entry_id": str(entry.id) if entry is not None else None}
