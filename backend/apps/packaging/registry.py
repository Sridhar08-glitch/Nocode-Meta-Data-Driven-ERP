"""
Package registry — the single read surface over the package catalog and what is installed.

Catalog rows live in ``solution_templates.SolutionTemplate`` (global); per-workspace installs
in ``solution_templates.InstalledSolution``. The registry derives each package's identity and
compatibility from the manifest ``package`` block (falling back to the template's own columns),
so every package exposes: name, slug, version, author, dependencies, capabilities, upgrade
path, installed version, and compatible core versions.
"""
from __future__ import annotations

from . import capabilities, requirements, semver


def describe_template(template) -> dict:
    """Registry record for a catalog template (independent of any workspace)."""
    req = requirements.extract(template.manifest)
    compatible = _compatible_core_range(req)
    return {
        "slug": req.slug or template.slug,
        "name": req.name or template.name,
        "version": template.version or req.version,
        "author": req.author or template.publisher or "",
        "category": template.category,
        "description": req.description or template.description,
        "is_system": template.is_system,
        "is_published": template.is_published,
        "install_count": template.install_count,
        "dependencies": {
            "requires_packages": [r.__dict__ for r in req.requires_packages],
            "optional_packages": [r.__dict__ for r in req.optional_packages],
            "conflicts_packages": [r.__dict__ for r in req.conflicts_packages],
        },
        "requires_engines": req.requires_engines,
        "requires_capabilities": req.requires_capabilities,
        "provides_capabilities": req.provides_capabilities,
        "compatible_core_versions": compatible,
        "min_core_version": req.min_core_version,
        "max_core_version": req.max_core_version,
        "has_migrations": bool(req.migrations),
        "template_id": str(template.id),
    }


def _compatible_core_range(req) -> str:
    lo = req.min_core_version or "0.0.0"
    hi = req.max_core_version or "*"
    return f">={lo}" + (f",<={hi}" if hi != "*" else "")


def list_catalog(*, category=None, search=None) -> list[dict]:
    from apps.solution_templates.models import SolutionTemplate
    qs = SolutionTemplate.objects.filter(is_published=True)
    if category:
        qs = qs.filter(category=category)
    if search:
        qs = qs.filter(name__icontains=search)
    return [describe_template(t) for t in qs.order_by("-install_count", "name")]


def _latest_catalog_version(slug):
    from apps.solution_templates.models import SolutionTemplate
    rows = SolutionTemplate.objects.filter(slug=slug, is_published=True).values_list(
        "version", flat=True)
    return semver.max_version([v for v in rows if v]) if rows else None


def list_installed(*, workspace_id) -> list[dict]:
    from apps.solution_templates.models import InstalledSolution
    out = []
    for inst in InstalledSolution.objects.filter(
            workspace_id=workspace_id).order_by("-created_at"):
        latest = _latest_catalog_version(inst.solution_slug)
        upgrade = bool(
            latest and inst.installed_version
            and semver.is_valid(latest) and semver.is_valid(inst.installed_version)
            and semver.compare(latest, inst.installed_version) > 0)
        out.append({
            "installed_id": str(inst.id),
            "slug": inst.solution_slug,
            "name": inst.solution_name,
            "installed_version": inst.installed_version,
            "status": inst.status,
            "latest_version": latest,
            "upgrade_available": upgrade,
            "applied_migrations": list(getattr(inst, "applied_migrations", []) or []),
            "summary": inst.summary,
        })
    return out


def installed_map(*, workspace_id) -> dict:
    from .dependencies import installed_packages
    return installed_packages(workspace_id)


def core() -> dict:
    return {
        "core_version": capabilities.CORE_VERSION,
        "engines": capabilities.list_engines(),
        "capabilities": capabilities.list_capabilities(),
    }


def dependency_matrix() -> list[dict]:
    """For every published catalog package, its declared package dependencies + conflicts —
    the data backing PACKAGE_DEPENDENCY_MATRIX.md."""
    rows = []
    for rec in list_catalog():
        rows.append({
            "slug": rec["slug"], "name": rec["name"], "version": rec["version"],
            "requires_packages": rec["dependencies"]["requires_packages"],
            "optional_packages": rec["dependencies"]["optional_packages"],
            "conflicts_packages": rec["dependencies"]["conflicts_packages"],
            "requires_engines": rec["requires_engines"],
            "requires_capabilities": rec["requires_capabilities"],
            "provides_capabilities": rec["provides_capabilities"],
            "compatible_core_versions": rec["compatible_core_versions"],
        })
    return rows
