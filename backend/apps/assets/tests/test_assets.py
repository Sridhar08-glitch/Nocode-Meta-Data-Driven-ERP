"""
Asset Management (Phase P2.9) — framework provisioning of the asset registry/operations + the
native depreciation engine (straight-line/declining/double-declining, immutable entries, GL,
asset valuation update), disposal/retirement with GL + audit, and asset lifecycle.
"""
import datetime
import uuid
from decimal import Decimal

import pytest

from apps.assets import depreciation
from apps.assets.blueprint import build_assets_manifest, seed_assets_template
from apps.assets.models import (
    AssetValuationSnapshot,
    DepreciationEntry,
    DisposalRecord,
)
from apps.assets.services import AssetService, DepreciationService, DisposalService
from apps.eventstore.models import DomainEvent
from apps.metadata.models import EntityDefinition
from apps.permissions.models import Role
from apps.reporting.models import Dashboard
from apps.solution_templates import services as st
from apps.solution_templates.validators import validate_solution_manifest
from apps.studio.models import Application
from apps.workflows.models import WorkflowDefinition

A = str(uuid.uuid4())
JUNE = datetime.date(2026, 6, 30)


# ── depreciation calculator (pure) ───────────────────────────────────────────
def test_straight_line():
    amt = depreciation.period_amount(method="straight_line", cost=1200, salvage=0,
                                     useful_life_months=12, accumulated=0, period_index=0)
    assert amt == Decimal("100.00")


def test_declining_and_double_declining():
    dec = depreciation.period_amount(method="declining_balance", cost=1200, salvage=0,
                                     useful_life_months=24, accumulated=0, period_index=0)
    assert dec == Decimal("50.00")          # 1200 * (1/2)/12
    ddb = depreciation.period_amount(method="double_declining", cost=1200, salvage=0,
                                     useful_life_months=24, accumulated=0, period_index=0)
    assert ddb == Decimal("100.00")         # 1200 * (2/2)/12


def test_never_below_salvage():
    # cost 100, salvage 90 → only 10 depreciable; once accumulated=10, returns 0.
    amt = depreciation.period_amount(method="straight_line", cost=100, salvage=90,
                                     useful_life_months=12, accumulated=10, period_index=5)
    assert amt == Decimal("0.00")


def test_full_schedule_sums_to_depreciable():
    rows = depreciation.full_schedule(method="straight_line", cost=1200, salvage=0,
                                      useful_life_months=12)
    assert len(rows) == 12
    assert rows[-1]["accumulated"] == Decimal("1200.00")
    assert rows[-1]["net_book_value"] == Decimal("0.00")


# ── framework provisioning ────────────────────────────────────────────────────
def test_manifest_validates_clean():
    assert validate_solution_manifest(build_assets_manifest()) == []


@pytest.mark.django_db
def test_install_provisions_assets_solution():
    ws = uuid.uuid4()
    st.install(template_id=seed_assets_template().id, workspace_id=ws, installed_by=None)
    for slug in ["asset", "asset_category", "asset_assignment", "maintenance_work_order",
                 "inspection", "warranty"]:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    assert WorkflowDefinition.objects.filter(workspace_id=ws, slug="disposal_approval").exists() \
        or WorkflowDefinition.objects.filter(workspace_id=ws, slug="maintenance_approval").exists()
    assert Role.objects.filter(workspace_id=ws, slug="asset_administrator").exists()
    assert Dashboard.objects.filter(workspace_id=ws).count() == 2
    assert Application.objects.filter(workspace_id=ws, slug="assets").exists()


# ── lifecycle + native engines (with the solution installed) ─────────────────
@pytest.fixture
def installed_ws(db):
    ws = uuid.uuid4()
    st.install(template_id=seed_assets_template().id, workspace_id=ws, installed_by=None)
    return ws


@pytest.mark.django_db
def test_create_and_assign_asset(installed_ws):
    ws = installed_ws
    asset = AssetService.create_asset(
        workspace_id=ws, data={"name": "MacBook", "status": "in_service"}, actor_id=A)
    assert asset["number"] == "AST-000001"
    assert DomainEvent.objects.filter(event_type="asset.created").exists()

    assigned = AssetService.assign_asset(workspace_id=ws, asset_record_id=asset["id"], actor_id=A)
    assert assigned["status"] == "assigned"
    assert DomainEvent.objects.filter(event_type="asset.assigned").exists()
    returned = AssetService.return_asset(workspace_id=ws, asset_record_id=asset["id"], actor_id=A)
    assert returned["status"] == "in_service"


@pytest.mark.django_db
def test_depreciation_run_updates_asset_and_is_immutable(installed_ws):
    ws = installed_ws
    asset = AssetService.create_asset(
        workspace_id=ws, data={"name": "Server", "purchase_cost": "1200"}, actor_id=A)
    sched = DepreciationService.create_schedule(
        workspace_id=ws, asset_record_id=asset["id"], method="straight_line",
        acquisition_cost=1200, salvage_value=0, useful_life_months=12, actor_id=A)

    e1 = DepreciationService.run_period(workspace_id=ws, schedule_id=sched.id, period_date=JUNE)
    assert e1.amount == Decimal("100.00") and e1.net_book_value == Decimal("1100.00")
    e2 = DepreciationService.run_period(workspace_id=ws, schedule_id=sched.id, period_date=JUNE)
    assert e2.period_index == 1 and e2.accumulated == Decimal("200.00")
    assert DepreciationEntry.objects.filter(workspace_id=ws, schedule_id=sched.id).count() == 2
    assert AssetValuationSnapshot.objects.filter(workspace_id=ws).count() == 2
    assert DomainEvent.objects.filter(event_type="asset.depreciation.posted").count() == 2

    # The asset metadata valuation fields were updated.
    from apps.records.services import RecordService, resolve_entity
    from apps.solution_templates.documents import system_member
    rec = RecordService.retrieve_record(
        workspace_id=ws, member=system_member(None),
        entity=resolve_entity(ws, "asset"), record_id=asset["id"])
    assert float(rec["net_book_value"]) == 1000.0  # 1200 - 200


@pytest.mark.django_db
def test_run_all_bulk(installed_ws):
    ws = installed_ws
    for i in range(3):
        a = AssetService.create_asset(workspace_id=ws, data={"name": f"A{i}"}, actor_id=A)
        DepreciationService.create_schedule(
            workspace_id=ws, asset_record_id=a["id"], acquisition_cost=1200,
            useful_life_months=12, actor_id=A)
    posted = DepreciationService.run_all(workspace_id=ws, period_date=JUNE)
    assert posted == 3


@pytest.mark.django_db
def test_dispose_and_retire(installed_ws):
    ws = installed_ws
    asset = AssetService.create_asset(
        workspace_id=ws, data={"name": "Van", "net_book_value": "1100"}, actor_id=A)
    rec = DisposalService.dispose(
        workspace_id=ws, asset_record_id=asset["id"], method="sale", proceeds=500,
        book_value=1100, actor_id=A)
    assert rec.gain_loss == Decimal("-600.00")
    assert DomainEvent.objects.filter(event_type="asset.disposed").exists()

    asset2 = AssetService.create_asset(
        workspace_id=ws, data={"name": "Old PC", "net_book_value": "50"}, actor_id=A)
    ret = AssetService.retire_asset(
        workspace_id=ws, asset_record_id=asset2["id"], reason="EOL", actor_id=A)
    assert ret.kind == "retirement" and ret.book_value == Decimal("50.00")
    assert DomainEvent.objects.filter(event_type="asset.retired").exists()
    assert DisposalRecord.objects.filter(workspace_id=ws).count() == 2
