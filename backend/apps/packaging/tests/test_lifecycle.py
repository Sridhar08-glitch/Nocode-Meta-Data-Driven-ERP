"""Full package lifecycle through the authoritative installer: install → upgrade (with a
declarative migration) → rollback → disable → enable."""
import uuid

import pytest

from apps.metadata.models import EntityDefinition, FieldDefinition
from apps.solution_templates import services as sol
from apps.solution_templates.models import InstalledSolution, SolutionTemplate


def _entity(slug, fields):
    return {"slug": slug, "name": slug.title(), "plural_name": slug.title() + "s",
            "fields": fields}


def _v1():
    return {"schema_version": 1,
            "package": {"slug": "widget", "name": "Widget", "version": "1.0.0",
                        "author": "Acme", "min_core_version": "2.0.0"},
            "entities": [_entity("widget", [
                {"slug": "name", "name": "Name", "field_type": "text", "is_promoted": True}])]}


def _v2():
    return {"schema_version": 1,
            "package": {"slug": "widget", "name": "Widget", "version": "1.1.0",
                        "author": "Acme", "min_core_version": "2.0.0",
                        "migrations": [{"version": "1.1.0", "operations": [
                            {"op": "add_field", "entity": "widget",
                             "field": {"slug": "tier", "name": "Tier", "field_type": "text",
                                       "is_promoted": True}},
                            {"op": "set_default", "entity": "widget", "field": "tier",
                             "value": "standard"}]}]},
            "entities": [_entity("widget", [
                {"slug": "name", "name": "Name", "field_type": "text", "is_promoted": True},
                {"slug": "color", "name": "Color", "field_type": "text", "is_promoted": True}])]}


@pytest.fixture
def template(db):
    return SolutionTemplate.objects.create(
        slug="widget", name="Widget", version="1.0.0", is_published=True, manifest=_v1())


@pytest.mark.django_db
def test_install_records_manifest_and_version(template):
    ws = uuid.uuid4()
    inst = sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    assert inst.installed_version == "1.0.0"
    assert inst.installed_manifest["package"]["slug"] == "widget"
    assert EntityDefinition.objects.filter(workspace_id=ws, slug="widget").exists()


@pytest.mark.django_db
def test_upgrade_applies_new_fields_and_migrations(template):
    ws = uuid.uuid4()
    inst = sol.install(template_id=template.id, workspace_id=ws, installed_by=None)

    upgraded = sol.upgrade(installed_id=inst.id, workspace_id=ws, actor_id=None,
                           manifest=_v2(), version="1.1.0")
    assert upgraded.installed_version == "1.1.0"
    assert upgraded.applied_migrations == ["1.1.0"]
    ent = EntityDefinition.objects.get(workspace_id=ws, slug="widget")
    fields = set(FieldDefinition.objects.filter(
        workspace_id=ws, entity_id=ent.id).values_list("slug", flat=True))
    assert {"name", "color", "tier"} <= fields            # new field + migration field
    tier = FieldDefinition.objects.get(workspace_id=ws, entity_id=ent.id, slug="tier")
    assert tier.config.get("default_value") == "standard"
    # previous manifest retained for rollback
    assert upgraded.previous_manifest["package"]["version"] == "1.0.0"


@pytest.mark.django_db
def test_upgrade_migration_runs_once(template):
    ws = uuid.uuid4()
    inst = sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    sol.upgrade(installed_id=inst.id, workspace_id=ws, actor_id=None,
                manifest=_v2(), version="1.1.0")
    # re-upgrade to same version: migration already applied, not repeated
    again = sol.upgrade(installed_id=inst.id, workspace_id=ws, actor_id=None,
                        manifest=_v2(), version="1.1.0")
    assert again.applied_migrations == ["1.1.0"]


@pytest.mark.django_db
def test_rollback_restores_version_but_keeps_schema(template):
    ws = uuid.uuid4()
    inst = sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    sol.upgrade(installed_id=inst.id, workspace_id=ws, actor_id=None,
                manifest=_v2(), version="1.1.0")

    rolled = sol.rollback(installed_id=inst.id, workspace_id=ws, actor_id=None)
    assert rolled.installed_version == "1.0.0"
    assert rolled.installed_manifest["package"]["version"] == "1.0.0"
    # data safety: schema additions are NOT undone
    ent = EntityDefinition.objects.get(workspace_id=ws, slug="widget")
    assert FieldDefinition.objects.filter(
        workspace_id=ws, entity_id=ent.id, slug="tier").exists()


@pytest.mark.django_db
def test_rollback_without_previous_raises(template):
    ws = uuid.uuid4()
    inst = sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    with pytest.raises(sol.SolutionTemplateError):
        sol.rollback(installed_id=inst.id, workspace_id=ws, actor_id=None)


@pytest.mark.django_db
def test_disable_then_enable_round_trip(template):
    ws = uuid.uuid4()
    inst = sol.install(template_id=template.id, workspace_id=ws, installed_by=None)

    sol.uninstall(installed_id=inst.id, workspace_id=ws, actor_id=None)
    assert InstalledSolution.objects.get(id=inst.id).status == "disabled"

    enabled = sol.enable(installed_id=inst.id, workspace_id=ws, actor_id=None)
    assert enabled.status == "active"
    # entity reactivated
    assert EntityDefinition.objects.get(workspace_id=ws, slug="widget").is_active is True


@pytest.mark.django_db
def test_upgrade_blocks_on_unsatisfied_dependency(template):
    ws = uuid.uuid4()
    inst = sol.install(template_id=template.id, workspace_id=ws, installed_by=None)
    bad = _v2()
    bad["package"]["requires_packages"] = [{"slug": "inventory", "version": ">=1.0.0"}]
    with pytest.raises(sol.SolutionTemplateError):
        sol.upgrade(installed_id=inst.id, workspace_id=ws, actor_id=None,
                    manifest=bad, version="1.1.0")
