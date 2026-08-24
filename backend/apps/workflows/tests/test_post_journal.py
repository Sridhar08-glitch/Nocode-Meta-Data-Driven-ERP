"""
Platform capability test: the ``action_post_journal`` workflow step executor.

This is a CORE platform test (not a package test). It proves the generic, metadata-driven
journal-posting step reuses the GL engine (GLBus / PostingRule / AccountingSettings /
JournalEntry / numbering / audit) without duplicating any ledger logic, is idempotent, balanced,
workspace-isolated, and decoupled (no rule ⇒ no error).
"""
import uuid
from types import SimpleNamespace

import pytest

from apps.ledger.models import JournalEntry, PostingRule
from apps.ledger.provisioning import provision_accounting
from apps.workflows.executors import ExecutorError, exec_post_journal


def _run(ws, actor=None):
    return SimpleNamespace(workspace_id=ws, initiated_by=actor or uuid.uuid4(),
                           record_id=None, definition_id=None)


def _step(config):
    return SimpleNamespace(config=config)


@pytest.fixture
def ws(db):
    w = uuid.uuid4()
    provision_accounting(w)          # seeds chart of accounts + settings + default rules
    return w


# ── successful posting + context resolution + balance ─────────────────────────
@pytest.mark.django_db
def test_shorthand_posts_balanced_entry_from_context(ws):
    out = exec_post_journal(
        _step({"account_debit": "1100", "account_credit": "4100",
               "amount": "{{record.amount}}", "memo": "Tuition {{record.ref}}",
               "source_module": "school", "source_ref": "{{record.ref}}"}),
        _run(ws), {"record": {"amount": "500.00", "ref": "INV-1"}}, None)

    assert out["posted"] is True
    entry = JournalEntry.objects.get(id=out["journal_entry_id"])
    assert entry.workspace_id == ws
    assert entry.status == JournalEntry.POSTED
    assert entry.source_module == "school" and entry.source_ref == "INV-1"
    lines = {ln.account.code: (ln.debit, ln.credit) for ln in entry.lines.all()}
    assert lines["1100"][0] == 500 and lines["1100"][1] == 0     # Dr A/R 500
    assert lines["4100"][1] == 500 and lines["4100"][0] == 0     # Cr Revenue 500


@pytest.mark.django_db
def test_explicit_lines_mode(ws):
    out = exec_post_journal(
        _step({"source_ref": "J-1", "lines": [
            {"account_code": "1000", "debit": "{{record.amount}}"},
            {"account_code": "1100", "credit": "{{record.amount}}"}]}),
        _run(ws), {"record": {"amount": 250}}, None)
    assert out["posted"] is True
    assert JournalEntry.objects.get(id=out["journal_entry_id"]).lines.count() == 2


# ── posting-rule mode (reuses PostingRule + AccountingSettings) ───────────────
@pytest.mark.django_db
def test_posting_rule_mode_uses_configured_rule(ws):
    PostingRule.objects.create(
        workspace_id=ws, event_type="document.invoiced", is_active=True,
        name="Invoice posting", template=[
            {"side": "debit", "account_code": "1100", "amount_field": "amount"},
            {"side": "credit", "account_code": "4100", "amount_field": "amount"}])
    out = exec_post_journal(
        _step({"posting_rule": "document.invoiced", "source_ref": "PR-1",
               "context": {"amount": "{{record.amount}}"}}),
        _run(ws), {"record": {"amount": 800}}, None)
    assert out["posted"] is True
    entry = JournalEntry.objects.get(id=out["journal_entry_id"])
    assert entry.posting_rule_key == "document.invoiced"
    assert sum(ln.debit for ln in entry.lines.all()) == 800


@pytest.mark.django_db
def test_posting_rule_absent_is_decoupled_no_error(ws):
    out = exec_post_journal(
        _step({"posting_rule": "nonexistent.event", "source_ref": "X",
               "context": {"amount": "{{record.amount}}"}}),
        _run(ws), {"record": {"amount": 100}}, None)
    assert out == {"posted": False, "reason": "no_posting_rule"}
    assert JournalEntry.objects.filter(workspace_id=ws).count() == 0


# ── idempotency / duplicate protection ───────────────────────────────────────
@pytest.mark.django_db
def test_duplicate_execution_never_double_posts(ws):
    cfg = {"account_debit": "1100", "account_credit": "4100", "amount": 300,
           "source_module": "school", "source_ref": "DUP-1"}
    first = exec_post_journal(_step(cfg), _run(ws), {}, None)
    second = exec_post_journal(_step(cfg), _run(ws), {}, None)
    assert first["posted"] is True
    assert second["posted"] is False and second["reason"] == "already_posted"
    assert second["journal_entry_id"] == first["journal_entry_id"]
    assert JournalEntry.objects.filter(
        workspace_id=ws, source_module="school", source_ref="DUP-1").count() == 1


# ── guards: zero amount, invalid account, unbalanced ─────────────────────────
@pytest.mark.django_db
def test_zero_amount_is_skipped(ws):
    out = exec_post_journal(
        _step({"account_debit": "1100", "account_credit": "4100",
               "amount": "{{record.amount}}", "source_ref": "Z-1"}),
        _run(ws), {"record": {"amount": 0}}, None)
    assert out == {"posted": False, "reason": "zero_amount"}
    assert JournalEntry.objects.filter(workspace_id=ws).count() == 0


@pytest.mark.django_db
def test_invalid_account_raises(ws):
    with pytest.raises(ExecutorError):
        exec_post_journal(
            _step({"account_debit": "9999", "account_credit": "4100", "amount": 100,
                   "source_ref": "BAD-1"}),
            _run(ws), {}, None)


@pytest.mark.django_db
def test_unbalanced_lines_raise(ws):
    with pytest.raises(ExecutorError):
        exec_post_journal(
            _step({"source_ref": "UB-1", "lines": [
                {"account_code": "1000", "debit": 100},
                {"account_code": "1100", "credit": 90}]}),
            _run(ws), {}, None)


@pytest.mark.django_db
def test_missing_config_raises(ws):
    with pytest.raises(ExecutorError):
        exec_post_journal(_step({"source_ref": "M-1"}), _run(ws), {}, None)


# ── workspace isolation ──────────────────────────────────────────────────────
@pytest.mark.django_db
def test_workspace_isolation_and_per_workspace_idempotency(ws):
    other = uuid.uuid4()
    provision_accounting(other)
    cfg = {"account_debit": "1100", "account_credit": "4100", "amount": 50,
           "source_module": "school", "source_ref": "SAME"}
    exec_post_journal(_step(cfg), _run(ws), {}, None)
    # same source_ref in a DIFFERENT workspace posts its own entry (idempotency is per-ws)
    exec_post_journal(_step(cfg), _run(other), {}, None)
    assert JournalEntry.objects.filter(workspace_id=ws).count() == 1
    assert JournalEntry.objects.filter(workspace_id=other).count() == 1
    # no leakage
    assert not JournalEntry.objects.filter(
        workspace_id=ws, id__in=JournalEntry.objects.filter(
            workspace_id=other).values("id")).exists()


@pytest.mark.django_db
def test_step_type_registered():
    from apps.workflows.executors import REGISTRY
    assert REGISTRY["action_post_journal"] is exec_post_journal
    assert REGISTRY["post_journal_entry"] is exec_post_journal
    assert REGISTRY["accounting_post"] is exec_post_journal
