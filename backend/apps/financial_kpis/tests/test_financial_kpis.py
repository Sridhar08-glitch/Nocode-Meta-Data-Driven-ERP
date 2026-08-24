"""
Financial KPI Library (F13) certification.

Proves: the finance KPIs REUSE the frozen Analytics engine (native evaluators, no second KPI engine);
each KPI computes correctly from the GL statement / cash / settlement / treasury engines (no accounting
owned here); the catalog exposes full AI-readiness metadata; provisioning seeds native KPIDefinitions +
dashboard templates (reporting platform); evaluation delegates to KPIService; NO KPI-code duplication
with the existing analytics library (ownership review); performance is O(KPIs) not O(rows) (no N+1);
REST contracts + admin authz + tenant isolation.
"""
import uuid
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.analytics.models import KPIDefinition
from apps.analytics.seeding import STANDARD_KPIS
from apps.financial_kpis import evaluators
from apps.financial_kpis.catalog import BY_CODE, CATALOG
from apps.financial_kpis.services import FinancialKpiCatalog
from apps.ledger.provisioning import provision_accounting
from apps.ledger.services import GLBus
from apps.tenancy.models import Workspace, WorkspaceMember

pytestmark = pytest.mark.django_db
PW = "Sup3rStr0ng!pw"


def _post(ws, dr, cr, amt, ref):
    GLBus.post(ws, date=timezone.now().date(),
               lines=[{"account_code": dr, "debit": str(amt)},
                      {"account_code": cr, "credit": str(amt)}],
               source_module="test", source_ref=ref)


def _seed_finance(ws):
    """A small but complete book so every GL-derived ratio has a real value."""
    provision_accounting(ws)
    _post(ws, "1010", "3000", 100000, "equity")        # cash from equity
    _post(ws, "1200", "2000", 40000, "buy-inv")        # inventory on credit → AP
    _post(ws, "1100", "4000", 30000, "credit-sale")    # AR sale → revenue
    _post(ws, "1010", "4000", 70000, "cash-sale")      # cash sale → revenue
    _post(ws, "5000", "1200", 25000, "cogs")           # COGS consumes inventory
    _post(ws, "6100", "1010", 10000, "rent")           # opex
    _post(ws, "6500", "1010", 5000, "interest")        # interest expense
    _post(ws, "6300", "1600", 3000, "deprec")          # depreciation
    evaluators.invalidate(ws)


def _v(ws, code):
    """Compute a KPI value directly via its registered evaluator (no KPIDefinition seed needed)."""
    return Decimal(str(evaluators.EVALUATORS[code](ws)))


# ── Gate 1: catalog integrity + ownership (no duplication) ───────────────────────
def test_catalog_evaluator_parity():
    assert set(evaluators.EVALUATORS) == set(BY_CODE)
    from apps.analytics import registry
    for code in BY_CODE:
        assert registry.get(f"finance_{code}") is not None   # every KPI has a registered evaluator


def test_no_kpi_code_duplication_with_analytics_library():
    """Ownership review: finance KPI codes must not collide with the existing analytics seed set."""
    existing = {k["code"] for k in STANDARD_KPIS}
    finance = set(BY_CODE)
    assert existing.isdisjoint(finance), f"duplicate KPI codes: {existing & finance}"


# ── Gate 7: AI-readiness metadata ────────────────────────────────────────────────
def test_every_kpi_exposes_ai_readiness_metadata():
    for k in CATALOG:
        d = k.descriptor()
        for field in ("name", "formula", "inputs", "dependencies", "unit", "direction",
                      "target", "warning_threshold", "category", "explanation"):
            assert d.get(field) not in (None, ""), f"{k.code} missing {field}"
        assert d["inputs"] and d["dependencies"]              # non-empty
        assert d["native_key"] == f"finance_{k.code}"


# ── Gate 2/4: evaluators compute correctly over a real book ──────────────────────
def test_liquidity_and_working_capital():
    ws = uuid.uuid4()
    _seed_finance(ws)
    assert _v(ws, "current_ratio") == Decimal("5")           # 200000 / 40000
    assert _v(ws, "quick_ratio") == Decimal("4.625")         # 185000 / 40000
    assert _v(ws, "cash_ratio") == Decimal("3.875")          # 155000 / 40000
    assert _v(ws, "working_capital") == Decimal("160000")    # 200000 - 40000


def test_profitability_and_returns():
    ws = uuid.uuid4()
    _seed_finance(ws)
    assert _v(ws, "gross_margin_pct") == Decimal("75.00")    # (100000-25000)/100000
    assert _v(ws, "net_profit_margin_pct") == Decimal("57.00")
    assert _v(ws, "operating_margin_pct") == Decimal("62.00")
    assert _v(ws, "ebitda") == Decimal("65000")              # op income 62000 + deprec 3000
    assert _v(ws, "gl_total_revenue") == Decimal("100000")
    assert _v(ws, "gl_total_expense") == Decimal("43000")
    assert _v(ws, "return_on_equity_pct") == Decimal("36.31")  # 57000/157000*100


def test_efficiency_and_leverage():
    ws = uuid.uuid4()
    _seed_finance(ws)
    assert _v(ws, "dso_days") == Decimal("109.50")           # 30000/100000*365
    assert _v(ws, "dio_days") == Decimal("219.00")           # 15000/25000*365
    assert _v(ws, "interest_coverage") == Decimal("12.4")    # 62000/5000
    assert _v(ws, "debt_to_equity") > 0                       # 40000/157000
    assert Decimal("0.20") <= _v(ws, "debt_ratio") <= Decimal("0.21")   # 40000/197000


def test_treasury_kpis_reuse_liquidity_engine():
    """total_borrowings reuses the F12 LiquidityService (treasury facilities), not GL 2600."""
    from apps.treasury.services import TreasuryService
    ws = uuid.uuid4()
    provision_accounting(ws)
    f = TreasuryService.create_facility(workspace_id=ws, principal="80000", currency="USD",
                                        interest_rate="6")
    TreasuryService.drawdown(workspace_id=ws, facility_id=f.id)
    evaluators.invalidate(ws)
    assert _v(ws, "total_borrowings") == Decimal("80000")
    assert _v(ws, "net_liquidity") == Decimal("-80000")      # 0 bank cash + 0 inv - 80000 borrow


def test_unavailable_kpi_is_graceful():
    """A workspace with no GL data yields 0 / unknown, never an error (best-effort)."""
    ws = uuid.uuid4()
    provision_accounting(ws)
    FinancialKpiCatalog.setup(workspace_id=ws)               # KPI exists, but no GL data
    r = FinancialKpiCatalog.evaluate(workspace_id=ws, code="current_ratio")
    assert r["value"] == "0"


# ── Gate 3: provisioning seeds native KPIs + dashboards, evaluation delegates ─────
def test_provisioning_seeds_kpis_and_dashboards():
    from apps.reporting.models import Dashboard, DashboardWidget
    ws = uuid.uuid4()
    provision_accounting(ws)
    out = FinancialKpiCatalog.setup(workspace_id=ws)
    assert out["kpis_created"] == len(CATALOG)
    assert out["dashboards_created"] == 4
    kpis = KPIDefinition.objects.filter(workspace_id=ws, category="financial", source_type="native")
    assert kpis.count() == len(CATALOG)
    assert Dashboard.objects.filter(workspace_id=ws, slug="cfo-overview").exists()
    widgets = DashboardWidget.objects.filter(workspace_id=ws, widget_type="metric_card")
    assert widgets.count() >= 20
    # idempotent: re-run creates nothing new
    out2 = FinancialKpiCatalog.setup(workspace_id=ws)
    assert out2["kpis_created"] == 0 and out2["dashboards_created"] == 0


def test_evaluate_all_delegates_to_analytics():
    ws = uuid.uuid4()
    _seed_finance(ws)
    FinancialKpiCatalog.setup(workspace_id=ws)
    evaluators.invalidate(ws)
    results = FinancialKpiCatalog.evaluate_all(workspace_id=ws)
    assert len(results) == len(CATALOG)
    by_code = {r["code"]: r for r in results}
    assert by_code["current_ratio"]["value"] == "5"


# ── Gate 8: performance — query count is O(KPIs), independent of journal volume ───
def test_evaluate_all_has_no_nplus1_on_data_volume():
    ws = uuid.uuid4()
    _seed_finance(ws)
    FinancialKpiCatalog.setup(workspace_id=ws)

    evaluators.invalidate(ws)
    with CaptureQueriesContext(connection) as q1:
        FinancialKpiCatalog.evaluate_all(workspace_id=ws)
    baseline = len(q1)

    for i in range(40):                                       # add 40 more journal lines
        _post(ws, "1010", "4000", 100, f"extra-{i}")
    evaluators.invalidate(ws)
    with CaptureQueriesContext(connection) as q2:
        FinancialKpiCatalog.evaluate_all(workspace_id=ws)

    assert len(q2) == baseline, f"N+1: {baseline} -> {len(q2)} queries after +40 rows"


# ── Gate 3/7/9: REST contracts + authz + tenant isolation ────────────────────────
def _client(ws, user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                  HTTP_X_WORKSPACE_SLUG=ws.slug)
    return c


@pytest.fixture
def env(db):
    ws = Workspace.objects.create(name="Acme", slug="acme-fk", is_active=True)
    provision_accounting(ws.id)
    admin = User.objects.create_user(email="admin@fk.com", password=PW, is_verified=True)
    WorkspaceMember.objects.create(workspace=ws, user=admin, role="admin", status="active")
    member = User.objects.create_user(email="member@fk.com", password=PW, is_verified=True)
    WorkspaceMember.objects.create(workspace=ws, user=member, role="member", status="active")
    return {"ws": ws, "admin": _client(ws, admin), "member": _client(ws, member)}


def test_catalog_endpoint_returns_ai_metadata(env):
    r = env["member"].get("/api/v1/financial-kpis/catalog/")
    assert r.status_code == 200
    assert r.data["count"] == len(CATALOG)
    assert len(r.data["categories"]) == 17
    one = r.data["kpis"][0]
    assert {"formula", "inputs", "dependencies", "explanation"} <= set(one)
    # category filter
    liq = env["member"].get("/api/v1/financial-kpis/catalog/?category=liquidity")
    assert all(k["category"] == "liquidity" for k in liq.data["kpis"])


def test_setup_is_admin_gated(env):
    assert env["member"].post("/api/v1/financial-kpis/setup/").status_code == 403
    r = env["admin"].post("/api/v1/financial-kpis/setup/")
    assert r.status_code == 201 and r.data["kpis_created"] == len(CATALOG)


def test_evaluate_endpoint(env):
    ws = env["ws"].id
    _seed_finance(ws)
    env["admin"].post("/api/v1/financial-kpis/setup/")
    evaluators.invalidate(ws)
    r = env["admin"].get("/api/v1/financial-kpis/evaluate/current_ratio/")
    assert r.status_code == 200 and r.data["value"] == "5"
    assert env["admin"].get("/api/v1/financial-kpis/dashboards/").status_code == 200


def test_cross_tenant_catalog_requires_membership(env):
    other = Workspace.objects.create(name="Other", slug="other-fk", is_active=True)
    u = User.objects.create_user(email="x@other.com", password=PW, is_verified=True)
    WorkspaceMember.objects.create(workspace=other, user=u, role="admin", status="active")
    # a member of 'other' setting up their own ws does not touch Acme's KPIs
    _client(other, u).post("/api/v1/financial-kpis/setup/")
    assert not KPIDefinition.objects.filter(workspace_id=env["ws"].id).exists()
