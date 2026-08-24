"""Computed Fields Engine — formula (safe eval) + rollup + cycle detection (§39)."""
import pytest

from apps.accounts.models import User
from apps.computed.services import ComputedError, compute_rollup, safe_eval
from apps.records.services import RecordService
from apps.schema_registry.services import SchemaRegistryService
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"


@pytest.fixture
def setup(db):
    ws = Workspace.objects.create(name="Acme", slug="acme", is_active=True)
    user = User.objects.create_user(email="cf@acme.com", password=PW, is_verified=True)
    member = WorkspaceMember.objects.create(workspace=ws, user=user, role="admin", status="active")
    ent = SchemaRegistryService.create_entity(
        workspace_id=ws.id, slug="line", name="Line", plural_name="Lines")
    SchemaRegistryService.add_field(workspace_id=ws.id, entity_slug="line", slug="price",
                                    name="Price", field_type="decimal", is_promoted=True)
    SchemaRegistryService.add_field(workspace_id=ws.id, entity_slug="line", slug="qty",
                                    name="Qty", field_type="integer", is_promoted=True)
    # formula field (overflow): total = price * qty
    SchemaRegistryService.add_field(workspace_id=ws.id, entity_slug="line", slug="total",
                                    name="Total", field_type="formula", is_promoted=False)
    line = ent.fields.get(slug="total")
    line.config = {"expression": "price * qty", "result_type": "decimal"}
    line.save(update_fields=["config"])
    ent.refresh_from_db()
    return ws, member, ent


@pytest.mark.django_db
class TestComputed:
    def test_safe_eval_rejects_calls(self):
        assert safe_eval("a * 2 + 1", {"a": 5}) == 11
        with pytest.raises(ComputedError):
            safe_eval("__import__('os').system('x')", {})

    def test_formula_on_create_and_update(self, setup):
        ws, member, ent = setup
        rec = RecordService.create_record(workspace_id=ws.id, member=member, entity=ent,
                                          data={"price": 10, "qty": 3})
        assert float(rec["total"]) == 30.0
        upd = RecordService.update_record(workspace_id=ws.id, member=member, entity=ent,
                                          record_id=rec["id"], data={"qty": 5})
        assert float(upd["total"]) == 50.0

    def test_circular_formula_detected(self, setup):
        ws, member, ent = setup
        for slug, expr in [("a", "b + 1"), ("b", "a + 1")]:
            SchemaRegistryService.add_field(workspace_id=ws.id, entity_slug="line", slug=slug,
                                            name=slug, field_type="formula", is_promoted=False)
            fd = ent.fields.get(slug=slug)
            fd.config = {"expression": expr}
            fd.save(update_fields=["config"])
        with pytest.raises(ComputedError, match="Circular"):
            RecordService.create_record(workspace_id=ws.id, member=member, entity=ent,
                                        data={"price": 1, "qty": 1})

    def test_rollup_aggregates_children(self, setup):
        ws, member, parent_ent = setup
        # child entity 'pay' with parent_id + amount; rollup sum on the parent entity
        child = SchemaRegistryService.create_entity(
            workspace_id=ws.id, slug="pay", name="Pay", plural_name="Pays")
        SchemaRegistryService.add_field(workspace_id=ws.id, entity_slug="pay", slug="parent_id",
                                        name="Parent", field_type="uuid", is_promoted=True)
        SchemaRegistryService.add_field(workspace_id=ws.id, entity_slug="pay", slug="amount",
                                        name="Amount", field_type="decimal", is_promoted=True)
        child.refresh_from_db()
        line = RecordService.create_record(workspace_id=ws.id, member=member, entity=parent_ent,
                                           data={"price": 1, "qty": 1})
        for amt in (100, 250):
            RecordService.create_record(workspace_id=ws.id, member=member, entity=child,
                                        data={"parent_id": line["id"], "amount": amt})
        # a rollup field config aggregating child 'amount' where parent_id == this record
        rollup_fd = type("F", (), {"config": {
            "source_entity_slug": "pay", "match_field": "parent_id", "agg": "sum", "field": "amount"}})()
        total = compute_rollup(parent_ent, line["id"], rollup_fd)
        assert float(total) == 350.0
