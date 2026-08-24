"""The preflight gate: structural + compatibility + dependency + conflict verdicts."""
import uuid

import pytest

from apps.packaging import preflight as pf
from apps.solution_templates.models import InstalledSolution


def _manifest(pkg=None, **sections):
    m = {"schema_version": 1}
    if pkg is not None:
        m["package"] = pkg
    m.update(sections)
    return m


@pytest.mark.django_db
def test_clean_manifest_is_ok():
    res = pf.preflight(_manifest(entities=[{"slug": "thing", "fields": []}]),
                       workspace_id=uuid.uuid4())
    assert res.ok
    assert res.errors == []
    assert res.plan["entities"] == 1


@pytest.mark.django_db
def test_blocks_on_incompatible_core_version():
    res = pf.preflight(_manifest({"slug": "p", "version": "1.0.0",
                                  "min_core_version": "99.0.0"}),
                       workspace_id=uuid.uuid4())
    assert not res.ok
    assert any("core >=" in e for e in res.errors)


@pytest.mark.django_db
def test_blocks_on_missing_required_engine_and_capability():
    res = pf.preflight(_manifest({"slug": "p", "version": "1.0.0",
                                  "requires_engines": ["ghost_engine"],
                                  "requires_capabilities": ["telepathy"]}),
                       workspace_id=uuid.uuid4())
    # unknown engine/capability fail validation first (hard error either way)
    assert not res.ok
    assert any("ghost_engine" in e for e in res.errors)


@pytest.mark.django_db
def test_blocks_on_missing_required_package():
    res = pf.preflight(_manifest({"slug": "pos", "version": "1.0.0",
                                  "requires_packages": [{"slug": "inventory",
                                                         "version": ">=1.0.0"}]}),
                       workspace_id=uuid.uuid4())
    assert not res.ok
    assert any("inventory" in e for e in res.errors)


@pytest.mark.django_db
def test_passes_when_required_package_installed():
    ws = uuid.uuid4()
    InstalledSolution.objects.create(workspace_id=ws, solution_slug="inventory",
                                     installed_version="1.2.0", status="active")
    res = pf.preflight(_manifest({"slug": "pos", "version": "1.0.0",
                                  "requires_packages": [{"slug": "inventory",
                                                         "version": ">=1.0.0"}]}),
                       workspace_id=ws)
    assert res.ok
    assert res.dependency["satisfied_required"][0]["slug"] == "inventory"


@pytest.mark.django_db
def test_blocks_on_conflicting_package():
    ws = uuid.uuid4()
    InstalledSolution.objects.create(workspace_id=ws, solution_slug="legacy_crm",
                                     installed_version="3.0.0", status="active")
    res = pf.preflight(_manifest({"slug": "crm", "version": "1.0.0",
                                  "conflicts_packages": [{"slug": "legacy_crm"}]}),
                       workspace_id=ws)
    assert not res.ok
    assert any("conflicting" in e for e in res.errors)


@pytest.mark.django_db
def test_object_conflicts_are_warnings_not_errors():
    from apps.metadata.models import EntityDefinition
    ws = uuid.uuid4()
    EntityDefinition.objects.create(workspace_id=ws, slug="customer", name="Customer",
                                    plural_name="Customers")
    res = pf.preflight(_manifest(entities=[{"slug": "customer", "fields": []}]),
                       workspace_id=ws)
    assert res.ok                                    # duplicate entity does NOT block
    assert any("customer" in w for w in res.warnings)


@pytest.mark.django_db
def test_requirement_errors_only_skips_structure_and_conflicts():
    # a structurally-questionable manifest with a satisfiable package block → no hard req errors
    errs = pf.requirement_errors(_manifest({"slug": "p", "version": "1.0.0"}),
                                 workspace_id=uuid.uuid4())
    assert errs == []
