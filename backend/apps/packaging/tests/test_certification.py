"""Platform certification: every shipped industry package still installs + uninstalls cleanly
through the package platform (preflight gate + authoritative installer)."""
import importlib
import uuid

import pytest

from apps.metadata.models import EntityDefinition
from apps.packaging import preflight
from apps.solution_templates import services as sol
from apps.solution_templates.models import InstalledSolution

# (app, seed-function) for each shipped solution package.
PACKAGES = [
    ("crm", "seed_crm_template"),
    ("hr", "seed_hr_template"),
    ("procurement", "seed_procurement_template"),
    ("projects", "seed_projects_template"),
    ("helpdesk", "seed_helpdesk_template"),
    ("manufacturing", "seed_manufacturing_template"),
    ("assets", "seed_assets_template"),
    ("payroll", "seed_payroll_template"),
    ("analytics", "seed_analytics_template"),
]


def _seed(app, fn):
    mod = importlib.import_module(f"apps.{app}.blueprint")
    return getattr(mod, fn)()


@pytest.mark.django_db
@pytest.mark.parametrize("app,fn", PACKAGES)
def test_shipped_package_preflights_clean(app, fn):
    tpl = _seed(app, fn)
    res = preflight.preflight(tpl.manifest, workspace_id=uuid.uuid4())
    assert res.ok, f"{app} preflight errors: {res.errors}"


@pytest.mark.django_db
@pytest.mark.parametrize("app,fn", PACKAGES)
def test_shipped_package_installs_and_uninstalls(app, fn):
    tpl = _seed(app, fn)
    ws = uuid.uuid4()

    installed = sol.install(template_id=tpl.id, workspace_id=ws, installed_by=None)
    assert installed.status == "active"
    # Each package provisions SOMETHING (metadata packages provision entities; native-heavy
    # packages like manufacturing/payroll/analytics provision roles + app + nav only).
    assert sum(installed.summary.values()) >= 1, installed.summary
    entity_count = EntityDefinition.objects.filter(workspace_id=ws).count()

    obj = sol.uninstall(installed_id=installed.id, workspace_id=ws, actor_id=None)
    assert obj.status == "disabled"
    # soft uninstall preserves entity definitions (data safety)
    assert EntityDefinition.objects.filter(workspace_id=ws).count() == entity_count


@pytest.mark.django_db
def test_all_nine_packages_coexist_in_one_workspace():
    """Install every shipped package into a single workspace — the platform must let them
    compose without hard conflicts (idempotent appliers; overlaps are warnings)."""
    ws = uuid.uuid4()
    for app, fn in PACKAGES:
        tpl = _seed(app, fn)
        installed = sol.install(template_id=tpl.id, workspace_id=ws, installed_by=None)
        assert installed.status == "active"
    assert InstalledSolution.objects.filter(workspace_id=ws, status="active").count() == len(
        PACKAGES)
