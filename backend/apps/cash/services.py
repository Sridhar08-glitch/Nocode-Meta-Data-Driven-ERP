"""
Cash Management & Bank Reconciliation services (Financial Platform — F8).

Three reusable entry points, all package-independent:
  * ``CashService``          — bank/cash accounts, transfers (post ONE GL entry via GLBus), cash
                               instruments (cheque/deposit/EFT tracking), cash position + bank balance.
  * ``ReconciliationService``— import a bank statement, open a reconciliation, compute the book vs
                               statement position + outstanding items, and complete it.
  * ``MatchingService``      — deterministic (no-AI) matching of statement lines ⇄ GL journal lines:
                               exact / reference / tolerance (auto 1:1) and manual group matching
                               (partial / split / one-to-many / many-to-one), with duplicate prevention.

GL OWNERSHIP: reconciliation REFERENCES ``JournalLine`` by id and posts NO accounting; the only GL
posting is a real cash transfer. Idempotent on ``external_ref``; workspace-scoped.
"""
from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from apps.ledger.models import JournalEntry, JournalLine, LedgerAccount
from apps.solution_templates.documents import emit_event

from .models import (
    IN,
    BankReconciliation,
    BankStatement,
    BankStatementLine,
    BankTransfer,
    CashInstrument,
    ReconciliationMatch,
)

CENTS = Decimal("0.01")
_POSTED = [JournalEntry.POSTED, JournalEntry.REVERSED]


class CashError(Exception):  # noqa: N818 — domain error
    pass


def _m(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(CENTS, rounding=ROUND_HALF_UP)


def _uid(actor_id):
    return uuid.UUID(str(actor_id)) if actor_id else None


class CashService:
    @staticmethod
    def ensure_account(*, workspace_id, code, name="", account_type="bank", gl_account_code="",
                       currency="", bank_name="", account_number="", actor_id=None):
        from .models import BankAccount
        acct, _ = BankAccount.objects.get_or_create(
            workspace_id=workspace_id, code=str(code),
            defaults={"name": name or code, "account_type": account_type,
                      "gl_account_code": gl_account_code, "currency": currency,
                      "bank_name": bank_name, "account_number": account_number,
                      "created_by": _uid(actor_id)})
        return acct

    @staticmethod
    def bank_balance(workspace_id, bank_account) -> Decimal:
        """The GL book balance of the account's cash control account (single source of truth)."""
        if not bank_account.gl_account_code:
            return Decimal("0.00")
        from apps.ledger.services import GLBus
        acct = LedgerAccount.objects.filter(
            workspace_id=workspace_id, code=bank_account.gl_account_code).first()
        return GLBus.account_balance(workspace_id, acct.id) if acct else Decimal("0.00")

    @staticmethod
    def cash_position(workspace_id) -> dict:
        """Available cash across all active bank/cash accounts (book balances)."""
        from .models import BankAccount
        rows, total = [], Decimal("0")
        for acct in BankAccount.objects.filter(workspace_id=workspace_id, is_active=True):
            bal = CashService.bank_balance(workspace_id, acct)
            total += bal
            rows.append({"code": acct.code, "name": acct.name, "type": acct.account_type,
                         "currency": acct.currency, "balance": str(_m(bal))})
        return {"accounts": rows, "total_available": str(_m(total))}

    @staticmethod
    def post_transfer(*, workspace_id, from_account, to_account, amount, transfer_date=None,
                      memo="", external_ref="", post_gl=True, actor_id=None) -> BankTransfer:
        """Record + post a transfer between own accounts. Posts ONE GL entry (Dr destination cash /
        Cr source cash) through GLBus — no duplicate accounting. Idempotent on ``external_ref``."""
        from .models import BankAccount
        amt = _m(amount)
        if amt <= 0:
            raise CashError("Transfer amount must be positive.")
        src = BankAccount.objects.filter(workspace_id=workspace_id, id=from_account).first()
        dst = BankAccount.objects.filter(workspace_id=workspace_id, id=to_account).first()
        if src is None or dst is None:
            raise CashError("Bank account not found.")
        if src.id == dst.id:
            raise CashError("Source and destination must differ.")
        ttype = f"{'cash' if src.account_type == 'cash' else 'bank'}_to_" \
                f"{'cash' if dst.account_type == 'cash' else 'bank'}"
        with transaction.atomic():
            if external_ref:
                dup = (BankTransfer.objects.select_for_update()
                       .filter(workspace_id=workspace_id, external_ref=external_ref)
                       .exclude(status=BankTransfer.CANCELLED).first())
                if dup is not None:
                    return dup
            from apps.numbering.services import NumberingService
            NumberingService.ensure_sequence(
                workspace_id, "bank_transfer", defaults={"prefix": "BT-", "padding": 6},
                created_by=actor_id)
            number = NumberingService.allocate(
                workspace_id, "bank_transfer", actor_id=actor_id,
                context={"source_module": "cash", "source_ref": "transfer"})
            xfer = BankTransfer.objects.create(
                workspace_id=workspace_id, number=number, transfer_type=ttype,
                from_account=src, to_account=dst, amount=amt, currency=src.currency,
                transfer_date=transfer_date or timezone.now().date(), memo=memo,
                external_ref=str(external_ref or ""), status=BankTransfer.COMPLETED,
                created_by=_uid(actor_id))
            if post_gl and src.gl_account_code and dst.gl_account_code:
                xfer.journal_entry_id = CashService._post_transfer_gl(
                    workspace_id, xfer, src, dst, actor_id)
                xfer.save(update_fields=["journal_entry_id"])
        emit_event(workspace_id, "bank_transfer", xfer.id, "cash.transfer.posted",
                   {"number": number, "amount": str(amt), "type": ttype}, actor_id)
        return xfer

    @staticmethod
    def _post_transfer_gl(workspace_id, xfer, src, dst, actor_id):
        from apps.ledger.services import GLBus, LedgerError, emit_post_failure
        try:
            entry = GLBus.post(
                workspace_id, date=xfer.transfer_date, lines=[
                    {"account_code": dst.gl_account_code, "debit": str(xfer.amount),
                     "memo": f"Transfer {xfer.number}"},
                    {"account_code": src.gl_account_code, "credit": str(xfer.amount),
                     "memo": f"Transfer {xfer.number}"}],
                memo=xfer.memo or f"Transfer {xfer.number}", currency=xfer.currency,
                source_module="cash", source_ref=xfer.number, actor_id=actor_id)
            return entry.id if entry is not None else None
        except LedgerError as exc:
            emit_post_failure(workspace_id, module="cash", source_ref=xfer.number,
                              error=str(exc), actor_id=actor_id)
            raise

    @staticmethod
    def record_instrument(*, workspace_id, bank_account, amount, instrument_type="cheque_received",
                          direction=IN, reference="", counterparty="", partner_ref="",
                          issue_date=None, external_ref="", actor_id=None) -> CashInstrument:
        from .models import BankAccount
        acct = BankAccount.objects.filter(workspace_id=workspace_id, id=bank_account).first()
        if acct is None:
            raise CashError("Bank account not found.")
        from apps.numbering.services import NumberingService
        NumberingService.ensure_sequence(
            workspace_id, "cash_instrument", defaults={"prefix": "CI-", "padding": 6},
            created_by=actor_id)
        number = NumberingService.allocate(
            workspace_id, "cash_instrument", actor_id=actor_id,
            context={"source_module": "cash", "source_ref": instrument_type})
        inst = CashInstrument.objects.create(
            workspace_id=workspace_id, number=number, instrument_type=instrument_type,
            bank_account=acct, amount=_m(amount), direction=direction, reference=reference,
            counterparty=counterparty, partner_ref=partner_ref, issue_date=issue_date,
            status=CashInstrument.PENDING, created_by=_uid(actor_id))
        emit_event(workspace_id, "cash_instrument", inst.id, "cash.instrument.recorded",
                   {"number": number, "type": instrument_type, "amount": str(_m(amount))}, actor_id)
        return inst

    @staticmethod
    def set_instrument_status(*, workspace_id, instrument_id, status, clearing_date=None,
                              actor_id=None) -> CashInstrument:
        valid = {s for s, _ in CashInstrument.STATUS_CHOICES}
        if status not in valid:
            raise CashError(f"Invalid instrument status {status!r}.")
        with transaction.atomic():
            inst = (CashInstrument.objects.select_for_update()
                    .filter(workspace_id=workspace_id, id=instrument_id).first())
            if inst is None:
                raise CashError("Instrument not found.")
            inst.status = status
            if clearing_date:
                inst.clearing_date = clearing_date
            inst.save(update_fields=["status", "clearing_date", "updated_at"])
        emit_event(workspace_id, "cash_instrument", inst.id, f"cash.instrument.{status}",
                   {"number": inst.number}, actor_id)
        return inst


class ReconciliationService:
    @staticmethod
    def import_statement(*, workspace_id, bank_account, lines, statement_ref="", statement_date=None,
                         opening_balance=0, closing_balance=0, currency="", external_ref="",
                         actor_id=None) -> BankStatement:
        """Import a bank statement + its lines (idempotent on ``external_ref``). ``lines`` = list of
        {line_date, amount, direction (in/out), reference, description, counterparty}."""
        from .models import BankAccount
        acct = BankAccount.objects.filter(workspace_id=workspace_id, id=bank_account).first()
        if acct is None:
            raise CashError("Bank account not found.")
        with transaction.atomic():
            if external_ref:
                dup = (BankStatement.objects.filter(
                    workspace_id=workspace_id, external_ref=external_ref).first())
                if dup is not None:
                    return dup
            stmt = BankStatement.objects.create(
                workspace_id=workspace_id, bank_account=acct, statement_ref=statement_ref,
                statement_date=statement_date, opening_balance=_m(opening_balance),
                closing_balance=_m(closing_balance), currency=currency or acct.currency,
                external_ref=str(external_ref or ""), status=BankStatement.IMPORTED,
                created_by=_uid(actor_id))
            for raw in lines or []:
                BankStatementLine.objects.create(
                    workspace_id=workspace_id, statement=stmt, bank_account=acct,
                    line_date=raw.get("line_date"), amount=_m(raw.get("amount")),
                    direction=raw.get("direction", IN), reference=str(raw.get("reference", "") or ""),
                    description=str(raw.get("description", "") or ""),
                    counterparty=str(raw.get("counterparty", "") or ""))
        emit_event(workspace_id, "bank_statement", stmt.id, "cash.statement.imported",
                   {"ref": statement_ref, "lines": len(lines or [])}, actor_id)
        return stmt

    @staticmethod
    def open_reconciliation(*, workspace_id, bank_account, statement=None, reconciliation_date=None,
                            actor_id=None) -> BankReconciliation:
        from .models import BankAccount
        acct = BankAccount.objects.filter(workspace_id=workspace_id, id=bank_account).first()
        if acct is None:
            raise CashError("Bank account not found.")
        stmt = None
        if statement:
            stmt = BankStatement.objects.filter(workspace_id=workspace_id, id=statement).first()
        rec = BankReconciliation.objects.create(
            workspace_id=workspace_id, bank_account=acct, statement=stmt,
            reconciliation_date=reconciliation_date
            or (stmt.statement_date if stmt else timezone.now().date()),
            statement_balance=stmt.closing_balance if stmt else Decimal("0"),
            status=BankReconciliation.IN_PROGRESS, created_by=_uid(actor_id))
        ReconciliationService.refresh(workspace_id, rec)
        return rec

    @staticmethod
    def _book_lines(workspace_id, rec, *, only_unmatched=False):
        """GL journal lines on the bank's cash account up to the reconciliation date."""
        acct = LedgerAccount.objects.filter(
            workspace_id=workspace_id, code=rec.bank_account.gl_account_code).first()
        if acct is None:
            return []
        qs = JournalLine.objects.filter(
            workspace_id=workspace_id, account_id=acct.id, entry__status__in=_POSTED)
        if rec.reconciliation_date:
            qs = qs.filter(entry__date__lte=rec.reconciliation_date)
        rows = list(qs.select_related("entry"))
        if only_unmatched:
            matched_ids = set(ReconciliationMatch.objects.filter(
                workspace_id=workspace_id, journal_line_id__isnull=False
            ).values_list("journal_line_id", flat=True))
            rows = [r for r in rows if r.id not in matched_ids]
        return rows

    @staticmethod
    def refresh(workspace_id, rec) -> BankReconciliation:
        """Recompute the book balance, outstanding items and the reconciliation difference."""
        book_balance = sum((ln.debit - ln.credit for ln in
                            ReconciliationService._book_lines(workspace_id, rec)), Decimal("0"))
        unmatched_book = sum((ln.debit - ln.credit for ln in
                              ReconciliationService._book_lines(
                                  workspace_id, rec, only_unmatched=True)), Decimal("0"))
        stmt_balance = rec.statement.closing_balance if rec.statement else rec.statement_balance
        unmatched_stmt = Decimal("0")
        if rec.statement:
            for line in rec.statement.lines.filter(status=BankStatementLine.UNMATCHED):
                unmatched_stmt += line.signed
        # Adjusted book (add bank-only items, remove in-transit book items) should equal statement.
        reconciled_balance = _m(book_balance + unmatched_stmt - unmatched_book)
        rec.book_balance = _m(book_balance)
        rec.statement_balance = _m(stmt_balance)
        rec.reconciled_balance = reconciled_balance
        rec.difference = _m(stmt_balance - reconciled_balance)
        rec.save(update_fields=["book_balance", "statement_balance", "reconciled_balance",
                                "difference", "updated_at"])
        return rec

    @staticmethod
    def outstanding_items(workspace_id, rec) -> dict:
        """Items explaining the book↔statement difference: unreconciled book lines (in transit) +
        unmatched statement lines (bank-only)."""
        book = [{"journal_line_id": str(ln.id), "date": str(ln.entry.date),
                 "amount": str(_m(ln.debit - ln.credit)), "memo": ln.memo or ln.entry.memo}
                for ln in ReconciliationService._book_lines(workspace_id, rec, only_unmatched=True)]
        stmt = []
        if rec.statement:
            for line in rec.statement.lines.filter(status=BankStatementLine.UNMATCHED):
                stmt.append({"line_id": str(line.id), "date": str(line.line_date),
                             "amount": str(_m(line.signed)), "reference": line.reference})
        return {"outstanding_book": book, "outstanding_statement": stmt}

    @staticmethod
    def complete(*, workspace_id, reconciliation_id, tolerance=0, actor_id=None) -> BankReconciliation:
        with transaction.atomic():
            rec = (BankReconciliation.objects.select_for_update()
                   .filter(workspace_id=workspace_id, id=reconciliation_id).first())
            if rec is None:
                raise CashError("Reconciliation not found.")
            ReconciliationService.refresh(workspace_id, rec)
            if abs(rec.difference) > _m(tolerance):
                raise CashError(
                    f"Cannot complete: unexplained difference {rec.difference} exceeds tolerance.")
            rec.status = BankReconciliation.RECONCILED
            rec.reconciled_by = _uid(actor_id)
            rec.reconciled_at = timezone.now()
            rec.save(update_fields=["status", "reconciled_by", "reconciled_at", "updated_at"])
            if rec.statement:
                rec.statement.status = BankStatement.RECONCILED
                rec.statement.save(update_fields=["status", "updated_at"])
        emit_event(workspace_id, "bank_reconciliation", rec.id, "cash.reconciliation.completed",
                   {"difference": str(rec.difference)}, actor_id)
        return rec


class MatchingService:
    """Deterministic (no-AI) reconciliation matching."""

    @staticmethod
    def auto_match(*, workspace_id, reconciliation_id, amount_tolerance=0, date_tolerance_days=5,
                   actor_id=None) -> dict:
        """Auto-match statement lines to unreconciled GL book lines 1:1, in deterministic priority:
        reference+amount, then exact amount+date, then amount-within-tolerance+date."""
        rec = BankReconciliation.objects.filter(
            workspace_id=workspace_id, id=reconciliation_id).first()
        if rec is None or rec.statement is None:
            raise CashError("Reconciliation or statement not found.")
        tol = _m(amount_tolerance)
        book = {ln.id: ln for ln in ReconciliationService._book_lines(
            workspace_id, rec, only_unmatched=True)}
        stmt_lines = list(rec.statement.lines.filter(status=BankStatementLine.UNMATCHED))
        made = {"reference": 0, "exact": 0, "tolerance": 0}

        def _pick(line, predicate):
            for bid, bln in list(book.items()):
                if predicate(line, bln):
                    return bid, bln
            return None, None

        def _amount_eq(line, bln):
            return _m(bln.debit - bln.credit) == _m(line.signed)

        def _date_ok(line, bln):
            if not line.line_date or not bln.entry.date:
                return True
            return abs((line.line_date - bln.entry.date).days) <= date_tolerance_days

        for line in stmt_lines:
            # Pass 1 — reference + amount
            bid, bln = _pick(line, lambda ln_, b_: _amount_eq(ln_, b_) and ln_.reference and (
                ln_.reference in (b_.partner_ref or "") or ln_.reference in (b_.memo or "")))
            mtype = "reference"
            if bid is None:  # Pass 2 — exact amount + date
                bid, bln = _pick(line, lambda ln_, b_: _amount_eq(ln_, b_) and _date_ok(ln_, b_))
                mtype = "exact"
            if bid is None and tol > 0:  # Pass 3 — amount tolerance + date
                bid, bln = _pick(line, lambda ln_, b_: abs(
                    _m(b_.debit - b_.credit) - _m(ln_.signed)) <= tol and _date_ok(ln_, b_))
                mtype = "tolerance"
            if bid is not None:
                MatchingService._create_match(workspace_id, rec, line, bln.id,
                                              _m(line.amount), mtype, actor_id)
                book.pop(bid, None)
                made[mtype] += 1
        ReconciliationService.refresh(workspace_id, rec)
        return {"matched": sum(made.values()), **made}

    @staticmethod
    def match_group(*, workspace_id, reconciliation_id, statement_line_ids=None,
                    journal_line_ids=None, amount=None, tolerance=0, actor_id=None) -> dict:
        """Manual group match — supports split / one-to-many / many-to-one / partial. The signed sum of
        the chosen statement lines must equal the net movement of the chosen book lines (within
        tolerance), unless an explicit ``amount`` is given (partial)."""
        rec = BankReconciliation.objects.filter(
            workspace_id=workspace_id, id=reconciliation_id).first()
        if rec is None:
            raise CashError("Reconciliation not found.")
        stmt_lines = list(BankStatementLine.objects.filter(
            workspace_id=workspace_id, id__in=statement_line_ids or []))
        book_lines = list(JournalLine.objects.filter(
            workspace_id=workspace_id, id__in=journal_line_ids or []))
        if not stmt_lines and not book_lines:
            raise CashError("Nothing to match.")
        # Duplicate prevention: reject already-matched book lines.
        already = set(ReconciliationMatch.objects.filter(
            workspace_id=workspace_id,
            journal_line_id__in=[b.id for b in book_lines]).values_list("journal_line_id", flat=True))
        if already:
            raise CashError("One or more journal lines are already matched.")
        stmt_sum = sum((ln.signed for ln in stmt_lines), Decimal("0"))
        book_sum = sum((ln.debit - ln.credit for ln in book_lines), Decimal("0"))
        if amount is None and abs(_m(stmt_sum) - _m(book_sum)) > _m(tolerance):
            raise CashError(
                f"Group does not balance: statement {stmt_sum} vs book {book_sum}.")
        match_amount = _m(amount) if amount is not None else _m(abs(stmt_sum) or abs(book_sum))
        with transaction.atomic():
            for line in stmt_lines:
                MatchingService._create_match(workspace_id, rec, line, None,
                                              _m(abs(line.signed)), "manual", actor_id, refresh=False)
            for bln in book_lines:
                MatchingService._create_match(workspace_id, rec, None, bln.id,
                                              _m(abs(bln.debit - bln.credit)), "manual", actor_id,
                                              refresh=False)
        ReconciliationService.refresh(workspace_id, rec)
        return {"matched": True, "statement_lines": len(stmt_lines),
                "journal_lines": len(book_lines), "amount": str(match_amount)}

    @staticmethod
    def _create_match(workspace_id, rec, statement_line, journal_line_id, amount, match_type,
                      actor_id, *, refresh=True):
        ReconciliationMatch.objects.create(
            workspace_id=workspace_id, reconciliation=rec, bank_account=rec.bank_account,
            statement_line=statement_line, journal_line_id=journal_line_id, amount=amount,
            match_type=match_type, created_by=_uid(actor_id))
        if statement_line is not None:
            statement_line.matched_amount = _m(statement_line.matched_amount + amount)
            statement_line.status = (BankStatementLine.MATCHED
                                     if statement_line.matched_amount >= statement_line.amount
                                     else BankStatementLine.UNMATCHED)
            statement_line.save(update_fields=["matched_amount", "status", "updated_at"])

    @staticmethod
    def unmatch(*, workspace_id, match_id, actor_id=None) -> dict:
        with transaction.atomic():
            match = (ReconciliationMatch.objects.select_for_update()
                     .filter(workspace_id=workspace_id, id=match_id).first())
            if match is None:
                return {"unmatched": False, "reason": "not_found"}
            line = match.statement_line
            rec = match.reconciliation
            amount = match.amount
            if line is not None:
                line.matched_amount = _m(line.matched_amount - amount)
                line.status = BankStatementLine.UNMATCHED
                line.save(update_fields=["matched_amount", "status", "updated_at"])
            match.delete()
        ReconciliationService.refresh(workspace_id, rec)
        return {"unmatched": True, "amount": str(amount)}
