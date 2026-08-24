"""Declarative package migration runner — validation, ordering, schema ops, and backfill."""
import uuid

import pytest

from apps.metadata.models import EntityDefinition, FieldDefinition
from apps.packaging import package_migrations as pm
from apps.records.services import RecordService
from apps.solution_templates import services as sol
from apps.solution_templates.documents import system_member
from apps.solution_templates.seeding import seed_system_templates


# ── pure ──────────────────────────────────────────────────────────────────────
def test_validate_migrations():
    assert pm.validate_migrations([]) == []
    errs = pm.validate_migrations([
        {"version": "bad", "operations": "nope"},
        {"version": "1.0.0", "operations": [{"op": "ghost"}]},
        {"version": "1.0.0", "operations": [{"op": "add_field", "entity": "x"}]},  # missing field
    ])
    joined = " ".join(errs)
    assert "is not a valid version" in joined
    assert "must be a list" in joined
    assert "unknown op" in joined
    assert "duplicate version" in joined
    assert "missing 'field'" in joined


def test_pending_versions_ordering():
    migs = [{"version": "1.2.0"}, {"version": "1.0.0"}, {"version": "1.1.0"}]
    out = [m["version"] for m in pm.pending_versions(migs, "1.0.0")]
    assert out == ["1.1.0", "1.2.0"]            # > from_version, ascending
    assert [m["version"] for m in pm.pending_versions(migs, "")] == ["1.0.0", "1.1.0", "1.2.0"]


# ── execution ─────────────────────────────────────────────────────────────────
@pytest.fixture
def installed_crm(db):
    tpl = seed_system_templates()[0]
    ws = uuid.uuid4()
    sol.install(template_id=tpl.id, workspace_id=ws, installed_by=None)
    return ws


@pytest.mark.django_db
def test_schema_ops_add_field_set_default_deprecate(installed_crm):
    ws = installed_crm
    migration = {"version": "1.1.0", "operations": [
        {"op": "add_field", "entity": "customer",
         "field": {"slug": "loyalty_tier", "name": "Loyalty Tier", "field_type": "text",
                   "is_promoted": True}},
        {"op": "set_default", "entity": "customer", "field": "loyalty_tier", "value": "bronze"},
        {"op": "deprecate_field", "entity": "customer", "field": "industry"},
    ]}
    pm.run_migration(migration, workspace_id=ws, actor_id=None)

    ent = EntityDefinition.objects.get(workspace_id=ws, slug="customer")
    new = FieldDefinition.objects.get(workspace_id=ws, entity_id=ent.id, slug="loyalty_tier")
    assert new.config.get("default_value") == "bronze"
    industry = FieldDefinition.objects.get(workspace_id=ws, entity_id=ent.id, slug="industry")
    assert industry.config.get("deprecated") is True


@pytest.mark.django_db
def test_add_field_is_idempotent(installed_crm):
    ws = installed_crm
    op = {"version": "1.1.0", "operations": [
        {"op": "add_field", "entity": "customer",
         "field": {"slug": "segment", "name": "Segment", "field_type": "text"}}]}
    pm.run_migration(op, workspace_id=ws, actor_id=None)
    pm.run_migration(op, workspace_id=ws, actor_id=None)   # second run must not error/dup
    ent = EntityDefinition.objects.get(workspace_id=ws, slug="customer")
    assert FieldDefinition.objects.filter(
        workspace_id=ws, entity_id=ent.id, slug="segment").count() == 1


@pytest.mark.django_db
def test_backfill_sets_constant_where_empty(installed_crm):
    ws = installed_crm
    ent = EntityDefinition.objects.get(workspace_id=ws, slug="customer")
    member = system_member(None)
    empty = RecordService.create_record(
        workspace_id=ws, member=member, entity=ent, data={"name": "Acme"})
    filled = RecordService.create_record(
        workspace_id=ws, member=member, entity=ent,
        data={"name": "Globex", "industry": "tech"})
    assert (empty.get("industry") or "") == ""

    pm.run_migration(
        {"version": "1.1.0", "operations": [
            {"op": "backfill", "entity": "customer", "field": "industry", "value": "general"}]},
        workspace_id=ws, actor_id=None)

    a = RecordService.retrieve_record(workspace_id=ws, member=member, entity=ent,
                                      record_id=empty["id"])
    b = RecordService.retrieve_record(workspace_id=ws, member=member, entity=ent,
                                      record_id=filled["id"])
    assert a["industry"] == "general"     # was empty → backfilled
    assert b["industry"] == "tech"        # already set → untouched


@pytest.mark.django_db
def test_backfill_unknown_field_raises(installed_crm):
    ws = installed_crm
    with pytest.raises(pm.MigrationError):
        pm.run_migration(
            {"version": "1.1.0", "operations": [
                {"op": "backfill", "entity": "customer", "field": "ghost", "value": "x"}]},
            workspace_id=ws, actor_id=None)


@pytest.mark.django_db
def test_run_pending_tracks_applied(installed_crm):
    ws = installed_crm
    migs = [
        {"version": "1.1.0", "operations": [
            {"op": "add_field", "entity": "customer",
             "field": {"slug": "f1", "name": "F1", "field_type": "text"}}]},
        {"version": "1.2.0", "operations": [
            {"op": "add_field", "entity": "customer",
             "field": {"slug": "f2", "name": "F2", "field_type": "text"}}]},
    ]
    applied = pm.run_pending(migs, workspace_id=ws, from_version="1.0.0", actor_id=None)
    assert applied == ["1.1.0", "1.2.0"]
    # already-applied are skipped
    again = pm.run_pending(migs, workspace_id=ws, from_version="1.0.0",
                           already_applied=applied)
    assert again == []
