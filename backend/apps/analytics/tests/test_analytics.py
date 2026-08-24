"""
Analytics / KPI Registry (Phase P2.13) — KPI evaluation (NQL aggregate + native cross-module),
thresholds → status, role scorecards, snapshots, threshold alerts, audit, and framework install.
Reuses the NQL + reporting engines (no second reporting system). Covers spec Modules 1/11/14/29/33.
"""
import uuid
from decimal import Decimal

import pytest

from apps.analytics import services
from apps.analytics.blueprint import build_analytics_manifest, seed_analytics_template
from apps.analytics.models import KPIDefinition, KPISnapshot
from apps.analytics.seeding import seed_standard_kpis
from apps.analytics.services import KPIService
from apps.eventstore.models import DomainEvent
from apps.permissions.models import Role
from apps.records.services import RecordService, resolve_entity
from apps.schema_registry.services import SchemaRegistryService
from apps.solution_templates import services as st
from apps.solution_templates.documents import system_member
from apps.solution_templates.validators import validate_solution_manifest
from apps.studio.models import Application

A = str(uuid.uuid4())


# ── pure aggregation + status ─────────────────────────────────────────────────
def test_aggregate():
    rows = [{"v": "10"}, {"v": "20"}, {"v": None}]
    assert services._aggregate(rows, "v", "sum") == Decimal("30")
    assert services._aggregate(rows, "v", "avg") == Decimal("15")
    assert services._aggregate(rows, "v", "count") == Decimal("3")
    assert services._aggregate(rows, "v", "max") == Decimal("20")


def test_status_thresholds():
    hb = KPIDefinition(target=100, warning_threshold=80, direction="higher_better")
    assert services._status(Decimal("120"), hb) == "good"
    assert services._status(Decimal("90"), hb) == "warning"
    assert services._status(Decimal("50"), hb) == "critical"
    lb = KPIDefinition(target=100, warning_threshold=120, direction="lower_better")
    assert services._status(Decimal("90"), lb) == "good"
    assert services._status(Decimal("110"), lb) == "warning"
    assert services._status(Decimal("200"), lb) == "critical"


# ── KPI registry ──────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_seed_standard_kpis_idempotent():
    ws = uuid.uuid4()
    assert seed_standard_kpis(ws) == len(__import__(
        "apps.analytics.seeding", fromlist=["STANDARD_KPIS"]).STANDARD_KPIS)
    assert seed_standard_kpis(ws) == 0  # already present
    assert KPIDefinition.objects.filter(workspace_id=ws, code="revenue").exists()


# ── NQL KPI evaluation (reuses execute_nql) ──────────────────────────────────
@pytest.mark.django_db
def test_nql_kpi_aggregates_entity():
    ws = uuid.uuid4()
    SchemaRegistryService.create_entity(
        workspace_id=ws, slug="widget", name="Widget", plural_name="Widgets",
        fields=[{"slug": "price", "name": "Price", "field_type": "decimal", "is_promoted": True}])
    ent = resolve_entity(ws, "widget")
    for p in ("10", "20", "30"):
        RecordService.create_record(workspace_id=ws, member=system_member(None), entity=ent,
                                    data={"price": p})
    kpi = KPIDefinition.objects.create(
        workspace_id=ws, code="widget_value", name="Widget Value", source_type="nql",
        nql_source="FROM widget", value_field="price", aggregate="sum", target=100)
    r = KPIService.evaluate(workspace_id=ws, kpi=kpi)
    assert Decimal(r["value"]) == Decimal("60") and r["available"] is True
    assert r["status"] == "critical"   # 60 < target 100


@pytest.mark.django_db
def test_nql_kpi_missing_entity_is_unknown():
    ws = uuid.uuid4()
    kpi = KPIDefinition.objects.create(
        workspace_id=ws, code="revenue", name="Revenue", source_type="nql",
        nql_source="FROM sales_order", value_field="amount", aggregate="sum")
    r = KPIService.evaluate(workspace_id=ws, kpi=kpi)
    assert r["available"] is False and r["status"] == "unknown" and r["value"] == "0"


# ── native cross-module KPI ───────────────────────────────────────────────────
@pytest.mark.django_db
def test_native_inventory_value_kpi():
    from apps.inventory.models import Item, Warehouse
    from apps.inventory.services import InventoryService
    ws = uuid.uuid4()
    item = Item.objects.create(workspace_id=ws, sku="X", name="X", valuation_method="average")
    wh = Warehouse.objects.create(workspace_id=ws, code="M", name="M")
    InventoryService.receive(ws, item.id, wh.id, 10, "5")   # value = 50
    kpi = KPIDefinition.objects.create(
        workspace_id=ws, code="inventory_value", name="Inventory Value", source_type="native",
        native_key="inventory_value", target=1000000, direction="higher_better")
    r = KPIService.evaluate(workspace_id=ws, kpi=kpi)
    assert Decimal(r["value"]) == Decimal("50") and r["available"] is True
    assert r["status"] == "critical"  # far below target → alert candidate


# ── scorecard + snapshot + alerts + audit ────────────────────────────────────
@pytest.mark.django_db
def test_scorecard_and_snapshot_and_alerts():
    ws = uuid.uuid4()
    seed_standard_kpis(ws)
    sc = KPIService.scorecard(workspace_id=ws, role="cfo")
    assert sc["role"] == "cfo" and "kpis" in sc and "summary" in sc
    # CFO scorecard only includes its categories (financial/accounting/payroll/inventory/assets).
    assert all(k["category"] in ["financial", "accounting", "payroll", "inventory", "assets"]
               for k in sc["kpis"])

    n = KPIService.snapshot(workspace_id=ws, period="2026-06")
    assert n == KPISnapshot.objects.filter(workspace_id=ws).count() > 0
    assert DomainEvent.objects.filter(event_type="analytics.snapshot.created").exists()

    KPIService.check_alerts(workspace_id=ws)
    # The seeded KPIs over absent modules are "unknown" (no alert); none should raise here.
    # Add a guaranteed-breach native KPI:
    KPIDefinition.objects.create(
        workspace_id=ws, code="zero_kpi", name="Zero", source_type="native",
        native_key="manufacturing_output", target=999, direction="higher_better")
    alerts = KPIService.check_alerts(workspace_id=ws)
    assert any(a["code"] == "zero_kpi" for a in alerts)
    assert DomainEvent.objects.filter(event_type="analytics.alert.triggered").exists()


@pytest.mark.django_db
def test_evaluate_code_emits_executed_event():
    ws = uuid.uuid4()
    seed_standard_kpis(ws)
    KPIService.evaluate_code(workspace_id=ws, code="headcount")
    assert DomainEvent.objects.filter(event_type="analytics.report.executed").exists()


# ── framework install ─────────────────────────────────────────────────────────
def test_manifest_validates_clean():
    assert validate_solution_manifest(build_analytics_manifest()) == []


@pytest.mark.django_db
def test_install_provisions_analytics_roles_and_app():
    ws = uuid.uuid4()
    st.install(template_id=seed_analytics_template().id, workspace_id=ws, installed_by=None)
    assert Role.objects.filter(workspace_id=ws, slug="analytics_administrator").exists()
    assert Role.objects.filter(workspace_id=ws, slug="executive_cfo").exists()
    assert Application.objects.filter(workspace_id=ws, slug="analytics").exists()
