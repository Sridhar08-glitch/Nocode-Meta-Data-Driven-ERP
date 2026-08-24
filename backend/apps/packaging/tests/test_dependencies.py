"""Package dependency resolution against the installed set."""
import uuid

import pytest

from apps.packaging import dependencies as dep
from apps.packaging.requirements import PackageRef, PackageRequirements
from apps.solution_templates.models import InstalledSolution


def _req(**over):
    r = PackageRequirements(slug="demo", present=True)
    for k, v in over.items():
        setattr(r, k, v)
    return r


def test_required_present_and_version_ok():
    r = _req(requires_packages=[PackageRef("inventory", ">=1.0.0")])
    res = dep.resolve(r, {"inventory": "1.2.0"})
    assert res.ok
    assert res.satisfied_required[0]["slug"] == "inventory"


def test_required_missing_blocks():
    r = _req(requires_packages=[PackageRef("inventory", ">=1.0.0")])
    res = dep.resolve(r, {})
    assert not res.ok
    assert res.missing_required[0]["slug"] == "inventory"
    assert "not installed" in res.errors()[0]


def test_required_version_mismatch_blocks():
    r = _req(requires_packages=[PackageRef("inventory", ">=2.0.0")])
    res = dep.resolve(r, {"inventory": "1.2.0"})
    assert not res.ok
    assert res.version_conflicts[0]["installed"] == "1.2.0"
    assert "does not satisfy" in res.errors()[0]


def test_conflict_present_blocks():
    r = _req(conflicts_packages=[PackageRef("legacy_crm", "*")])
    res = dep.resolve(r, {"legacy_crm": "3.0.0"})
    assert not res.ok
    assert res.active_conflicts[0]["slug"] == "legacy_crm"


def test_conflict_absent_is_fine():
    r = _req(conflicts_packages=[PackageRef("legacy_crm", "*")])
    assert dep.resolve(r, {"crm": "1.0.0"}).ok


def test_optional_present_and_absent_are_advisory():
    r = _req(optional_packages=[PackageRef("analytics", "*"), PackageRef("search", "*")])
    res = dep.resolve(r, {"analytics": "1.0.0"})
    assert res.ok                       # optional never blocks
    assert res.optional_present[0]["slug"] == "analytics"
    assert res.optional_absent[0]["slug"] == "search"


@pytest.mark.django_db
def test_installed_packages_reads_active_only_and_keeps_highest():
    ws = uuid.uuid4()
    InstalledSolution.objects.create(workspace_id=ws, solution_slug="inventory",
                                     installed_version="1.0.0", status="active")
    InstalledSolution.objects.create(workspace_id=ws, solution_slug="inventory",
                                     installed_version="1.4.0", status="active")
    InstalledSolution.objects.create(workspace_id=ws, solution_slug="crm",
                                     installed_version="1.0.0", status="disabled")
    other = uuid.uuid4()
    InstalledSolution.objects.create(workspace_id=other, solution_slug="hr",
                                     installed_version="1.0.0", status="active")

    installed = dep.installed_packages(ws)
    assert installed == {"inventory": "1.4.0"}   # disabled excluded, highest kept, ws-scoped
