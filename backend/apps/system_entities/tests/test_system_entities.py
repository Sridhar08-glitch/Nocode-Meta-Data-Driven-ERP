"""
System-Entity Adapter (B0) certification.

Proves the GENERIC platform capability: any registered native model is published as a metadata-shaped
descriptor and served through one generic list/detail/create REST surface — validated on ≥2 unrelated
engines (treasury + inventory). Covers reflection/typing, descriptor contract, list filter/sort/paginate,
retrieve, create-delegates-to-engine, read/write permission gates, tenant isolation, no-N+1, and the
REST contracts through the real request stack.
"""
import uuid

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.ledger.provisioning import provision_accounting
from apps.system_entities import registry
from apps.system_entities.services import SystemEntityError, SystemEntityService
from apps.tenancy.models import Workspace, WorkspaceMember
from apps.treasury.models import TreasuryFacility
from apps.treasury.services import TreasuryService

pytestmark = pytest.mark.django_db
PW = "Sup3rStr0ng!pw"


# ── Gate 1/2: registry + reflection ──────────────────────────────────────────────
def test_both_engines_registered_generically():
    slugs = set(registry.slugs())
    assert {"treasury_facility", "treasury_counterparty", "treasury_transaction"} <= slugs
    assert {"inventory_item", "inventory_warehouse", "inventory_movement"} <= slugs   # ≥2 engines


def test_reflection_maps_types_and_hides_plumbing():
    fac = registry.get("treasury_facility")
    types = {f.name: f.type for f in fac.fields}
    assert types["principal"] == "decimal"
    assert types["rate_type"] == "select"          # has choices
    assert types["counterparty_id"] == "reference"
    assert types["maturity_date"] == "date"
    names = set(types)
    assert not ({"workspace_id", "is_deleted", "deleted_at", "deleted_by"} & names)  # plumbing hidden
    assert types["id"] == "text" and next(f for f in fac.fields if f.name == "id").readonly


def test_descriptor_contract():
    d = registry.get("inventory_item").descriptor(can_write=True)
    assert d["kind"] == "system" and d["slug"] == "inventory_item"
    assert any(f["name"] == "sku" for f in d["fields"])
    assert d["capabilities"]["can_create"] is True
    fac = registry.get("treasury_facility").descriptor(can_write=True)
    assert {a["key"] for a in fac["actions"]} == {"drawdown", "repay"}
    assert fac["actions"][0]["path"].startswith("/api/v1/treasury/facilities/")


# ── Gate 2/4: generic data access ────────────────────────────────────────────────
def _seed_treasury(ws):
    provision_accounting(ws)
    for i in range(3):
        TreasuryService.create_facility(workspace_id=ws, principal=str(10000 * (i + 1)),
                                        currency="USD", interest_rate="6")


def test_list_records_reflects_native_rows():
    ws = uuid.uuid4()
    _seed_treasury(ws)
    out = SystemEntityService.list_records(slug="treasury_facility", workspace_id=ws, role="admin")
    assert out["count"] == 3
    assert out["results"][0]["principal"] in ("10000.00", "20000.00", "30000.00")
    assert "workspace_id" not in out["results"][0]           # plumbing not serialized


def test_list_filter_sort_paginate():
    ws = uuid.uuid4()
    _seed_treasury(ws)
    page = SystemEntityService.list_records(
        slug="treasury_facility", workspace_id=ws, role="admin",
        sort="principal", page=1, page_size=2)
    assert len(page["results"]) == 2 and page["count"] == 3
    assert page["results"][0]["principal"] == "10000.00"     # ascending sort
    filt = SystemEntityService.list_records(
        slug="treasury_facility", workspace_id=ws, role="admin", filters={"currency": "USD"})
    assert filt["count"] == 3


def test_retrieve_and_missing():
    ws = uuid.uuid4()
    _seed_treasury(ws)
    fac = TreasuryFacility.objects.filter(workspace_id=ws).first()
    row = SystemEntityService.retrieve(slug="treasury_facility", workspace_id=ws, role="admin",
                                       record_id=fac.id)
    assert row["number"] == fac.number
    with pytest.raises(SystemEntityError):
        SystemEntityService.retrieve(slug="treasury_facility", workspace_id=ws, role="admin",
                                     record_id=uuid.uuid4())


def test_create_delegates_to_engine():
    ws = uuid.uuid4()
    provision_accounting(ws)
    row = SystemEntityService.create(
        slug="treasury_facility", workspace_id=ws, role="admin",
        data={"principal": "50000", "currency": "USD", "interest_rate": "5",
              "facility_type": "overdraft"})
    assert row["principal"] == "50000.00" and row["facility_type"] == "overdraft"
    assert row["number"].startswith("BOR-")                  # went through TreasuryService (numbered)
    assert TreasuryFacility.objects.filter(workspace_id=ws).count() == 1


def test_inventory_engine_is_generic_too():
    ws = uuid.uuid4()
    row = SystemEntityService.create(
        slug="inventory_item", workspace_id=ws, role="admin",
        data={"sku": "WIDGET-1", "name": "Widget", "standard_cost": "3.50"})
    assert row["sku"] == "WIDGET-1"
    out = SystemEntityService.list_records(slug="inventory_item", workspace_id=ws, role="admin")
    assert out["count"] == 1 and out["results"][0]["name"] == "Widget"


# ── Gate 9: permissions + capabilities + tenant isolation ────────────────────────
def test_read_only_entity_rejects_create():
    ws = uuid.uuid4()
    with pytest.raises(SystemEntityError):
        SystemEntityService.create(slug="treasury_transaction", workspace_id=ws, role="admin",
                                   data={})                  # transactions are read-only


def test_member_cannot_create():
    ws = uuid.uuid4()
    provision_accounting(ws)
    with pytest.raises(SystemEntityError):
        SystemEntityService.create(slug="treasury_facility", workspace_id=ws, role="member",
                                   data={"principal": "1000", "currency": "USD"})


def test_tenant_isolation():
    ws1, ws2 = uuid.uuid4(), uuid.uuid4()
    _seed_treasury(ws1)
    out = SystemEntityService.list_records(slug="treasury_facility", workspace_id=ws2, role="admin")
    assert out["count"] == 0                                 # ws2 sees nothing of ws1


# ── Gate 8: no-N+1 (list query count independent of row count) ───────────────────
def test_list_no_nplus1():
    ws = uuid.uuid4()
    _seed_treasury(ws)
    with CaptureQueriesContext(connection) as q1:
        SystemEntityService.list_records(slug="treasury_facility", workspace_id=ws, role="admin")
    base = len(q1)
    for i in range(20):
        TreasuryService.create_facility(workspace_id=ws, principal=str(100 + i), currency="USD",
                                        interest_rate="6")
    with CaptureQueriesContext(connection) as q2:
        SystemEntityService.list_records(slug="treasury_facility", workspace_id=ws, role="admin")
    assert len(q2) == base                                   # +20 rows → same query count


# ── Gate 3/7: REST contract through the real stack ───────────────────────────────
def _client(ws, user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                  HTTP_X_WORKSPACE_SLUG=ws.slug)
    return c


@pytest.fixture
def env(db):
    ws = Workspace.objects.create(name="Acme", slug="acme-se", is_active=True)
    provision_accounting(ws.id)
    admin = User.objects.create_user(email="a@se.com", password=PW, is_verified=True)
    WorkspaceMember.objects.create(workspace=ws, user=admin, role="admin", status="active")
    member = User.objects.create_user(email="m@se.com", password=PW, is_verified=True)
    WorkspaceMember.objects.create(workspace=ws, user=member, role="member", status="active")
    return {"ws": ws, "admin": _client(ws, admin), "member": _client(ws, member)}


def test_rest_entity_list_and_descriptor(env):
    r = env["member"].get("/api/v1/system-entities/")
    assert r.status_code == 200
    slugs = {e["slug"] for e in r.data}
    assert {"treasury_facility", "inventory_item"} <= slugs
    d = env["member"].get("/api/v1/system-entities/treasury_facility/")
    assert d.status_code == 200 and d.data["kind"] == "system"
    assert any(f["name"] == "principal" for f in d.data["fields"])


def test_rest_records_crud_and_authz(env):
    # admin creates via REST
    c = env["admin"].post("/api/v1/system-entities/treasury_facility/records/",
                          {"principal": "70000", "currency": "USD", "interest_rate": "5"},
                          format="json")
    assert c.status_code == 201 and c.data["principal"] == "70000.00"
    rid = c.data["id"]
    # list + detail
    lst = env["admin"].get("/api/v1/system-entities/treasury_facility/records/")
    assert lst.status_code == 200 and lst.data["count"] == 1
    det = env["admin"].get(f"/api/v1/system-entities/treasury_facility/records/{rid}/")
    assert det.status_code == 200 and det.data["number"].startswith("BOR-")
    # member forbidden to create (write gate)
    assert env["member"].post("/api/v1/system-entities/treasury_facility/records/",
                              {"principal": "1", "currency": "USD"},
                              format="json").status_code == 400
    # member can read
    assert env["member"].get("/api/v1/system-entities/treasury_facility/records/").status_code == 200


def test_rest_unknown_entity_404(env):
    assert env["admin"].get("/api/v1/system-entities/nope/").status_code == 404
    assert env["admin"].get("/api/v1/system-entities/nope/records/").status_code == 404
