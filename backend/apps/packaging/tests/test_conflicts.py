"""Conflict detection scans the live workspace and reports overlaps (warnings, not blocks)."""
import uuid

import pytest

from apps.metadata.models import EntityDefinition
from apps.packaging import conflicts
from apps.reporting.models import Report
from apps.workflows.models import WorkflowDefinition


@pytest.mark.django_db
def test_detects_existing_entities_workflows_reports():
    ws = uuid.uuid4()
    EntityDefinition.objects.create(workspace_id=ws, slug="customer", name="Customer",
                                    plural_name="Customers")
    WorkflowDefinition.objects.create(workspace_id=ws, slug="approve", name="Approve",
                                      trigger_type="record_created")
    Report.objects.create(workspace_id=ws, slug="aging", name="Aging", nql_ast={})

    manifest = {
        "entities": [{"slug": "customer"}, {"slug": "brand_new"}],
        "workflows": [{"slug": "approve"}],
        "reports": [{"slug": "aging"}, {"slug": "fresh"}],
    }
    res = conflicts.detect(manifest, ws)
    assert res.entities == ["customer"]
    assert res.workflows == ["approve"]
    assert res.reports == ["aging"]
    assert res.any()
    assert any("customer" in w for w in res.warnings())


@pytest.mark.django_db
def test_no_conflicts_on_clean_workspace():
    ws = uuid.uuid4()
    res = conflicts.detect({"entities": [{"slug": "x"}]}, ws)
    assert not res.any()
    assert res.warnings() == []


@pytest.mark.django_db
def test_conflicts_are_workspace_scoped():
    ws, other = uuid.uuid4(), uuid.uuid4()
    EntityDefinition.objects.create(workspace_id=other, slug="customer", name="Customer",
                                    plural_name="Customers")
    res = conflicts.detect({"entities": [{"slug": "customer"}]}, ws)
    assert res.entities == []   # belongs to a different workspace
