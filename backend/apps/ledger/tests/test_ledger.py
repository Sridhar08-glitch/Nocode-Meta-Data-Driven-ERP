"""
General Ledger / posting bus (Phase P2.2) — double-entry invariant, immutability, period locks,
reversal, event-driven posting via rules, API, and workspace isolation.
"""
import datetime as dt
import uuid
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.ledger.models import AccountingPeriod, JournalEntry, LedgerAccount, PostingRule
from apps.ledger.services import GLBus, LedgerError
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"
BASE = "/api/v1/ledger"
TODAY = dt.date(2026, 6, 15)


@pytest.fixture
def workspace(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


def _client(workspace, role="admin", email=None):
    email = email or f"{role}@example.com"
    user = User.objects.create_user(email=email, password=PW, is_verified=True)
    WorkspaceMember.objects.create(workspace=workspace, user=user, role=role, status="active")
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                  HTTP_X_WORKSPACE_SLUG=workspace.slug)
    return c, user


def _coa(ws):
    """A minimal chart: cash (asset), revenue, expense, payable (liability)."""
    return {
        "cash": LedgerAccount.objects.create(workspace_id=ws, code="1000", name="Cash", account_type="asset"),
        "ar": LedgerAccount.objects.create(workspace_id=ws, code="1100", name="A/R", account_type="asset"),
        "rev": LedgerAccount.objects.create(workspace_id=ws, code="4000", name="Sales", account_type="revenue"),
        "ap": LedgerAccount.objects.create(workspace_id=ws, code="2000", name="A/P", account_type="liability"),
    }


# ── posting invariants ──────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestPosting:
    def test_balanced_entry_posts_and_gets_number(self):
        ws = uuid.uuid4()
        a = _coa(ws)
        entry = GLBus.post(ws, date=TODAY, lines=[
            {"account_code": "1000", "debit": "100.00"},
            {"account_code": "4000", "credit": "100.00"},
        ], memo="cash sale")
        assert entry.status == JournalEntry.POSTED
        assert entry.entry_number == "JE-000001"
        assert entry.lines.count() == 2
        assert GLBus.account_balance(ws, a["cash"].id) == Decimal("100.00")
        assert GLBus.account_balance(ws, a["rev"].id) == Decimal("-100.00")

    def test_unbalanced_entry_rejected(self):
        ws = uuid.uuid4()
        _coa(ws)
        with pytest.raises(LedgerError, match="unbalanced"):
            GLBus.post(ws, date=TODAY, lines=[
                {"account_code": "1000", "debit": "100.00"},
                {"account_code": "4000", "credit": "90.00"},
            ])

    def test_line_cannot_have_both_sides(self):
        ws = uuid.uuid4()
        _coa(ws)
        with pytest.raises(LedgerError, match="exactly one"):
            GLBus.post(ws, date=TODAY, lines=[
                {"account_code": "1000", "debit": "100.00", "credit": "100.00"},
                {"account_code": "4000", "credit": "100.00"},
            ])

    def test_single_line_rejected(self):
        ws = uuid.uuid4()
        _coa(ws)
        with pytest.raises(LedgerError, match="at least two"):
            GLBus.post(ws, date=TODAY, lines=[{"account_code": "1000", "debit": "100.00"}])

    def test_unknown_account_rejected(self):
        ws = uuid.uuid4()
        _coa(ws)
        with pytest.raises(LedgerError, match="unknown account"):
            GLBus.post(ws, date=TODAY, lines=[
                {"account_code": "9999", "debit": "10.00"},
                {"account_code": "4000", "credit": "10.00"},
            ])

    def test_group_account_not_postable(self):
        ws = uuid.uuid4()
        LedgerAccount.objects.create(workspace_id=ws, code="1", name="Assets", account_type="asset", is_group=True)
        LedgerAccount.objects.create(workspace_id=ws, code="4000", name="Sales", account_type="revenue")
        with pytest.raises(LedgerError, match="group"):
            GLBus.post(ws, date=TODAY, lines=[
                {"account_code": "1", "debit": "10.00"},
                {"account_code": "4000", "credit": "10.00"},
            ])

    def test_numbers_are_sequential(self):
        ws = uuid.uuid4()
        _coa(ws)
        e1 = GLBus.post(ws, date=TODAY, lines=[{"account_code": "1000", "debit": "1.00"}, {"account_code": "4000", "credit": "1.00"}])
        e2 = GLBus.post(ws, date=TODAY, lines=[{"account_code": "1000", "debit": "2.00"}, {"account_code": "4000", "credit": "2.00"}])
        assert (e1.entry_number, e2.entry_number) == ("JE-000001", "JE-000002")


# ── periods + immutability + reversal ─────────────────────────────────────────────
@pytest.mark.django_db
class TestPeriodsAndReversal:
    def test_cannot_post_into_locked_period(self):
        ws = uuid.uuid4()
        _coa(ws)
        AccountingPeriod.objects.create(
            workspace_id=ws, code="2026-06", start_date=dt.date(2026, 6, 1),
            end_date=dt.date(2026, 6, 30), status=AccountingPeriod.LOCKED)
        with pytest.raises(LedgerError, match="locked"):
            GLBus.post(ws, date=TODAY, lines=[
                {"account_code": "1000", "debit": "5.00"},
                {"account_code": "4000", "credit": "5.00"}])

    def test_open_period_is_attached(self):
        ws = uuid.uuid4()
        _coa(ws)
        p = AccountingPeriod.objects.create(
            workspace_id=ws, code="2026-06", start_date=dt.date(2026, 6, 1),
            end_date=dt.date(2026, 6, 30), status=AccountingPeriod.OPEN)
        entry = GLBus.post(ws, date=TODAY, lines=[
            {"account_code": "1000", "debit": "5.00"}, {"account_code": "4000", "credit": "5.00"}])
        assert entry.period_id == p.id

    def test_reverse_swaps_sides_and_marks_original(self):
        ws = uuid.uuid4()
        a = _coa(ws)
        entry = GLBus.post(ws, date=TODAY, lines=[
            {"account_code": "1000", "debit": "100.00"}, {"account_code": "4000", "credit": "100.00"}])
        rev = GLBus.reverse(ws, entry.id, date=TODAY)
        entry.refresh_from_db()
        assert entry.status == JournalEntry.REVERSED
        assert rev.status == JournalEntry.POSTED and rev.reverses_id == entry.id
        # net effect on cash is now zero
        assert GLBus.account_balance(ws, a["cash"].id) == Decimal("0.00")

    def test_only_posted_can_be_reversed(self):
        ws = uuid.uuid4()
        _coa(ws)
        draft = GLBus.create_draft(ws, date=TODAY, lines=[
            {"account_code": "1000", "debit": "1.00"}, {"account_code": "4000", "credit": "1.00"}])
        with pytest.raises(LedgerError, match="posted"):
            GLBus.reverse(ws, draft.id)

    def test_draft_can_be_posted(self):
        ws = uuid.uuid4()
        _coa(ws)
        draft = GLBus.create_draft(ws, date=TODAY, lines=[
            {"account_code": "1000", "debit": "7.00"}, {"account_code": "4000", "credit": "7.00"}])
        assert draft.status == JournalEntry.DRAFT and draft.entry_number == ""
        posted = GLBus.post_draft(ws, draft.id)
        assert posted.status == JournalEntry.POSTED and posted.entry_number == "JE-000001"


# ── event-driven posting (rules) ──────────────────────────────────────────────────
@pytest.mark.django_db
class TestEventBus:
    def test_post_event_uses_rule_template(self):
        ws = uuid.uuid4()
        _coa(ws)
        PostingRule.objects.create(
            workspace_id=ws, event_type="sale.invoiced", name="Customer invoice",
            template=[
                {"account_code": "1100", "side": "debit", "amount_field": "total"},
                {"account_code": "4000", "side": "credit", "amount_field": "total"},
            ])
        entry = GLBus.post_event(ws, "sale.invoiced", {"total": "250.00", "source_ref": "SO-1"})
        assert entry is not None and entry.status == JournalEntry.POSTED
        assert entry.source_ref == "SO-1" and entry.posting_rule_key == "sale.invoiced"
        assert entry.lines.get(account__code="1100").debit == Decimal("250.00")

    def test_post_event_without_rule_returns_none(self):
        ws = uuid.uuid4()
        _coa(ws)
        assert GLBus.post_event(ws, "nothing.configured", {"amount": "10.00"}) is None


# ── API ────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestLedgerAPI:
    def test_account_crud_admin_only(self, workspace):
        admin, _ = _client(workspace, "admin")
        cr = admin.post(f"{BASE}/accounts/", {"code": "1000", "name": "Cash", "account_type": "asset"}, format="json")
        assert cr.status_code == 201 and cr.data["normal_balance"] == "debit"
        member, _ = _client(workspace, "member")
        assert member.post(f"{BASE}/accounts/", {"code": "2000", "name": "AP", "account_type": "liability"},
                           format="json").status_code == 403
        assert member.get(f"{BASE}/accounts/").status_code == 200

    def test_create_and_post_entry_via_api(self, workspace):
        admin, _ = _client(workspace, "admin")
        for code, typ in [("1000", "asset"), ("4000", "revenue")]:
            admin.post(f"{BASE}/accounts/", {"code": code, "name": code, "account_type": typ}, format="json")
        r = admin.post(f"{BASE}/entries/", {
            "date": "2026-06-15", "post": True,
            "lines": [{"account_code": "1000", "debit": "100.00"},
                      {"account_code": "4000", "credit": "100.00"}],
        }, format="json")
        assert r.status_code == 201 and r.data["status"] == "posted"
        assert r.data["entry_number"] == "JE-000001"

    def test_posted_entry_cannot_be_edited_or_deleted(self, workspace):
        admin, _ = _client(workspace, "admin")
        for code, typ in [("1000", "asset"), ("4000", "revenue")]:
            admin.post(f"{BASE}/accounts/", {"code": code, "name": code, "account_type": typ}, format="json")
        eid = admin.post(f"{BASE}/entries/", {
            "date": "2026-06-15", "post": True,
            "lines": [{"account_code": "1000", "debit": "5.00"}, {"account_code": "4000", "credit": "5.00"}],
        }, format="json").data["id"]
        assert admin.patch(f"{BASE}/entries/{eid}/", {"memo": "x"}, format="json").status_code == 400
        assert admin.delete(f"{BASE}/entries/{eid}/").status_code == 400
        # but it can be reversed
        assert admin.post(f"{BASE}/entries/{eid}/reverse/", {}, format="json").status_code == 201

    def test_unbalanced_via_api_returns_400(self, workspace):
        admin, _ = _client(workspace, "admin")
        for code, typ in [("1000", "asset"), ("4000", "revenue")]:
            admin.post(f"{BASE}/accounts/", {"code": code, "name": code, "account_type": typ}, format="json")
        r = admin.post(f"{BASE}/entries/", {
            "date": "2026-06-15", "post": True,
            "lines": [{"account_code": "1000", "debit": "100.00"}, {"account_code": "4000", "credit": "1.00"}],
        }, format="json")
        assert r.status_code == 400

    def test_period_close_blocks_posting(self, workspace):
        admin, _ = _client(workspace, "admin")
        for code, typ in [("1000", "asset"), ("4000", "revenue")]:
            admin.post(f"{BASE}/accounts/", {"code": code, "name": code, "account_type": typ}, format="json")
        pid = admin.post(f"{BASE}/periods/", {
            "code": "2026-06", "start_date": "2026-06-01", "end_date": "2026-06-30"}, format="json").data["id"]
        assert admin.post(f"{BASE}/periods/{pid}/close/", {}, format="json").data["status"] == "closed"
        r = admin.post(f"{BASE}/entries/", {
            "date": "2026-06-15", "post": True,
            "lines": [{"account_code": "1000", "debit": "5.00"}, {"account_code": "4000", "credit": "5.00"}],
        }, format="json")
        assert r.status_code == 400

    def test_workspace_isolation(self, workspace):
        admin, _ = _client(workspace, "admin")
        aid = admin.post(f"{BASE}/accounts/", {"code": "1000", "name": "Cash", "account_type": "asset"},
                         format="json").data["id"]
        other = Workspace.objects.create(name="Other", slug="other", is_active=True)
        other_admin, _ = _client(other, "admin", email="other@example.com")
        assert other_admin.get(f"{BASE}/accounts/{aid}/").status_code == 404
        assert other_admin.get(f"{BASE}/accounts/").data == []
