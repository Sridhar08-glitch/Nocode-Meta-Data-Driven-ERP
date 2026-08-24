"""
Consolidation & Intercompany services (Financial Platform — F11).

``IntercompanyService`` posts intercompany transactions as paired GLBus entries (one per company,
tagged ``company_id``) — no separate IC accounting engine. ``ConsolidationService`` produces immutable
``ConsolidationRun`` snapshots: it reads each member company's GL balances, TRANSLATES functional →
presentation currency via the F7 ``CurrencyService`` (closing rate for balance-sheet accounts, average
for P&L, residual → CTA), ELIMINATES intercompany balances, and computes MINORITY INTEREST from
``companies.CompanyOwnership`` — all in the run's worksheet. Operational books are never modified;
reruns produce new versions. GL stays the owner; translation reuses F7.
"""
from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone

from apps.companies.models import Company
from apps.companies.services import CompanyService
from apps.ledger.models import (
    ASSET,
    EQUITY,
    LIABILITY,
    JournalEntry,
    JournalLine,
    LedgerAccount,
)
from apps.ledger.provisioning import ensure_accounting_settings
from apps.solution_templates.documents import emit_event

from .models import ConsolidationRun

CENTS = Decimal("0.01")
_POSTED = [JournalEntry.POSTED, JournalEntry.REVERSED]
_BALANCE_SHEET = {ASSET, LIABILITY, EQUITY}


class ConsolidationError(Exception):  # noqa: N818 — domain error
    pass


def _m(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(CENTS, rounding=ROUND_HALF_UP)


def _uid(actor_id):
    return uuid.UUID(str(actor_id)) if actor_id else None


class IntercompanyService:
    @staticmethod
    def post_transaction(*, workspace_id, from_company, to_company, amount, from_account="6900",
                         to_account="4000", description="", date=None, external_ref="",
                         actor_id=None) -> dict:
        """Post an intercompany transaction as TWO GLBus entries (one per company): the payer books
        Dr <from_account> / Cr IC-Payable; the receiver books Dr IC-Receivable / Cr <to_account>.
        Uses the single GL — no duplicated accounting. Idempotent on ``external_ref``."""
        from apps.ledger.services import GLBus, LedgerError, emit_post_failure
        amt = _m(amount)
        if amt <= 0:
            raise ConsolidationError("Intercompany amount must be positive.")
        src = Company.objects.filter(workspace_id=workspace_id, id=from_company).first()
        dst = Company.objects.filter(workspace_id=workspace_id, id=to_company).first()
        if src is None or dst is None:
            raise ConsolidationError("Company not found.")
        if src.id == dst.id:
            raise ConsolidationError("Intercompany requires two different companies.")
        # IC control accounts resolve from Finance's AccountingSettings (Company is a platform object
        # with no accounting mappings); per-company overrides = a future Finance-side extension.
        settings = ensure_accounting_settings(workspace_id, actor_id=actor_id)
        ic_pay = settings.default_ic_payable_account
        ic_rec = settings.default_ic_receivable_account
        day = date or timezone.now().date()
        ext = external_ref or f"ic:{uuid.uuid4().hex}"
        if JournalEntry.objects.filter(
                workspace_id=workspace_id, source_module="intercompany", source_ref=f"{ext}:from"
        ).exclude(status=JournalEntry.REVERSED).exists():
            return {"posted": False, "reason": "already_posted"}
        try:
            e_from = GLBus.post(
                workspace_id, date=day, company_id=src.id, lines=[
                    {"account_code": from_account, "debit": str(amt),
                     "memo": description or "Intercompany"},
                    {"account_code": ic_pay, "credit": str(amt), "partner_ref": str(dst.code)}],
                memo=description or f"IC {src.code}->{dst.code}", source_module="intercompany",
                source_ref=f"{ext}:from", actor_id=actor_id)
            e_to = GLBus.post(
                workspace_id, date=day, company_id=dst.id, lines=[
                    {"account_code": ic_rec, "debit": str(amt), "partner_ref": str(src.code)},
                    {"account_code": to_account, "credit": str(amt),
                     "memo": description or "Intercompany"}],
                memo=description or f"IC {src.code}->{dst.code}", source_module="intercompany",
                source_ref=f"{ext}:to", actor_id=actor_id)
        except LedgerError as exc:
            emit_post_failure(workspace_id, module="intercompany", source_ref=ext,
                              error=str(exc), actor_id=actor_id)
            raise
        emit_event(workspace_id, "intercompany", e_from.id, "intercompany.posted",
                   {"from": src.code, "to": dst.code, "amount": str(amt)}, actor_id)
        return {"posted": True, "from_entry": str(e_from.id), "to_entry": str(e_to.id)}


class ConsolidationService:
    @staticmethod
    def company_balances(workspace_id, company_id, *, as_of=None) -> dict:
        """{account_code: (account_type, functional_balance)} for one company (functional currency =
        the company's posting currency); balance = Σ(debit − credit) transaction amounts."""
        qs = JournalLine.objects.filter(
            workspace_id=workspace_id, entry__company_id=company_id, entry__status__in=_POSTED)
        if as_of is not None:
            qs = qs.filter(entry__date__lte=as_of)
        accts = {a.id: a for a in LedgerAccount.objects.filter(workspace_id=workspace_id)}
        out: dict = {}
        for ln in qs.values("account_id", "debit", "credit"):
            acct = accts.get(ln["account_id"])
            if acct is None:
                continue
            slot = out.setdefault(acct.code, [acct.account_type, Decimal("0")])
            slot[1] += ln["debit"] - ln["credit"]
        return {code: (t, _m(bal)) for code, (t, bal) in out.items()}

    @staticmethod
    def run(*, workspace_id, group_id, as_of=None, presentation_currency=None, eliminate_ic=True,
            status="final", actor_id=None) -> ConsolidationRun:
        """Consolidate a group into an immutable ``ConsolidationRun`` snapshot (never touches
        operational books). Translate each member functional→presentation currency, eliminate
        intercompany balances, plug CTA, and compute minority interest."""
        from apps.currency.services import CurrencyError, CurrencyService
        group = Company.objects.filter(workspace_id=workspace_id, id=group_id).first()
        if group is None:
            raise ConsolidationError("Group company not found.")
        members = CompanyService.members(workspace_id, group_id)
        if not members:
            raise ConsolidationError("Group has no member companies.")
        presentation = (presentation_currency or group.functional_currency
                        or CurrencyService.base_code(workspace_id) or "").upper()
        settings = ensure_accounting_settings(workspace_id)
        ic_codes = {settings.default_ic_receivable_account, settings.default_ic_payable_account}
        cta_code = settings.default_cta_account

        consolidated: dict = {}          # account_code -> [type, translated balance]
        company_cols, translations, minorities, cells = [], [], [], []
        for company in members:
            fcur = (company.functional_currency or presentation).upper()
            try:
                closing = (Decimal("1") if not presentation or fcur == presentation
                           else CurrencyService.get_rate(workspace_id, fcur, presentation,
                                                         on_date=as_of, rate_type="closing"))
                avg = (Decimal("1") if not presentation or fcur == presentation
                       else CurrencyService.get_rate(workspace_id, fcur, presentation,
                                                     on_date=as_of, rate_type="average"))
            except CurrencyError as exc:
                raise ConsolidationError(
                    f"Missing translation rate {fcur}->{presentation}: {exc}") from exc
            balances = ConsolidationService.company_balances(workspace_id, company.id, as_of=as_of)
            net_assets, comp_residual = Decimal("0"), Decimal("0")
            for code, (atype, fbal) in balances.items():
                rate = closing if atype in _BALANCE_SHEET else avg
                translated = _m(fbal * rate)
                cells.append({"company_code": company.code, "account_code": code,
                              "account_type": atype, "functional_balance": _m(fbal),
                              "translated_balance": translated})
                consolidated.setdefault(code, [atype, Decimal("0")])[1] += translated
                comp_residual += translated
                if atype in (ASSET, LIABILITY):
                    net_assets += translated          # assets(+) + liabilities(−) = net assets
            company_cols.append({"company": company.code, "functional_currency": fcur,
                                 "closing_rate": str(closing), "average_rate": str(avg)})
            translations.append({"company_id": company.id, "company_code": company.code,
                                 "from_currency": fcur, "to_currency": presentation,
                                 "closing_rate": closing, "average_rate": avg,
                                 "cta_amount": _m(-comp_residual)})   # this company's CTA contribution
            own_pct = CompanyService.ownership_pct_at(workspace_id, company.id, on_date=as_of)
            if own_pct < 100:
                minority_pct = Decimal("100") - own_pct
                mi = _m(minority_pct / Decimal("100") * net_assets)
                minorities.append({"company_id": company.id, "company_code": company.code,
                                   "ownership_pct": own_pct, "minority_pct": minority_pct,
                                   "net_assets": _m(net_assets), "minority_amount": mi})

        eliminations = {}
        if eliminate_ic:
            for code in ic_codes:
                if code in consolidated:
                    eliminations[code] = str(_m(consolidated[code][1]))
                    consolidated[code][1] = Decimal("0")

        residual = sum((bal for _t, bal in consolidated.values()), Decimal("0"))
        cta = _m(-residual)
        if cta != 0:
            consolidated.setdefault(cta_code, [EQUITY, Decimal("0")])[1] += cta

        # Consolidated (group-total) cells: post-elimination + CTA, company_code blank.
        for code, (atype, bal) in sorted(consolidated.items()):
            cells.append({"company_code": "", "account_code": code, "account_type": atype,
                          "functional_balance": Decimal("0"), "translated_balance": _m(bal),
                          "eliminated_amount": _m(Decimal(eliminations.get(code, "0"))),
                          "is_cta": code == cta_code and cta != 0})
        total = sum((bal for _t, bal in consolidated.values()), Decimal("0"))
        balanced = _m(total) == 0
        total_mi = _m(sum((m["minority_amount"] for m in minorities), Decimal("0")))
        # COMPACT summary only — the per-account/per-company detail lives in worksheet-line ROWS.
        worksheet = {"group": group.code, "presentation_currency": presentation,
                     "companies": company_cols, "eliminations": eliminations, "cta": str(cta),
                     "total_minority_interest": str(total_mi), "balanced": balanced,
                     "line_count": len(cells)}
        last = (ConsolidationRun.objects.filter(workspace_id=workspace_id, group_company_id=group.id)
                .order_by("-version_no").first())
        run = ConsolidationRun.objects.create(
            workspace_id=workspace_id, group_company_id=group.id, group_code=group.code,
            as_of=as_of, presentation_currency=presentation,
            version_no=(last.version_no + 1) if last else 1, status=status, balanced=balanced,
            company_count=len(members), worksheet=worksheet, cta=cta,
            total_minority_interest=total_mi, created_by=_uid(actor_id))
        # Persist the first-class worksheet DETAIL + translation + minority-interest disclosures
        # (queryable / auditable / diffable; never a JSON blob, never compute-only).
        from .models import (
            ConsolidationWorksheetLine,
            MinorityInterest,
            TranslationAdjustment,
        )
        ConsolidationWorksheetLine.objects.bulk_create([
            ConsolidationWorksheetLine(workspace_id=workspace_id, run=run, **c) for c in cells])
        TranslationAdjustment.objects.bulk_create([
            TranslationAdjustment(workspace_id=workspace_id, run=run, **t) for t in translations])
        MinorityInterest.objects.bulk_create([
            MinorityInterest(workspace_id=workspace_id, run=run, as_of=as_of, **m)
            for m in minorities])
        emit_event(workspace_id, "consolidation", run.id, "consolidation.run",
                   {"group": group.code, "version": run.version_no, "status": status,
                    "balanced": balanced}, actor_id)
        return run
