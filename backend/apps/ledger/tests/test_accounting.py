"""
Accounting engine (Phase P2.3) — COA seeding, fiscal-year generation, and the four financial
reports (trial balance, general ledger, P&L, balance sheet) over posted journal lines.
"""
import datetime as dt
import uuid

import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.ledger import reports, seeding
from apps.ledger.models import AccountingPeriod, LedgerAccount
from apps.ledger.services import GLBus
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"
BASE = "/api/v1/ledger"
D = dt.date(2026, 6, 15)


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


def _seed_and_post(ws):
    seeding.seed_standard_chart(ws)
    # Cash sale: Dr Cash 300 / Cr Sales 300; then Dr Rent 100 / Cr Cash 100.
    GLBus.post(ws, date=D, lines=[{"account_code": "1000", "debit": "300.00"},
                                  {"account_code": "4000", "credit": "300.00"}])
    GLBus.post(ws, date=D, lines=[{"account_code": "6100", "debit": "100.00"},
                                  {"account_code": "1000", "credit": "100.00"}])


# ── seeding ───────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestSeeding:
    def test_seed_standard_chart_is_idempotent(self):
        ws = uuid.uuid4()
        first = seeding.seed_standard_chart(ws)
        assert first["created"] == len(seeding.STANDARD_CHART)
        assert LedgerAccount.objects.filter(workspace_id=ws).count() == len(seeding.STANDARD_CHART)
        second = seeding.seed_standard_chart(ws)
        assert second["created"] == 0 and second["skipped"] == len(seeding.STANDARD_CHART)

    def test_generate_fiscal_year_creates_12_periods(self):
        ws = uuid.uuid4()
        res = seeding.generate_fiscal_year(ws, year=2026)
        assert res["created"] == 12
        periods = AccountingPeriod.objects.filter(workspace_id=ws).order_by("start_date")
        assert periods.count() == 12
        assert periods.first().code == "2026-01"
        assert periods.last().code == "2026-12"
        # idempotent
        assert seeding.generate_fiscal_year(ws, year=2026)["created"] == 0

    def test_fiscal_year_with_start_month_wraps(self):
        ws = uuid.uuid4()
        seeding.generate_fiscal_year(ws, year=2026, start_month=4)
        codes = list(AccountingPeriod.objects.filter(workspace_id=ws)
                     .order_by("start_date").values_list("code", flat=True))
        assert codes[0] == "2026-04" and codes[-1] == "2027-03"


# ── reports ───────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestReports:
    def test_trial_balance_balances(self):
        ws = uuid.uuid4()
        _seed_and_post(ws)
        tb = reports.trial_balance(ws)
        assert tb["balanced"] is True
        assert tb["total_debit"] == tb["total_credit"]
        cash = next(r for r in tb["rows"] if r["code"] == "1000")
        assert cash["debit"] == "200.00"  # 300 in − 100 out

    def test_profit_and_loss(self):
        ws = uuid.uuid4()
        _seed_and_post(ws)
        pl = reports.profit_and_loss(ws, date_from=dt.date(2026, 6, 1), date_to=dt.date(2026, 6, 30))
        assert pl["total_revenue"] == "300.00"
        assert pl["total_expense"] == "100.00"
        assert pl["net_income"] == "200.00"

    def test_balance_sheet_equation_holds(self):
        ws = uuid.uuid4()
        _seed_and_post(ws)
        bs = reports.balance_sheet(ws)
        # assets (cash 200) == liabilities (0) + equity (0 + current earnings 200)
        assert bs["total_assets"] == "200.00"
        assert bs["balanced"] is True
        assert bs["total_liabilities_equity"] == "200.00"

    def test_general_ledger_running_balance(self):
        ws = uuid.uuid4()
        _seed_and_post(ws)
        cash = LedgerAccount.objects.get(workspace_id=ws, code="1000")
        gl = reports.general_ledger(ws, cash.id)
        assert gl["account"]["code"] == "1000"
        assert len(gl["lines"]) == 2
        assert gl["closing_balance"] == "200.00"  # 300 − 100

    def test_general_ledger_opening_balance_with_date_filter(self):
        ws = uuid.uuid4()
        seeding.seed_standard_chart(ws)
        GLBus.post(ws, date=dt.date(2026, 5, 1), lines=[
            {"account_code": "1000", "debit": "50.00"}, {"account_code": "4000", "credit": "50.00"}])
        GLBus.post(ws, date=dt.date(2026, 6, 1), lines=[
            {"account_code": "1000", "debit": "20.00"}, {"account_code": "4000", "credit": "20.00"}])
        cash = LedgerAccount.objects.get(workspace_id=ws, code="1000")
        gl = reports.general_ledger(ws, cash.id, date_from=dt.date(2026, 6, 1))
        assert gl["opening_balance"] == "50.00"   # the May posting
        assert len(gl["lines"]) == 1              # only June in range
        assert gl["closing_balance"] == "70.00"

    def test_reversed_entries_still_count_in_reports(self):
        ws = uuid.uuid4()
        seeding.seed_standard_chart(ws)
        e = GLBus.post(ws, date=D, lines=[{"account_code": "1000", "debit": "100.00"},
                                          {"account_code": "4000", "credit": "100.00"}])
        GLBus.reverse(ws, e.id, date=D)
        tb = reports.trial_balance(ws)
        # original + reversal net to zero → cash drops out of the trial balance
        assert all(r["code"] != "1000" for r in tb["rows"]) or \
            next(r["debit"] for r in tb["rows"] if r["code"] == "1000") == "0.00"
        assert tb["balanced"] is True


# ── API ────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestAccountingAPI:
    def test_seed_chart_endpoint(self, workspace):
        admin, _ = _client(workspace, "admin")
        r = admin.post(f"{BASE}/seed-chart/", {}, format="json")
        assert r.status_code == 201 and r.data["created"] == len(seeding.STANDARD_CHART)
        member, _ = _client(workspace, "member")
        assert member.post(f"{BASE}/seed-chart/", {}, format="json").status_code == 403

    def test_generate_fiscal_year_endpoint(self, workspace):
        admin, _ = _client(workspace, "admin")
        r = admin.post(f"{BASE}/fiscal-years/", {"year": 2026}, format="json")
        assert r.status_code == 201 and r.data["created"] == 12

    def test_reports_endpoints(self, workspace):
        admin, _ = _client(workspace, "admin")
        admin.post(f"{BASE}/seed-chart/", {}, format="json")
        admin.post(f"{BASE}/entries/", {
            "date": "2026-06-15", "post": True,
            "lines": [{"account_code": "1000", "debit": "300.00"},
                      {"account_code": "4000", "credit": "300.00"}]}, format="json")
        tb = admin.get(f"{BASE}/reports/trial-balance/")
        assert tb.status_code == 200 and tb.data["balanced"] is True
        pl = admin.get(f"{BASE}/reports/profit-loss/?date_from=2026-06-01&date_to=2026-06-30")
        assert pl.status_code == 200 and pl.data["total_revenue"] == "300.00"
        bs = admin.get(f"{BASE}/reports/balance-sheet/")
        assert bs.status_code == 200 and bs.data["balanced"] is True
        cash_id = next(a["id"] for a in admin.get(f"{BASE}/accounts/").data if a["code"] == "1000")
        gl = admin.get(f"{BASE}/reports/general-ledger/?account={cash_id}")
        assert gl.status_code == 200 and gl.data["closing_balance"] == "300.00"

    def test_general_ledger_requires_account(self, workspace):
        admin, _ = _client(workspace, "admin")
        assert admin.get(f"{BASE}/reports/general-ledger/").status_code == 400

    def test_member_can_read_reports(self, workspace):
        admin, _ = _client(workspace, "admin")
        admin.post(f"{BASE}/seed-chart/", {}, format="json")
        member, _ = _client(workspace, "member")
        assert member.get(f"{BASE}/reports/trial-balance/").status_code == 200
