"""
Inventory Engine (Phase P2.4) — weighted-average + FIFO costing, negative-stock guard, transfer,
adjustments, reports, GL hook, API, and workspace isolation.
"""
import uuid
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.inventory.models import AVERAGE, FIFO, Item, StockLevel, Warehouse
from apps.inventory.services import InventoryError, InventoryService
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"
BASE = "/api/v1/inventory"


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


def _item(ws, sku="W-1", method=AVERAGE):
    return Item.objects.create(workspace_id=ws, sku=sku, name="Widget", valuation_method=method)


def _wh(ws, code="MAIN"):
    return Warehouse.objects.create(workspace_id=ws, code=code, name=code)


def _level(ws, item, wh):
    return StockLevel.objects.get(workspace_id=ws, item=item, warehouse=wh)


# ── weighted average ───────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestAverageCosting:
    def test_moving_average_on_receipts(self):
        ws = uuid.uuid4()
        item, wh = _item(ws), _wh(ws)
        InventoryService.receive(ws, item.id, wh.id, 10, "2.00")   # 10 @ 2 → value 20
        InventoryService.receive(ws, item.id, wh.id, 10, "4.00")   # +10 @ 4 → value 60, avg 3
        lvl = _level(ws, item, wh)
        assert lvl.on_hand == Decimal("10.0000") * 2
        assert lvl.avg_cost == Decimal("3.0000")
        assert lvl.value == Decimal("60.00")

    def test_issue_relieves_at_average(self):
        ws = uuid.uuid4()
        item, wh = _item(ws), _wh(ws)
        InventoryService.receive(ws, item.id, wh.id, 10, "2.00")
        InventoryService.receive(ws, item.id, wh.id, 10, "4.00")   # avg 3
        mv = InventoryService.issue(ws, item.id, wh.id, 5)         # 5 @ 3 = 15
        assert mv.total_cost == Decimal("15.00")
        lvl = _level(ws, item, wh)
        assert lvl.on_hand == Decimal("15.0000")
        assert lvl.avg_cost == Decimal("3.0000")        # unchanged
        assert lvl.value == Decimal("45.00")

    def test_issue_to_zero_clears_value(self):
        ws = uuid.uuid4()
        item, wh = _item(ws), _wh(ws)
        InventoryService.receive(ws, item.id, wh.id, 5, "2.00")
        InventoryService.issue(ws, item.id, wh.id, 5)
        lvl = _level(ws, item, wh)
        assert lvl.on_hand == 0 and lvl.value == 0


# ── FIFO ────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestFifoCosting:
    def test_fifo_consumes_oldest_layers(self):
        ws = uuid.uuid4()
        item, wh = _item(ws, "F-1", FIFO), _wh(ws)
        InventoryService.receive(ws, item.id, wh.id, 10, "2.00")   # layer 1: 10 @ 2
        InventoryService.receive(ws, item.id, wh.id, 10, "5.00")   # layer 2: 10 @ 5
        # issue 15 → 10@2 + 5@5 = 20 + 25 = 45
        mv = InventoryService.issue(ws, item.id, wh.id, 15)
        assert mv.total_cost == Decimal("45.00")
        lvl = _level(ws, item, wh)
        assert lvl.on_hand == Decimal("5.0000")
        # remaining is 5 units from layer 2 @ 5 = 25
        assert lvl.value == Decimal("25.00")

    def test_fifo_next_issue_uses_remaining_layer(self):
        ws = uuid.uuid4()
        item, wh = _item(ws, "F-2", FIFO), _wh(ws)
        InventoryService.receive(ws, item.id, wh.id, 10, "2.00")
        InventoryService.receive(ws, item.id, wh.id, 10, "5.00")
        InventoryService.issue(ws, item.id, wh.id, 15)  # leaves 5 @ 5
        mv = InventoryService.issue(ws, item.id, wh.id, 5)
        assert mv.total_cost == Decimal("25.00")


# ── guards + adjust + transfer ────────────────────────────────────────────────────
@pytest.mark.django_db
class TestGuardsAndMoves:
    def test_negative_stock_blocked(self):
        ws = uuid.uuid4()
        item, wh = _item(ws), _wh(ws)
        InventoryService.receive(ws, item.id, wh.id, 3, "1.00")
        with pytest.raises(InventoryError, match="Insufficient"):
            InventoryService.issue(ws, item.id, wh.id, 5)

    def test_allow_negative_issue(self):
        ws = uuid.uuid4()
        item, wh = _item(ws), _wh(ws)
        InventoryService.receive(ws, item.id, wh.id, 3, "1.00")
        mv = InventoryService.issue(ws, item.id, wh.id, 5, allow_negative=True)
        assert mv.on_hand_after == Decimal("-2.0000")

    def test_positive_adjustment(self):
        ws = uuid.uuid4()
        item, wh = _item(ws), _wh(ws)
        InventoryService.adjust(ws, item.id, wh.id, 7, unit_cost="1.50")
        assert _level(ws, item, wh).on_hand == Decimal("7.0000")

    def test_negative_adjustment(self):
        ws = uuid.uuid4()
        item, wh = _item(ws), _wh(ws)
        InventoryService.receive(ws, item.id, wh.id, 10, "1.00")
        InventoryService.adjust(ws, item.id, wh.id, -4)
        assert _level(ws, item, wh).on_hand == Decimal("6.0000")

    def test_transfer_conserves_value(self):
        ws = uuid.uuid4()
        item = _item(ws)
        a, b = _wh(ws, "A"), _wh(ws, "B")
        InventoryService.receive(ws, item.id, a.id, 10, "3.00")
        InventoryService.transfer(ws, item.id, a.id, b.id, 4)
        assert _level(ws, item, a).on_hand == Decimal("6.0000")
        assert _level(ws, item, b).on_hand == Decimal("4.0000")
        assert _level(ws, item, b).value == Decimal("12.00")   # 4 @ 3

    def test_transfer_same_warehouse_rejected(self):
        ws = uuid.uuid4()
        item, wh = _item(ws), _wh(ws)
        InventoryService.receive(ws, item.id, wh.id, 5, "1.00")
        with pytest.raises(InventoryError, match="differ"):
            InventoryService.transfer(ws, item.id, wh.id, wh.id, 1)


# ── reports + GL hook ─────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestReportsAndGL:
    def test_stock_balance_and_valuation(self):
        ws = uuid.uuid4()
        item, wh = _item(ws), _wh(ws)
        InventoryService.receive(ws, item.id, wh.id, 10, "2.50")
        val = InventoryService.valuation(ws)
        assert val["total_value"] == "25.00"
        bal = InventoryService.stock_balance(ws)
        assert bal[0]["on_hand"] == "10.0000" and bal[0]["value"] == "25.00"

    def test_movement_history_records_each_event(self):
        ws = uuid.uuid4()
        item, wh = _item(ws), _wh(ws)
        InventoryService.receive(ws, item.id, wh.id, 10, "2.00")
        InventoryService.issue(ws, item.id, wh.id, 3)
        hist = InventoryService.movement_history(ws, item_id=item.id)
        assert len(hist) == 2
        assert {h["movement_type"] for h in hist} == {"receipt", "issue"}

    def test_receive_posts_to_gl_when_rule_exists(self):
        from apps.ledger.models import LedgerAccount, PostingRule
        ws = uuid.uuid4()
        LedgerAccount.objects.create(workspace_id=ws, code="1200", name="Inventory", account_type="asset")
        LedgerAccount.objects.create(workspace_id=ws, code="2100", name="GRNI", account_type="liability")
        PostingRule.objects.create(workspace_id=ws, event_type="inventory.received", template=[
            {"account_code": "1200", "side": "debit", "amount_field": "amount"},
            {"account_code": "2100", "side": "credit", "amount_field": "amount"}])
        item, wh = _item(ws), _wh(ws)
        mv = InventoryService.receive(ws, item.id, wh.id, 10, "2.00")
        assert mv.journal_entry_id is not None

    def test_receive_without_rule_does_not_break(self):
        ws = uuid.uuid4()
        item, wh = _item(ws), _wh(ws)
        mv = InventoryService.receive(ws, item.id, wh.id, 5, "1.00")
        assert mv.journal_entry_id is None  # no rule → no GL, stock still moved
        assert _level(ws, item, wh).on_hand == Decimal("5.0000")


# ── API ────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestInventoryAPI:
    def test_item_warehouse_crud_admin_only(self, workspace):
        admin, _ = _client(workspace, "admin")
        it = admin.post(f"{BASE}/items/", {"sku": "W-1", "name": "Widget"}, format="json")
        assert it.status_code == 201
        wh = admin.post(f"{BASE}/warehouses/", {"code": "MAIN", "name": "Main"}, format="json")
        assert wh.status_code == 201
        member, _ = _client(workspace, "member")
        assert member.post(f"{BASE}/items/", {"sku": "W-2", "name": "x"}, format="json").status_code == 403

    def test_receive_issue_and_reports_via_api(self, workspace):
        admin, _ = _client(workspace, "admin")
        item_id = admin.post(f"{BASE}/items/", {"sku": "W-1", "name": "Widget"}, format="json").data["id"]
        wh_id = admin.post(f"{BASE}/warehouses/", {"code": "MAIN", "name": "Main"}, format="json").data["id"]
        member, _ = _client(workspace, "member")
        r = member.post(f"{BASE}/receive/", {"item": item_id, "warehouse": wh_id, "quantity": "10", "unit_cost": "2.00"}, format="json")
        assert r.status_code == 201 and r.data["on_hand_after"] == "10.0000"
        i = member.post(f"{BASE}/issue/", {"item": item_id, "warehouse": wh_id, "quantity": "4"}, format="json")
        assert i.status_code == 201 and i.data["total_cost"] == "8.00"
        stock = member.get(f"{BASE}/stock/")
        assert stock.data["rows"][0]["on_hand"] == "6.0000"
        val = member.get(f"{BASE}/valuation/")
        assert val.data["total_value"] == "12.00"

    def test_issue_over_stock_returns_400(self, workspace):
        admin, _ = _client(workspace, "admin")
        item_id = admin.post(f"{BASE}/items/", {"sku": "W-1", "name": "Widget"}, format="json").data["id"]
        wh_id = admin.post(f"{BASE}/warehouses/", {"code": "MAIN", "name": "Main"}, format="json").data["id"]
        r = admin.post(f"{BASE}/issue/", {"item": item_id, "warehouse": wh_id, "quantity": "5"}, format="json")
        assert r.status_code == 400

    def test_transfer_via_api(self, workspace):
        admin, _ = _client(workspace, "admin")
        item_id = admin.post(f"{BASE}/items/", {"sku": "W-1", "name": "Widget"}, format="json").data["id"]
        a = admin.post(f"{BASE}/warehouses/", {"code": "A", "name": "A"}, format="json").data["id"]
        b = admin.post(f"{BASE}/warehouses/", {"code": "B", "name": "B"}, format="json").data["id"]
        admin.post(f"{BASE}/receive/", {"item": item_id, "warehouse": a, "quantity": "10", "unit_cost": "1.00"}, format="json")
        t = admin.post(f"{BASE}/transfer/", {"item": item_id, "from_warehouse": a, "to_warehouse": b, "quantity": "3"}, format="json")
        assert t.status_code == 201
        assert t.data["out"]["movement_type"] == "transfer_out"
        assert t.data["in"]["movement_type"] == "transfer_in"

    def test_workspace_isolation(self, workspace):
        admin, _ = _client(workspace, "admin")
        item_id = admin.post(f"{BASE}/items/", {"sku": "W-1", "name": "Widget"}, format="json").data["id"]
        other = Workspace.objects.create(name="Other", slug="other", is_active=True)
        other_admin, _ = _client(other, "admin", email="other@example.com")
        assert other_admin.get(f"{BASE}/items/{item_id}/").status_code == 404
        assert other_admin.get(f"{BASE}/items/").data == []
