"""
Treasury Platform (F12) — REST integration, API-contract & authorization certification
(Certification Gates 3 / 7 / 9). Exercises the REAL request stack (JWT auth + TenantMiddleware
workspace resolution + RLS GUC + RBAC role gate), not the service layer directly: every treasury
endpoint through an authenticated ``APIClient``, request/response contracts, status codes, admin-vs-member
authorization, cross-tenant isolation, and error responses.
"""
import datetime as dt
import uuid

import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.ledger.provisioning import provision_accounting
from apps.tenancy.models import Workspace, WorkspaceMember

pytestmark = pytest.mark.django_db

PW = "Sup3rStr0ng!pw"
TODAY = "2026-01-01"
MAT = "2026-12-31"


def _client(ws, user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                  HTTP_X_WORKSPACE_SLUG=ws.slug)
    return c


@pytest.fixture
def env(db):
    ws = Workspace.objects.create(name="Acme", slug="acme", is_active=True)
    provision_accounting(ws.id)
    admin = User.objects.create_user(email="admin@acme.com", password=PW, is_verified=True)
    WorkspaceMember.objects.create(workspace=ws, user=admin, role="admin", status="active")
    member = User.objects.create_user(email="member@acme.com", password=PW, is_verified=True)
    WorkspaceMember.objects.create(workspace=ws, user=member, role="member", status="active")
    return {"ws": ws, "admin": admin, "member": member,
            "admin_client": _client(ws, admin), "member_client": _client(ws, member)}


def _facility(client, **over):
    body = {"principal": "100000", "currency": "USD", "interest_rate": "6",
            "payment_frequency": "quarterly", "start_date": TODAY, "maturity_date": MAT}
    body.update(over)
    return client.post("/api/v1/treasury/facilities/", body, format="json")


# ── Gate 3/7: full REST lifecycle + contracts ────────────────────────────────────
def test_counterparty_crud_contract(env):
    c = env["admin_client"]
    r = c.post("/api/v1/treasury/counterparties/",
               {"code": "BANK1", "name": "Test Bank", "exposure_limit": "1000000"}, format="json")
    assert r.status_code == 201 and r.data["code"] == "BANK1"
    lst = c.get("/api/v1/treasury/counterparties/")
    assert lst.status_code == 200 and len(lst.data) == 1
    assert lst.data[0]["exposure_limit"] == "1000000.00"


def test_facility_lifecycle_via_api(env):
    c = env["admin_client"]
    r = _facility(c)
    assert r.status_code == 201
    fid = r.data["id"]
    # drawdown action posts a GL entry and returns the transaction
    dd = c.post(f"/api/v1/treasury/facilities/{fid}/drawdown/", {}, format="json")
    assert dd.status_code == 201
    assert dd.data["transaction_type"] == "drawdown"
    assert dd.data["journal_entry_id"] is not None
    # facility list reflects outstanding
    lst = c.get("/api/v1/treasury/facilities/")
    assert lst.data[0]["outstanding"] == "100000.00"
    # repay
    rp = c.post(f"/api/v1/treasury/facilities/{fid}/repay/", {"date": MAT}, format="json")
    assert rp.status_code == 201 and rp.data["transaction_type"] == "principal_repayment"


def test_investment_lifecycle_via_api(env):
    c = env["admin_client"]
    r = c.post("/api/v1/treasury/investments/",
               {"principal": "60000", "investment_type": "bond", "currency": "USD",
                "interest_rate": "4", "start_date": TODAY, "maturity_date": MAT}, format="json")
    assert r.status_code == 201
    iid = r.data["id"]
    assert c.post(f"/api/v1/treasury/investments/{iid}/place/", {}, format="json").status_code == 201
    mat = c.post(f"/api/v1/treasury/investments/{iid}/mature/", {"date": MAT}, format="json")
    assert mat.status_code == 201 and mat.data["transaction_type"] == "maturity"


def test_transactions_and_interest_run_endpoints(env):
    c = env["admin_client"]
    fid = _facility(c).data["id"]
    c.post(f"/api/v1/treasury/facilities/{fid}/drawdown/", {}, format="json")
    run = c.post("/api/v1/treasury/pay-interest-due/", {"as_of": "2027-01-31"}, format="json")
    assert run.status_code == 201 and run.data["posted"] >= 1
    txns = c.get("/api/v1/treasury/transactions/")
    assert txns.status_code == 200
    types = {t["transaction_type"] for t in txns.data}
    assert "drawdown" in types and "interest_payment" in types
    # filter contract
    filt = c.get("/api/v1/treasury/transactions/?transaction_type=drawdown")
    assert all(t["transaction_type"] == "drawdown" for t in filt.data)


def test_computed_report_endpoints(env):
    c = env["admin_client"]
    fid = _facility(c).data["id"]
    c.post(f"/api/v1/treasury/facilities/{fid}/drawdown/", {}, format="json")
    sched = c.get(f"/api/v1/treasury/schedules/interest/facility/{fid}/")
    assert sched.status_code == 200 and len(sched.data) == 4
    assert c.get("/api/v1/treasury/schedules/debt/").status_code == 200
    assert c.get("/api/v1/treasury/schedules/maturity/").status_code == 200
    liq = c.get("/api/v1/treasury/liquidity/")
    assert liq.status_code == 200 and liq.data["borrowings"] == "100000.00"
    assert c.get("/api/v1/treasury/exposure/").status_code == 200
    fc = c.get("/api/v1/treasury/forecast/?from=2026-01-01&to=2027-12-31")
    assert fc.status_code == 200 and "net_projected" in fc.data


# ── Gate 7: error responses ───────────────────────────────────────────────────────
def test_bad_input_returns_400(env):
    c = env["admin_client"]
    assert c.post("/api/v1/treasury/counterparties/", {"name": "x"}, format="json").status_code == 400
    assert _facility(c, principal="-5").status_code == 400
    fid = _facility(c).data["id"]
    assert c.post(f"/api/v1/treasury/facilities/{fid}/frobnicate/", {},
                  format="json").status_code == 400


# ── Gate 9: authorization (RBAC role gate) ───────────────────────────────────────
def test_member_cannot_write_but_can_read(env):
    m = env["member_client"]
    assert _facility(m).status_code == 403                    # member write denied
    # admin creates, member can read
    env["admin_client"].post("/api/v1/treasury/counterparties/",
                             {"code": "B", "name": "B", "exposure_limit": "1"}, format="json")
    assert m.get("/api/v1/treasury/counterparties/").status_code == 200


def test_unauthenticated_denied(env):
    anon = APIClient()
    assert anon.get("/api/v1/treasury/facilities/").status_code in (401, 403)


def test_missing_workspace_header_denied(env):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(env['admin'])}")
    assert c.get("/api/v1/treasury/facilities/").status_code in (401, 403)


# ── Gate 9: cross-tenant isolation (ORM + RLS via the real stack) ─────────────────
def test_cross_tenant_isolation(env, db):
    _facility(env["admin_client"])                            # a facility in Acme
    other = Workspace.objects.create(name="Other", slug="other", is_active=True)
    provision_accounting(other.id)
    u2 = User.objects.create_user(email="x@other.com", password=PW, is_verified=True)
    WorkspaceMember.objects.create(workspace=other, user=u2, role="admin", status="active")
    c2 = _client(other, u2)
    assert c2.get("/api/v1/treasury/facilities/").data == []   # cannot see Acme's facility
    # and a bogus id from another tenant is not actionable
    bogus = str(uuid.uuid4())
    assert c2.post(f"/api/v1/treasury/facilities/{bogus}/drawdown/", {},
                   format="json").status_code == 400


# ── Gate 4 (behavior) + Gate 3 (statement integration): loan lifecycle → statements ─
def test_loan_lifecycle_flows_into_financial_statements(env):
    from apps.financial_reports.services import StatementService
    c = env["admin_client"]
    ws = env["ws"].id
    fid = _facility(c, principal="120000", interest_rate="10",
                    payment_frequency="annual").data["id"]
    c.post(f"/api/v1/treasury/facilities/{fid}/drawdown/", {}, format="json")
    c.post("/api/v1/treasury/pay-interest-due/", {"as_of": "2027-01-31"}, format="json")

    tb = StatementService.trial_balance(ws, as_of=dt.date(2027, 1, 31))
    assert tb["balanced"] is True                             # treasury postings keep the TB balanced
    codes = {r["code"] for r in tb["rows"]}
    assert {"1010", "2600", "6500"} <= codes                 # cash, borrowings, interest expense present
    pnl = StatementService.profit_and_loss(ws, from_date=dt.date(2026, 1, 1),
                                           to_date=dt.date(2027, 1, 31))
    assert any(e["code"] == "6500" for e in pnl["expenses"])  # interest expense on the P&L
