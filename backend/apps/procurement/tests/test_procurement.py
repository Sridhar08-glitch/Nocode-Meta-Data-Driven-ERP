"""
Procurement Solution (Phase P2.5) — framework provisioning + the native integrity seams:
gapless numbering, Goods-Receipt → Inventory ledger, Vendor-Bill → GL event, audit, RBAC.
"""
import uuid

import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.eventstore.models import DomainEvent
from apps.inventory.models import Item, StockMovement
from apps.metadata.models import EntityDefinition
from apps.permissions.models import Role
from apps.procurement.blueprint import seed_procurement_template
from apps.procurement.services import ProcurementService
from apps.reporting.models import Dashboard
from apps.solution_templates import services as st
from apps.solution_templates.models import SolutionTemplate
from apps.studio.models import Application
from apps.tenancy.models import Workspace, WorkspaceMember
from apps.workflows.models import WorkflowDefinition

PW = "Sup3rStr0ng!pw"
BASE = "/api/v1/procurement"


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


def _install(ws):
    tpl = seed_procurement_template()
    return st.install(template_id=tpl.id, workspace_id=ws, installed_by=None)


# ── framework provisioning ───────────────────────────────────────────────────
@pytest.mark.django_db
def test_seed_creates_published_system_template():
    tpl = seed_procurement_template()
    assert tpl.slug == "procurement" and tpl.is_system and tpl.is_published
    # idempotent
    assert SolutionTemplate.objects.filter(slug="procurement").count() == 1
    seed_procurement_template()
    assert SolutionTemplate.objects.filter(slug="procurement").count() == 1


@pytest.mark.django_db
def test_install_provisions_full_procurement_solution():
    ws = uuid.uuid4()
    _install(ws)
    for slug in ["vendor", "rfq", "purchase_order", "goods_receipt", "vendor_bill",
                 "purchase_order_line", "goods_receipt_line"]:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    for wf in ["rfq_approval", "po_approval", "gr_validation", "vb_approval"]:
        assert WorkflowDefinition.objects.filter(workspace_id=ws, slug=wf).exists(), wf
    assert Role.objects.filter(workspace_id=ws, slug="procurement_manager").exists()
    assert Role.objects.filter(workspace_id=ws, slug="buyer").exists()
    assert Dashboard.objects.filter(workspace_id=ws).count() == 2
    assert Application.objects.filter(workspace_id=ws, slug="procurement").exists()


# ── numbering ────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_create_document_allocates_gapless_number():
    ws = uuid.uuid4()
    _install(ws)
    po1 = ProcurementService.create_document(
        workspace_id=ws, entity_slug="purchase_order",
        data={"status": "draft"}, actor_id=None)
    po2 = ProcurementService.create_document(
        workspace_id=ws, entity_slug="purchase_order",
        data={"status": "draft"}, actor_id=None)
    assert po1["number"] == "PO-000001"
    assert po2["number"] == "PO-000002"
    assert DomainEvent.objects.filter(event_type="procurement.po.created").count() == 2


# ── Goods Receipt → Inventory ─────────────────────────────────────────────────
@pytest.mark.django_db
def test_goods_receipt_posting_increases_stock_idempotently():
    ws = uuid.uuid4()
    _install(ws)
    gr = ProcurementService.create_document(
        workspace_id=ws, entity_slug="goods_receipt",
        data={"warehouse_code": "MAIN", "status": "received"}, actor_id=None)
    assert gr["number"] == "GR-000001"
    for sku, qty, cost in [("W-1", 10, "2.00"), ("W-2", 5, "4.00")]:
        ProcurementService.create_document(
            workspace_id=ws, entity_slug="goods_receipt_line",
            data={"goods_receipt": gr["id"], "item_sku": sku,
                  "quantity": qty, "unit_cost": cost}, actor_id=None)

    posted = ProcurementService.post_goods_receipt(workspace_id=ws, record_id=gr["id"])
    assert posted["status"] == "posted"
    assert Item.objects.filter(workspace_id=ws, sku="W-1").exists()
    assert StockMovement.objects.filter(workspace_id=ws).count() == 2
    assert DomainEvent.objects.filter(event_type="procurement.receipt.posted").count() == 1

    # idempotent: re-posting does nothing further
    ProcurementService.post_goods_receipt(workspace_id=ws, record_id=gr["id"])
    assert StockMovement.objects.filter(workspace_id=ws).count() == 2
    assert DomainEvent.objects.filter(event_type="procurement.receipt.posted").count() == 1


# ── Vendor Bill → GL ──────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_vendor_bill_posting_emits_gl_event(monkeypatch):
    from apps.ledger import services as ledger_services
    ws = uuid.uuid4()
    _install(ws)
    vb = ProcurementService.create_document(
        workspace_id=ws, entity_slug="vendor_bill",
        data={"amount": "150.00", "status": "approved"}, actor_id=None)

    calls = {}

    def fake_post_event(workspace_id, event_type, context, **kw):
        calls["event_type"] = event_type
        calls["amount"] = context.get("amount")
        return None  # no PostingRule configured → no-op (contract still fires)

    monkeypatch.setattr(ledger_services.GLBus, "post_event", staticmethod(fake_post_event))

    posted = ProcurementService.post_vendor_bill(workspace_id=ws, record_id=vb["id"])
    assert posted["status"] == "posted"
    assert calls["event_type"] == "vendor_bill.posted"
    assert float(calls["amount"]) == 150.0
    assert DomainEvent.objects.filter(event_type="procurement.bill.posted").count() == 1

    # idempotent
    ProcurementService.post_vendor_bill(workspace_id=ws, record_id=vb["id"])
    assert DomainEvent.objects.filter(event_type="procurement.bill.posted").count() == 1


@pytest.mark.django_db
def test_approve_document_emits_approved_event():
    ws = uuid.uuid4()
    _install(ws)
    rfq = ProcurementService.create_document(
        workspace_id=ws, entity_slug="rfq", data={"status": "sent"}, actor_id=None)
    approved = ProcurementService.approve_document(
        workspace_id=ws, entity_slug="rfq", record_id=rfq["id"])
    assert approved["status"] == "approved"
    assert DomainEvent.objects.filter(event_type="procurement.rfq.approved").exists()


# ── API ──────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_setup_requires_admin(workspace):
    _install(workspace.id)
    cm, _ = _client(workspace, "member", "m@e.com")
    assert cm.post(f"{BASE}/setup/").status_code == 403
    ca, _ = _client(workspace, "admin", "a@e.com")
    assert ca.post(f"{BASE}/setup/").status_code == 200


@pytest.mark.django_db
def test_create_and_post_receipt_via_api(workspace):
    _install(workspace.id)
    ca, _ = _client(workspace, "admin")

    gr = ca.post(f"{BASE}/goods_receipt/",
                 {"warehouse_code": "MAIN", "status": "received"}, format="json")
    assert gr.status_code == 201
    gr_id = gr.json()["id"]
    assert gr.json()["number"] == "GR-000001"

    ca.post(f"{BASE}/goods_receipt_line/",
            {"goods_receipt": gr_id, "item_sku": "A-1", "quantity": 3, "unit_cost": "5.00"},
            format="json")
    resp = ca.post(f"{BASE}/goods-receipts/{gr_id}/post/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "posted"
    assert StockMovement.objects.filter(workspace_id=workspace.id).count() == 1
