"""
Platform capability test: a record-action workflow step can target a RELATED record via a
``{{record.field}}`` template in ``record_id`` (not only its own trigger record). Generic; no
industry package referenced.
"""
import uuid
from types import SimpleNamespace

import pytest

from apps.metadata.models import EntityDefinition
from apps.records.services import RecordService
from apps.schema_registry.services import SchemaRegistryService
from apps.solution_templates.documents import system_member
from apps.workflows.executors import exec_set_field, exec_update_record


def _run(ws, record_id=None):
    return SimpleNamespace(workspace_id=ws, initiated_by=uuid.uuid4(),
                           record_id=record_id, id=uuid.uuid4())


@pytest.fixture
def graph(db):
    ws = uuid.uuid4()
    SchemaRegistryService.create_entity(
        workspace_id=ws, slug="node", name="Node", plural_name="Nodes",
        fields=[{"slug": "name", "name": "Name", "field_type": "text", "is_promoted": True},
                {"slug": "ref", "name": "Ref", "field_type": "lookup", "is_promoted": True,
                 "config": {"target_entity_slug": "node"}}],
        created_by=None)
    member = system_member(None)
    entity = EntityDefinition.objects.get(workspace_id=ws, slug="node")
    target = RecordService.create_record(workspace_id=ws, member=member, entity=entity,
                                         data={"name": "target"})
    source = RecordService.create_record(workspace_id=ws, member=member, entity=entity,
                                         data={"name": "source", "ref": str(target["id"])})
    return ws, member, entity, target["id"], source


@pytest.mark.django_db
def test_update_targets_related_record_via_template(graph):
    ws, member, entity, target_id, source = graph
    step = SimpleNamespace(config={"entity_slug": "node", "record_id": "{{record.ref}}",
                                   "data": {"name": "updated-by-related"}})
    exec_update_record(step, _run(ws), {"record": source}, member)
    updated = RecordService.retrieve_record(workspace_id=ws, member=member, entity=entity,
                                            record_id=target_id)
    assert updated["name"] == "updated-by-related"


@pytest.mark.django_db
def test_set_field_targets_related_record(graph):
    ws, member, entity, target_id, source = graph
    step = SimpleNamespace(config={"entity_slug": "node", "record_id": "{{record.ref}}",
                                   "field": "name", "value": "set-on-related"})
    exec_set_field(step, _run(ws), {"record": source}, member)
    updated = RecordService.retrieve_record(workspace_id=ws, member=member, entity=entity,
                                            record_id=target_id)
    assert updated["name"] == "set-on-related"


@pytest.mark.django_db
def test_plain_record_id_still_works(graph):
    ws, member, entity, target_id, source = graph
    # a non-template record_id passes through unchanged
    step = SimpleNamespace(config={"entity_slug": "node", "record_id": str(target_id),
                                   "data": {"name": "plain"}})
    exec_update_record(step, _run(ws), {}, member)
    assert RecordService.retrieve_record(
        workspace_id=ws, member=member, entity=entity, record_id=target_id)["name"] == "plain"


@pytest.mark.django_db
def test_falls_back_to_trigger_record(graph):
    ws, member, entity, target_id, source = graph
    # no record_id in config → acts on the run's trigger record
    step = SimpleNamespace(config={"entity_slug": "node", "data": {"name": "trigger"}})
    exec_update_record(step, _run(ws, record_id=target_id), {}, member)
    assert RecordService.retrieve_record(
        workspace_id=ws, member=member, entity=entity, record_id=target_id)["name"] == "trigger"
