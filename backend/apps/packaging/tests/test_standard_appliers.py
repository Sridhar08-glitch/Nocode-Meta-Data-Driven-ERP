"""
Platform tests: the standard manifest appliers for existing Core engines (Phase P3.1A).

These provision document_templates / email_templates / portal_grants / approval_processes /
sla_policies / business_hours / kpis from a manifest — each idempotent, each backed by an
existing engine (no duplicated logic). Generic; no industry package referenced.
"""
import uuid

import pytest

from apps.analytics.models import KPIDefinition
from apps.approvals.models import ApprovalProcess
from apps.document_templates.models import DocumentTemplate
from apps.email_templates.models import EmailTemplate
from apps.metadata.models import EntityDefinition
from apps.portal.models import PortalEntityGrant
from apps.sla.models import BusinessHours, SLAPolicy
from apps.solution_templates import appliers
from apps.solution_templates import services as sol
from apps.solution_templates.models import InstalledSolution, SolutionTemplate


def _manifest():
    return {
        "schema_version": 1,
        "entities": [{"slug": "thing", "name": "Thing", "plural_name": "Things",
                      "fields": [{"slug": "name", "name": "Name", "field_type": "text",
                                  "is_promoted": True}]}],
        "document_templates": [{"slug": "dt_summary", "name": "Summary", "entity_slug": "thing",
                                "page_config": {"title": "Summary"},
                                "blocks": [{"field": "name", "label": "Name"}]}],
        "email_templates": [{"slug": "welcome", "name": "Welcome", "locale": "en",
                             "subject_template": "Hi ${name}", "body_html": "<p>Hi</p>"}],
        "portal_grants": [{"entity_slug": "thing", "portal_type": "customer",
                           "link_field": "owner", "can_read": True}],
        "approval_processes": [{"slug": "review", "name": "Review", "entity_slug": "thing",
                                "levels": [{"approvers": []}]}],
        "sla_policies": [{"slug": "response", "name": "Response", "entity_slug": "thing",
                          "targets": [{"metric": "resolution", "target_minutes": 60}]}],
        "business_hours": [{"name": "Standard", "timezone": "UTC"}],
        "kpis": [{"code": "thing_count", "name": "Thing Count", "source_type": "nql",
                  "nql_source": "FROM thing", "aggregate": "count"}],
    }


@pytest.fixture
def entity(db):
    ws = uuid.uuid4()
    EntityDefinition.objects.create(workspace_id=ws, slug="thing", name="Thing",
                                    plural_name="Things")
    return ws


@pytest.mark.django_db
def test_appliers_provision_every_section(entity):
    ws = entity
    out = appliers.apply_standard_sections(_manifest(), ws, None)
    assert all(len(out[k]) == 1 for k in out), out
    assert DocumentTemplate.objects.filter(workspace_id=ws, slug="dt_summary").exists()
    assert EmailTemplate.objects.filter(workspace_id=ws, slug="welcome", locale="en").exists()
    assert PortalEntityGrant.objects.filter(
        workspace_id=ws, entity_slug="thing", portal_type="customer").exists()
    assert ApprovalProcess.objects.filter(workspace_id=ws, slug="review").exists()
    assert SLAPolicy.objects.filter(workspace_id=ws, slug="response").exists()
    assert BusinessHours.objects.filter(workspace_id=ws, name="Standard").exists()
    assert KPIDefinition.objects.filter(workspace_id=ws, code="thing_count").exists()


@pytest.mark.django_db
def test_appliers_are_idempotent(entity):
    ws = entity
    appliers.apply_standard_sections(_manifest(), ws, None)
    second = appliers.apply_standard_sections(_manifest(), ws, None)
    assert all(len(second[k]) == 0 for k in second)   # nothing re-created
    assert DocumentTemplate.objects.filter(workspace_id=ws).count() == 1
    assert ApprovalProcess.objects.filter(workspace_id=ws).count() == 1
    assert KPIDefinition.objects.filter(workspace_id=ws).count() == 1


@pytest.mark.django_db
def test_approval_and_sla_skip_without_entity():
    ws = uuid.uuid4()   # no 'thing' entity in this workspace
    out = appliers.apply_standard_sections(_manifest(), ws, None)
    assert out["approval_processes"] == []   # entity binding missing → skipped
    assert out["sla_policies"] == []
    # entity-less sections still provision
    assert out["email_templates"] and out["business_hours"] and out["kpis"]


@pytest.mark.django_db
def test_install_records_extra_ids_and_summary():
    tpl = SolutionTemplate.objects.create(
        slug="std_demo", name="Std Demo", version="1.0.0", is_published=True,
        manifest=_manifest())
    ws = uuid.uuid4()
    inst = sol.install(template_id=tpl.id, workspace_id=ws, installed_by=None)
    assert inst.summary["document_templates"] == 1
    assert inst.summary["kpis"] == 1
    assert len(inst.created_extra_ids["approval_processes"]) == 1
    assert DocumentTemplate.objects.filter(workspace_id=ws).exists()
    assert InstalledSolution.objects.get(id=inst.id).created_extra_ids["business_hours"]


@pytest.mark.django_db
def test_validator_flags_bad_standard_sections():
    from apps.solution_templates.validators import validate_solution_manifest
    errs = validate_solution_manifest({
        "schema_version": 1,
        "portal_grants": [{"portal_type": "customer"}],          # missing entity_slug + link_field
        "approval_processes": [{"slug": "x"}],                    # missing entity_slug
        "business_hours": [{"timezone": "UTC"}],                  # missing name
        "kpis": [{"code": "Bad Code"}],                          # invalid slug/code
    })
    joined = " ".join(errs)
    assert "portal_grants" in joined and "link_field" in joined
    assert "approval_processes" in joined and "entity_slug" in joined
    assert "business_hours" in joined and "name" in joined
    assert "kpis" in joined
