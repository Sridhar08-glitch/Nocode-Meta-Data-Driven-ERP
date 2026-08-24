"""
Phase 1.10 — physical tables are projections of the event stream.

Proves a table can be truncated and fully rebuilt by replaying its record.*
events (replay / time-travel / PITR foundation), and the per-record timeline.
"""
import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.records import dal
from apps.records.projections import rebuild_entity_records
from apps.records.services import RecordService
from apps.schema_registry.services import SchemaRegistryService
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"


@pytest.fixture
def setup(db):
    ws = Workspace.objects.create(name="Acme", slug="acme", is_active=True)
    user = User.objects.create_user(email="reb@acme.com", password=PW, is_verified=True)
    member = WorkspaceMember.objects.create(workspace=ws, user=user, role="admin", status="active")
    ent = SchemaRegistryService.create_entity(
        workspace_id=ws.id, slug="lead", name="Lead", plural_name="Leads")
    SchemaRegistryService.add_field(workspace_id=ws.id, entity_slug="lead", slug="name",
                                    name="Name", field_type="text", is_promoted=True, is_required=True)
    SchemaRegistryService.add_field(workspace_id=ws.id, entity_slug="lead", slug="value",
                                    name="Value", field_type="decimal", is_promoted=True)
    SchemaRegistryService.add_field(workspace_id=ws.id, entity_slug="lead", slug="notes",
                                    name="Notes", field_type="text", is_promoted=False)
    ent.refresh_from_db()
    return ws, user, member, ent


@pytest.mark.django_db
class TestRecordRebuild:
    def test_rebuild_from_events(self, setup):
        ws, user, member, ent = setup
        r1 = RecordService.create_record(workspace_id=ws.id, member=member, entity=ent,
                                         data={"name": "A", "value": 100, "notes": "x"})
        r2 = RecordService.create_record(workspace_id=ws.id, member=member, entity=ent,
                                         data={"name": "B", "value": 50})
        RecordService.update_record(workspace_id=ws.id, member=member, entity=ent,
                                    record_id=r1["id"], data={"value": 200})
        RecordService.delete_record(workspace_id=ws.id, member=member, entity=ent, record_id=r2["id"])

        replayed = rebuild_entity_records(ent)         # truncate + replay
        assert replayed == 4                            # 2 created + 1 updated + 1 deleted

        fmap = dal.FieldMap(ent)
        rec1 = dal.get_row(ent, fmap, r1["id"])
        assert rec1 is not None and int(rec1["value"]) == 200 and rec1["notes"] == "x"
        # r2 was deleted ⇒ absent from active rows, present when include_deleted
        assert dal.get_row(ent, fmap, r2["id"]) is None
        assert dal.get_row(ent, fmap, r2["id"], include_deleted=True) is not None

    def test_rebuild_idempotent(self, setup):
        ws, user, member, ent = setup
        RecordService.create_record(workspace_id=ws.id, member=member, entity=ent,
                                    data={"name": "A", "value": 100})
        rebuild_entity_records(ent)
        rebuild_entity_records(ent)                     # twice → still one row
        rows = RecordService.list_records(workspace_id=ws.id, member=member, entity=ent)
        assert len(rows) == 1 and int(rows[0]["value"]) == 100


@pytest.mark.django_db
class TestTimeline:
    def test_record_timeline(self, setup):
        ws, user, member, ent = setup
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                      HTTP_X_WORKSPACE_SLUG="acme")
        rid = c.post("/api/v1/data/lead/", {"name": "A", "value": 1}, format="json").data["id"]
        c.patch(f"/api/v1/data/lead/{rid}/", {"value": 2}, format="json")
        r = c.get(f"/api/v1/data/lead/{rid}/timeline/")
        assert r.status_code == 200
        evs = r.data["events"]
        assert [e["event_type"] for e in evs] == ["record.created", "record.updated"]
        assert evs[0]["version"] == 1 and evs[1]["version"] == 2
        assert "value" in evs[1]["changed_fields"]
