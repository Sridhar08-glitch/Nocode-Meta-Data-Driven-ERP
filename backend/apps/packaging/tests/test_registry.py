"""Package registry — catalog description, installed view + upgrade detection, matrix."""
import uuid

import pytest

from apps.packaging import registry
from apps.solution_templates.models import InstalledSolution, SolutionTemplate


@pytest.mark.django_db
def test_describe_template_reads_package_block():
    tpl = SolutionTemplate.objects.create(
        slug="pos", name="POS", version="1.2.0", is_published=True, publisher="Sridhar ERP",
        manifest={"schema_version": 1, "package": {
            "slug": "pos", "name": "Point of Sale", "version": "1.2.0", "author": "Acme",
            "min_core_version": "2.0.0",
            "requires_packages": [{"slug": "inventory", "version": ">=1.0.0"}],
            "requires_engines": ["accounting"], "provides_capabilities": ["pos"]}})
    rec = registry.describe_template(tpl)
    assert rec["slug"] == "pos"
    assert rec["author"] == "Acme"
    assert rec["dependencies"]["requires_packages"][0]["slug"] == "inventory"
    assert rec["requires_engines"] == ["accounting"]
    assert rec["provides_capabilities"] == ["pos"]
    assert rec["compatible_core_versions"].startswith(">=2.0.0")


@pytest.mark.django_db
def test_catalog_lists_published_only():
    SolutionTemplate.objects.create(slug="a", name="A", is_published=True,
                                    manifest={"schema_version": 1})
    SolutionTemplate.objects.create(slug="b", name="B", is_published=False,
                                    manifest={"schema_version": 1})
    slugs = {r["slug"] for r in registry.list_catalog()}
    assert "a" in slugs and "b" not in slugs


@pytest.mark.django_db
def test_installed_view_detects_upgrade_available():
    ws = uuid.uuid4()
    SolutionTemplate.objects.create(slug="demo_crm", name="Demo CRM", version="2.0.0",
                                    is_published=True, manifest={"schema_version": 1})
    InstalledSolution.objects.create(workspace_id=ws, solution_slug="demo_crm",
                                     solution_name="Demo CRM", installed_version="1.0.0",
                                     status="active")
    rows = registry.list_installed(workspace_id=ws)
    assert rows[0]["upgrade_available"] is True
    assert rows[0]["latest_version"] == "2.0.0"


@pytest.mark.django_db
def test_dependency_matrix_exposes_declared_deps():
    SolutionTemplate.objects.create(
        slug="pos", name="POS", version="1.0.0", is_published=True,
        manifest={"schema_version": 1, "package": {
            "slug": "pos", "version": "1.0.0",
            "requires_packages": [{"slug": "inventory", "version": ">=1.0.0"}],
            "conflicts_packages": [{"slug": "legacy"}]}})
    matrix = registry.dependency_matrix()
    row = next(r for r in matrix if r["slug"] == "pos")
    assert row["requires_packages"][0]["slug"] == "inventory"
    assert row["conflicts_packages"][0]["slug"] == "legacy"


@pytest.mark.django_db
def test_core_reports_version_and_available_engines():
    core = registry.core()
    assert core["core_version"]
    assert core["engines"]["accounting"]["available"] is True
    assert core["capabilities"]["workflows"]["available"] is True
