"""Business Rules Engine — decisions on record save (master spec §38)."""
import pytest

from apps.accounts.models import User
from apps.records.services import RecordService
from apps.rules.models import BusinessRule, RuleExecutionLog
from apps.rules.services import RuleBlocked
from apps.schema_registry.services import SchemaRegistryService
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"


@pytest.fixture
def setup(db):
    ws = Workspace.objects.create(name="Acme", slug="acme", is_active=True)
    user = User.objects.create_user(email="r@acme.com", password=PW, is_verified=True)
    member = WorkspaceMember.objects.create(workspace=ws, user=user, role="admin", status="active")
    ent = SchemaRegistryService.create_entity(
        workspace_id=ws.id, slug="lead", name="Lead", plural_name="Leads")
    for slug, ftype in [("name", "text"), ("status", "text"), ("value", "decimal")]:
        SchemaRegistryService.add_field(workspace_id=ws.id, entity_slug="lead", slug=slug,
                                        name=slug.title(), field_type=ftype, is_promoted=True)
    ent.refresh_from_db()
    return ws, member, ent


@pytest.mark.django_db
class TestRulesEngine:
    def test_rule_sets_field_when_condition_matches(self, setup):
        ws, member, ent = setup
        BusinessRule.objects.create(
            workspace_id=ws.id, slug="hot", name="Hot", entity_id=ent.id,
            trigger_on="before_create", condition_nql="value > 1000",
            actions=[{"type": "set_field", "field": "status", "value": "hot"}], priority=100)
        hot = RecordService.create_record(workspace_id=ws.id, member=member, entity=ent,
                                          data={"name": "A", "value": 2000})
        assert hot["status"] == "hot"
        cold = RecordService.create_record(workspace_id=ws.id, member=member, entity=ent,
                                           data={"name": "B", "value": 500})
        assert cold["status"] != "hot"
        assert RuleExecutionLog.objects.filter(workspace_id=ws.id).count() == 2

    def test_block_save(self, setup):
        ws, member, ent = setup
        BusinessRule.objects.create(
            workspace_id=ws.id, slug="noneg", name="No Negative", entity_id=ent.id,
            trigger_on="before_create", condition_nql="value < 0",
            actions=[{"type": "block_save"}], priority=10)
        with pytest.raises(RuleBlocked):
            RecordService.create_record(workspace_id=ws.id, member=member, entity=ent,
                                        data={"name": "X", "value": -5})

    def test_priority_and_run_all_false_stops_chain(self, setup):
        ws, member, ent = setup
        BusinessRule.objects.create(
            workspace_id=ws.id, slug="r1", name="R1", entity_id=ent.id, trigger_on="before_create",
            condition_nql="", actions=[{"type": "set_field", "field": "status", "value": "first"}],
            priority=10, run_all=False)
        BusinessRule.objects.create(
            workspace_id=ws.id, slug="r2", name="R2", entity_id=ent.id, trigger_on="before_create",
            condition_nql="", actions=[{"type": "set_field", "field": "status", "value": "second"}],
            priority=20)
        rec = RecordService.create_record(workspace_id=ws.id, member=member, entity=ent,
                                          data={"name": "A", "value": 1})
        assert rec["status"] == "first"   # r1 (priority 10, run_all=False) stopped the chain
