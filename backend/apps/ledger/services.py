"""
GLBus / PostingService (Phase P2.2) — the single posting pipeline every module uses to write
to the general ledger. It guarantees the accounting invariants:

  * balanced entries (Σ debits == Σ credits, to 2dp),
  * immutable posted entries (correction = a reversing entry),
  * no posting into a closed/locked ``AccountingPeriod``,
  * gapless ``JE-`` numbers via the P2.1 numbering engine (allocated inside the posting txn).

Modules either call ``GLBus.post(...)`` with explicit lines, or fire ``GLBus.post_event(type, ctx)``
to let a configurable ``PostingRule`` build the lines — so new modules post consistently with no
bespoke GL code.
"""
from __future__ import annotations

import logging
import uuid
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from apps.eventstore.events import DomainEventData, DomainEventFactory
from apps.numbering.services import NumberingService

from .models import AccountingPeriod, JournalEntry, JournalLine, LedgerAccount, PostingRule

CENTS = Decimal("0.01")
logger = logging.getLogger("nexus.ledger")

# Stable namespace so a ledger.post.failed event for the same (module, source_ref) aggregates.
_POST_FAILURE_NS = uuid.UUID("6f1d2c4e-0b3a-4f5e-9c1d-2a3b4c5d6e7f")


class LedgerError(Exception):
    """Raised on a broken accounting invariant (unbalanced, locked period, bad account…)."""


def _money(value) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(CENTS, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise LedgerError(f"Invalid monetary amount: {value!r}") from exc


def _emit(entry: JournalEntry, event_type: str, payload: dict, actor_id=None):
    from apps.eventstore.models import DomainEvent
    version = DomainEvent.objects.filter(aggregate_id=entry.id).count() + 1
    DomainEventFactory.persist_one(DomainEventData(
        event_type=event_type, workspace_id=entry.workspace_id,
        aggregate_type="journal_entry", aggregate_id=entry.id, version=version,
        payload={"entry_number": entry.entry_number, "status": entry.status,
                 "source_module": entry.source_module, "source_ref": entry.source_ref, **payload},
        actor_id=uuid.UUID(str(actor_id)) if actor_id else uuid.UUID(int=0)))


def emit_post_failure(workspace_id, *, module, source_ref, error, actor_id=None) -> None:
    """Record a GL posting failure VISIBLY (P2.15 Blocker 3 — no silent accounting loss):
    a structured ``logging.error`` (survives any DB rollback) plus a ``ledger.post.failed``
    domain event carrying workspace/module/record/error. Callers emit this and then re-raise,
    so the operation fails loudly instead of silently dropping the entry."""
    logger.error(
        "GL posting failed: workspace=%s module=%s source_ref=%s error=%s",
        workspace_id, module, source_ref, error)
    from apps.eventstore.models import DomainEvent
    agg = uuid.uuid5(_POST_FAILURE_NS, f"{workspace_id}:{module}:{source_ref}")
    version = DomainEvent.objects.filter(aggregate_id=agg).count() + 1
    DomainEventFactory.persist_one(DomainEventData(
        event_type="ledger.post.failed", workspace_id=workspace_id,
        aggregate_type="ledger_posting", aggregate_id=agg, version=version,
        payload={"module": str(module), "source_ref": str(source_ref), "error": str(error)},
        actor_id=uuid.UUID(str(actor_id)) if actor_id else uuid.UUID(int=0)))


def _resolve_period(workspace_id, date) -> AccountingPeriod | None:
    """Find the period covering ``date``. Reject if it is closed/locked; ``None`` if no period
    covers the date (period management is optional until P2.3 sets up fiscal years)."""
    period = (AccountingPeriod.objects
              .filter(workspace_id=workspace_id, start_date__lte=date, end_date__gte=date)
              .order_by("start_date").first())
    if period is not None and period.status != AccountingPeriod.OPEN:
        raise LedgerError(f"Period {period.code} is {period.status}; cannot post on {date}.")
    return period


def _base_code(workspace_id) -> str:
    """The workspace base currency, or "" when no currency master is configured (→ single-currency
    legacy behaviour). Lazy + fail-open so the ledger never depends on the currency app being set up."""
    try:
        from apps.currency.services import CurrencyService
        return CurrencyService.base_code(workspace_id)
    except Exception:  # noqa: BLE001 — currency app absent/unconfigured → legacy single-currency
        return ""


def _base_rate(workspace_id, currency, date) -> Decimal:
    try:
        from apps.currency.services import CurrencyService
        return CurrencyService.base_rate(workspace_id, currency, on_date=date)
    except LedgerError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise LedgerError(f"FX rate for {currency!r} unavailable: {type(exc).__name__}") from exc


def _normalize_lines(workspace_id, lines, *, date=None) -> list[dict]:
    """Validate/normalize raw line dicts → resolved account + Decimal sides + base-currency equivalents.
    Each line must carry a non-negative amount on exactly one side and reference an active, postable
    account. BACKWARD-COMPATIBLE: a line with no ``currency`` (the legacy path) gets fx_rate=1 and
    base_* == the transaction amount, and the balance is checked on transaction amounts exactly as
    before; a MIXED-currency entry is instead balanced on the base-currency amounts."""
    if not lines or len(lines) < 2:
        raise LedgerError("A journal entry needs at least two lines.")
    out = []
    base_ccy = _base_code(workspace_id)
    # Cache account lookups within the workspace.
    by_code = {a.code: a for a in LedgerAccount.objects.filter(workspace_id=workspace_id)}
    by_id = {str(a.id): a for a in by_code.values()}
    for i, raw in enumerate(lines):
        acct = None
        if raw.get("account_id"):
            acct = by_id.get(str(raw["account_id"]))
        elif raw.get("account_code"):
            acct = by_code.get(str(raw["account_code"]))
        if acct is None:
            raise LedgerError(f"Line {i + 1}: unknown account {raw.get('account_code') or raw.get('account_id')!r}.")
        if not acct.is_active:
            raise LedgerError(f"Line {i + 1}: account {acct.code} is inactive.")
        if acct.is_group:
            raise LedgerError(f"Line {i + 1}: account {acct.code} is a group/header and cannot be posted to.")
        debit = _money(raw.get("debit", 0))
        credit = _money(raw.get("credit", 0))
        if debit < 0 or credit < 0:
            raise LedgerError(f"Line {i + 1}: amounts must be non-negative.")
        if (debit > 0) == (credit > 0):
            raise LedgerError(f"Line {i + 1}: exactly one of debit/credit must be > 0.")
        currency = str(raw.get("currency", "") or "")
        # Resolve the base rate: explicit fx_rate wins; else convert a non-base currency to base;
        # else (legacy / base currency) rate 1.
        if raw.get("fx_rate") not in (None, ""):
            rate = Decimal(str(raw["fx_rate"]))
        elif currency and base_ccy and currency.upper() != base_ccy.upper():
            rate = _base_rate(workspace_id, currency, date)
        else:
            rate = Decimal("1")
        out.append({"account": acct, "debit": debit, "credit": credit,
                    "currency": currency, "fx_rate": rate,
                    "base_debit": _money(debit * rate), "base_credit": _money(credit * rate),
                    "memo": str(raw.get("memo", "") or "")[:500],
                    "partner_ref": str(raw.get("partner_ref", "") or "")[:128],
                    "dimensions": raw.get("dimensions") or {}})
    distinct = {(line_["currency"] or base_ccy or "").upper() for line_ in out}
    if len(distinct) <= 1:
        # Single-currency entry (base OR one foreign): balance on transaction amounts (legacy check).
        total_d = sum((line_["debit"] for line_ in out), Decimal("0"))
        total_c = sum((line_["credit"] for line_ in out), Decimal("0"))
    else:
        # Mixed-currency entry: balance on base-currency amounts.
        total_d = sum((line_["base_debit"] for line_ in out), Decimal("0"))
        total_c = sum((line_["base_credit"] for line_ in out), Decimal("0"))
    if total_d != total_c:
        raise LedgerError(f"Entry is unbalanced: debits {total_d} != credits {total_c}.")
    if total_d == 0:
        raise LedgerError("Entry total is zero.")
    _validate_dimensions(workspace_id, out, date)
    return out


def _validate_dimensions(workspace_id, out, date) -> None:
    """Validate any financial dimensions provided on the lines (F9). Runs ONLY when a line actually
    carries dimensions — legacy postings (no dimensions) skip this entirely (zero overhead / no
    behaviour change). Fail-open if the dimensions app is absent/unconfigured."""
    dimensioned = [line_ for line_ in out if line_.get("dimensions")]
    if not dimensioned:
        return
    try:
        from apps.dimensions.services import DimensionService
    except Exception:  # noqa: BLE001 — dimensions app not installed → skip
        return
    for line_ in dimensioned:
        errors = DimensionService.validate_map(workspace_id, line_["dimensions"], on_date=date)
        if errors:
            raise LedgerError(f"Line dimensions invalid: {'; '.join(errors)}")


class GLBus:
    # ── draft lifecycle ───────────────────────────────────────────────────────
    @staticmethod
    def create_draft(workspace_id, *, date, lines, memo="", currency="",
                     source_module="manual", source_ref="", company_id=None,
                     actor_id=None) -> JournalEntry:
        """Create an editable draft entry. Lines are persisted but the balance is only enforced
        at post time, so a half-built draft can be saved."""
        with transaction.atomic():
            entry = JournalEntry.objects.create(
                workspace_id=workspace_id, date=date, memo=memo, currency=currency,
                status=JournalEntry.DRAFT, source_module=source_module, source_ref=source_ref,
                company_id=uuid.UUID(str(company_id)) if company_id else None,
                created_by=uuid.UUID(str(actor_id)) if actor_id else None)
            GLBus._write_lines(workspace_id, entry, lines, validate=False)
            _emit(entry, "ledger.journal.drafted", {}, actor_id=actor_id)
            return entry

    @staticmethod
    def _write_lines(workspace_id, entry, lines, *, validate=True):
        if validate:
            norm = _normalize_lines(workspace_id, lines)
        else:
            # lenient: resolve accounts best-effort for a draft
            norm = []
            accts = {a.code: a for a in LedgerAccount.objects.filter(workspace_id=workspace_id)}
            ids = {str(a.id): a for a in accts.values()}
            for raw in lines or []:
                acct = ids.get(str(raw.get("account_id"))) or accts.get(str(raw.get("account_code")))
                if acct is None:
                    continue
                debit = _money(raw.get("debit", 0))
                credit = _money(raw.get("credit", 0))
                rate = Decimal(str(raw["fx_rate"])) if raw.get("fx_rate") not in (None, "") \
                    else Decimal("1")
                norm.append({"account": acct, "debit": debit, "credit": credit,
                             "currency": str(raw.get("currency", "") or ""), "fx_rate": rate,
                             "base_debit": _money(debit * rate), "base_credit": _money(credit * rate),
                             "memo": str(raw.get("memo", "") or "")[:500],
                             "partner_ref": str(raw.get("partner_ref", "") or "")[:128],
                             "dimensions": raw.get("dimensions") or {}})
        entry.lines.all().delete()
        for n, line_ in enumerate(norm, start=1):
            JournalLine.objects.create(workspace_id=workspace_id, entry=entry, line_no=n, **line_)
        return norm

    # ── posting ───────────────────────────────────────────────────────────────
    @staticmethod
    def post(workspace_id, *, date, lines, memo="", currency="", source_module="manual",
             source_ref="", posting_rule_key="", company_id=None, ledger_id=None,
             actor_id=None) -> JournalEntry:
        """Create AND post a balanced entry in one atomic step. ``company_id``/``ledger_id`` (F11)
        optionally tag the entry's legal entity + set of books — NULL keeps single-company/single-ledger
        behaviour unchanged."""
        with transaction.atomic():
            period = _resolve_period(workspace_id, date)
            norm = _normalize_lines(workspace_id, lines, date=date)
            entry = JournalEntry.objects.create(
                workspace_id=workspace_id, date=date, memo=memo, currency=currency,
                period=period, status=JournalEntry.DRAFT, source_module=source_module,
                source_ref=source_ref, posting_rule_key=posting_rule_key,
                company_id=uuid.UUID(str(company_id)) if company_id else None,
                ledger_id=uuid.UUID(str(ledger_id)) if ledger_id else None,
                created_by=uuid.UUID(str(actor_id)) if actor_id else None)
            for n, line_ in enumerate(norm, start=1):
                JournalLine.objects.create(workspace_id=workspace_id, entry=entry, line_no=n, **line_)
            return GLBus._finalize_post(workspace_id, entry, actor_id=actor_id)

    @staticmethod
    def post_draft(workspace_id, entry_id, *, actor_id=None) -> JournalEntry:
        """Validate + post an existing draft."""
        with transaction.atomic():
            entry = (JournalEntry.objects.select_for_update()
                     .filter(workspace_id=workspace_id, id=entry_id).first())
            if entry is None:
                raise LedgerError("Journal entry not found.")
            if entry.status != JournalEntry.DRAFT:
                raise LedgerError(f"Only draft entries can be posted (this is {entry.status}).")
            # Re-validate the persisted lines (carry currency/rate so multi-currency drafts balance).
            _normalize_lines(workspace_id, [
                {"account_id": str(line_.account_id), "debit": line_.debit, "credit": line_.credit,
                 "currency": line_.currency, "fx_rate": line_.fx_rate, "dimensions": line_.dimensions}
                for line_ in entry.lines.all()], date=entry.date)
            entry.period = _resolve_period(workspace_id, entry.date)
            return GLBus._finalize_post(workspace_id, entry, actor_id=actor_id)

    @staticmethod
    def _finalize_post(workspace_id, entry, *, actor_id=None) -> JournalEntry:
        NumberingService.ensure_sequence(
            workspace_id, "journal_entry",
            defaults={"name": "Journal Entry", "prefix": "JE-", "padding": 6})
        entry.entry_number = NumberingService.allocate(
            workspace_id, "journal_entry", actor_id=actor_id,
            context={"source_module": entry.source_module, "source_ref": entry.source_ref})
        entry.status = JournalEntry.POSTED
        entry.posted_at = timezone.now()
        entry.posted_by = uuid.UUID(str(actor_id)) if actor_id else None
        entry.save(update_fields=["entry_number", "status", "posted_at", "posted_by",
                                  "period", "updated_at"])
        _emit(entry, "ledger.journal.posted",
              {"total": str(sum((line_.debit for line_ in entry.lines.all()), Decimal("0")))},
              actor_id=actor_id)
        return entry

    @staticmethod
    def reverse(workspace_id, entry_id, *, date=None, memo="", actor_id=None) -> JournalEntry:
        """Post a reversing entry (debit↔credit swapped) and mark the original reversed.
        This is the ONLY way to change a posted entry — posted books stay immutable."""
        with transaction.atomic():
            original = (JournalEntry.objects.select_for_update()
                        .filter(workspace_id=workspace_id, id=entry_id).first())
            if original is None:
                raise LedgerError("Journal entry not found.")
            if original.status != JournalEntry.POSTED:
                raise LedgerError("Only posted entries can be reversed.")
            rev_lines = [{"account_id": str(line_.account_id),
                          "debit": line_.credit, "credit": line_.debit,
                          "currency": line_.currency, "fx_rate": line_.fx_rate,
                          "memo": line_.memo, "partner_ref": line_.partner_ref,
                          "dimensions": line_.dimensions}
                         for line_ in original.lines.all().order_by("line_no")]
            rev_date = date or timezone.now().date()
            period = _resolve_period(workspace_id, rev_date)
            norm = _normalize_lines(workspace_id, rev_lines, date=rev_date)
            rev = JournalEntry.objects.create(
                workspace_id=workspace_id, date=rev_date,
                memo=memo or f"Reversal of {original.entry_number}", currency=original.currency,
                period=period, status=JournalEntry.DRAFT, source_module=original.source_module,
                source_ref=original.source_ref, reverses=original,
                company_id=original.company_id, ledger_id=original.ledger_id,
                created_by=uuid.UUID(str(actor_id)) if actor_id else None)
            for n, line_ in enumerate(norm, start=1):
                JournalLine.objects.create(workspace_id=workspace_id, entry=rev, line_no=n, **line_)
            GLBus._finalize_post(workspace_id, rev, actor_id=actor_id)
            original.status = JournalEntry.REVERSED
            original.save(update_fields=["status", "updated_at"])
            _emit(original, "ledger.journal.reversed",
                  {"reversal_entry": str(rev.id), "reversal_number": rev.entry_number},
                  actor_id=actor_id)
            return rev

    # ── event-driven posting ────────────────────────────────────────────────────
    @staticmethod
    def post_event(workspace_id, event_type, context, *, date=None, source_module="",
                   source_ref="", actor_id=None) -> JournalEntry | None:
        """Resolve the active ``PostingRule`` for ``event_type`` and post the templated entry.
        Returns ``None`` (no error) when no rule is configured, so emitting modules stay decoupled."""
        rule = PostingRule.objects.filter(
            workspace_id=workspace_id, event_type=event_type, is_active=True).first()
        if rule is None:
            return None
        lines = GLBus._build_lines_from_template(rule.template, context)
        if not lines:
            raise LedgerError(f"Posting rule {event_type!r} produced no lines.")
        return GLBus.post(
            workspace_id, date=date or timezone.now().date(), lines=lines,
            memo=context.get("memo", rule.name or event_type),
            currency=context.get("currency", ""),
            source_module=source_module or event_type.split(".")[0],
            source_ref=source_ref or str(context.get("source_ref", "")),
            posting_rule_key=event_type, company_id=context.get("company_id"),
            ledger_id=context.get("ledger_id"), actor_id=actor_id)

    @staticmethod
    def _build_lines_from_template(template, context) -> list[dict]:
        lines = []
        for spec in template or []:
            if "fixed_amount" in spec:
                amount = _money(spec["fixed_amount"])
            else:
                amount = _money(context.get(spec.get("amount_field", "amount"), 0))
            if amount <= 0:
                continue
            side = spec.get("side", "debit")
            # ``account_field`` reads the account code from the event context (e.g. a per-item
            # override), falling back to the rule's static ``account_code`` when absent/blank.
            account_code = spec.get("account_code")
            if spec.get("account_field"):
                account_code = context.get(spec["account_field"]) or account_code
            lines.append({
                "account_code": account_code,
                "account_id": spec.get("account_id"),
                "debit": amount if side == "debit" else 0,
                "credit": amount if side == "credit" else 0,
                "memo": spec.get("memo", ""),
                "partner_ref": str(context.get("partner_ref", "")),
            })
        return lines

    # ── balances (used by P2.3 reports; lightweight helper here) ─────────────────
    @staticmethod
    def account_balance(workspace_id, account_id, *, as_of=None, company_id=None) -> Decimal:
        """Net movement on an account (debit − credit), optionally up to ``as_of`` date.

        Includes both POSTED and REVERSED entries: a reversed entry's lines really hit the books
        and are cancelled by its (also-posted) reversing entry, so both must be summed for the GL
        to balance — ``reversed`` is a workflow status, not a removal from the ledger.

        ``company_id`` (F11) optionally scopes to one legal entity; when omitted the balance is the
        whole workspace exactly as before (single-company byte-identical)."""
        qs = JournalLine.objects.filter(
            workspace_id=workspace_id, account_id=account_id,
            entry__status__in=[JournalEntry.POSTED, JournalEntry.REVERSED])
        if as_of is not None:
            qs = qs.filter(entry__date__lte=as_of)
        if company_id is not None:
            qs = qs.filter(entry__company_id=company_id)
        # Balances are reported in the BASE currency. Legacy rows were backfilled base_* == txn, so
        # single-currency workspaces are unaffected.
        total_d = sum((line_.base_debit for line_ in qs), Decimal("0"))
        total_c = sum((line_.base_credit for line_ in qs), Decimal("0"))
        return (total_d - total_c).quantize(CENTS)


# Backwards-friendly alias — the "posting service" name used in the readiness plan.
PostingService = GLBus
