"""Shared fixtures + builders for the workflow engine tests."""

import pytest

from apps.accounts.models import User
from apps.schema_registry.services import SchemaRegistryService
from apps.tenancy.models import Workspace, WorkspaceMember
from apps.workflows.models import (
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowStep,
)

PW = "Sup3rStr0ng!pw"


@pytest.fixture
def ws(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


@pytest.fixture
def user(ws):
    return User.objects.create_user(email="wf@acme.com", password=PW, is_verified=True)


@pytest.fixture
def member(ws, user):
    return WorkspaceMember.objects.create(
        workspace=ws, user=user, role="admin", status="active")


@pytest.fixture
def lead(ws):
    ent = SchemaRegistryService.create_entity(
        workspace_id=ws.id, slug="lead", name="Lead", plural_name="Leads")
    for slug, ftype in [("name", "text"), ("status", "text"), ("stage", "text"),
                        ("value", "decimal"), ("assigned_to", "text")]:
        SchemaRegistryService.add_field(
            workspace_id=ws.id, entity_slug="lead", slug=slug, name=slug.title(),
            field_type=ftype, is_promoted=True)
    ent.refresh_from_db()
    return ent


@pytest.fixture
def make_workflow(ws):
    counter = {"n": 0}

    def _make(trigger_type="manual", trigger_config=None, status="active",
              entity_id=None, retry_policy=None, max_concurrent_runs=10):
        counter["n"] += 1
        return WorkflowDefinition.objects.create(
            workspace_id=ws.id, name=f"WF {counter['n']}", slug=f"wf-{counter['n']}",
            trigger_type=trigger_type, trigger_config=trigger_config or {},
            status=status, entity_id=entity_id, retry_policy=retry_policy or {},
            max_concurrent_runs=max_concurrent_runs)
    return _make


@pytest.fixture
def add_step(ws):
    def _add(wf, step_type, name="step", config=None, is_entry=False,
             on_error="stop", retry_config=None):
        return WorkflowStep.objects.create(
            workflow_id=wf.id, workspace_id=ws.id, step_type=step_type, name=name,
            config=config or {}, is_entry=is_entry, on_error=on_error,
            retry_config=retry_config or {})
    return _add


@pytest.fixture
def add_edge(ws):
    def _add(wf, src, tgt, label="", expr=""):
        return WorkflowEdge.objects.create(
            workflow_id=wf.id, workspace_id=ws.id, source_step_id=src.id,
            target_step_id=tgt.id, condition_label=label, condition_expr=expr)
    return _add


@pytest.fixture
def make_lead_record(ws, member, lead):
    from apps.records.services import RecordService

    def _make(**data):
        data.setdefault("name", "Lead A")
        rec = RecordService.create_record(
            workspace_id=ws.id, member=member, entity=lead, data=data)
        return rec
    return _make
