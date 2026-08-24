"""
Pre-install preflight — the single gate every package install passes through.

It composes the platform's checks into one structured verdict:

  1. manifest structure        (reuses solution_templates / marketplace validators)
  2. package block validity    (requirements.validate)
  3. core-version compatibility (min/max_core_version vs CORE_VERSION)
  4. required engines present   (capabilities.missing_engines)
  5. required capabilities present
  6. package dependencies       (required present + version-ok, no active conflict)
  7. duplicate/object conflicts (warnings — appliers are idempotent)

``ok`` is True iff there are no hard errors. Conflicts and absent-optional dependencies are
surfaced as *warnings* so a re-install or an overlapping install is never blocked.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import capabilities, conflicts, dependencies, requirements, semver


@dataclass
class PreflightResult:
    ok: bool = True
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    requirements: dict = field(default_factory=dict)
    dependency: dict = field(default_factory=dict)
    conflicts: dict = field(default_factory=dict)
    plan: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "ok": self.ok, "errors": self.errors, "warnings": self.warnings,
            "requirements": self.requirements, "dependency": self.dependency,
            "conflicts": self.conflicts, "plan": self.plan,
        }


_PLAN_KEYS = ["entities", "forms", "views", "workflows", "rules", "reports",
              "notification_templates", "roles", "dashboards", "applications",
              "navigations", "home_layouts", "document_templates", "email_templates",
              "portal_grants", "approval_processes", "sla_policies", "business_hours", "kpis"]


def _plan(manifest) -> dict:
    m = manifest or {}
    return {k: len(m.get(k, []) or []) for k in _PLAN_KEYS}


def preflight(manifest, *, workspace_id=None, installed=None,
              core_version=None) -> PreflightResult:
    res = PreflightResult()
    core_version = core_version or capabilities.CORE_VERSION

    # 1 + 2 — manifest structure + package block.
    from apps.solution_templates.validators import validate_solution_manifest
    res.errors.extend(validate_solution_manifest(manifest))
    res.errors.extend(requirements.validate(manifest))

    req = requirements.extract(manifest)
    res.requirements = req.as_dict()
    res.requirements["present"] = req.present
    res.plan = _plan(manifest)

    # 3 — core-version compatibility.
    if req.min_core_version and semver.is_valid(req.min_core_version) and \
            semver.compare(core_version, req.min_core_version) < 0:
        res.errors.append(f"package requires core >= {req.min_core_version}; "
                          f"this core is {core_version}")
    if req.max_core_version and semver.is_valid(req.max_core_version) and \
            semver.compare(core_version, req.max_core_version) > 0:
        res.errors.append(f"package requires core <= {req.max_core_version}; "
                          f"this core is {core_version}")

    # 4 + 5 — required engines + capabilities.
    for eng in capabilities.missing_engines(req.requires_engines):
        res.errors.append(f"required engine {eng!r} is not available in this core")
    for cap in capabilities.missing_capabilities(req.requires_capabilities):
        res.errors.append(f"required capability {cap!r} is not available in this core")

    # 6 — package dependencies (only meaningful when we know what's installed).
    if installed is None and workspace_id is not None:
        installed = dependencies.installed_packages(workspace_id)
    dep = dependencies.resolve(req, installed or {})
    res.dependency = dep.as_dict()
    res.errors.extend(dep.errors())
    for opt in dep.optional_absent:
        res.warnings.append(
            f"optional package {opt['slug']!r} ({opt['constraint']}) is not installed")

    # 7 — object conflicts against the live workspace (warnings only).
    if workspace_id is not None:
        conf = conflicts.detect(manifest, workspace_id)
        res.conflicts = conf.as_dict()
        res.warnings.extend(conf.warnings())

    res.ok = not res.errors
    return res


def requirement_errors(manifest, *, workspace_id=None, installed=None,
                       core_version=None) -> list[str]:
    """Only the HARD requirement errors — package-block validity + core-version + required
    engines/capabilities + package dependencies — WITHOUT structural manifest re-validation
    or conflict warnings. For surfaces that run their own manifest validator (e.g. the
    marketplace) but still need the platform's dependency/compatibility gate."""
    core_version = core_version or capabilities.CORE_VERSION
    errors = list(requirements.validate(manifest))
    req = requirements.extract(manifest)
    if req.min_core_version and semver.is_valid(req.min_core_version) and \
            semver.compare(core_version, req.min_core_version) < 0:
        errors.append(f"package requires core >= {req.min_core_version}; "
                      f"this core is {core_version}")
    if req.max_core_version and semver.is_valid(req.max_core_version) and \
            semver.compare(core_version, req.max_core_version) > 0:
        errors.append(f"package requires core <= {req.max_core_version}; "
                      f"this core is {core_version}")
    for eng in capabilities.missing_engines(req.requires_engines):
        errors.append(f"required engine {eng!r} is not available in this core")
    for cap in capabilities.missing_capabilities(req.requires_capabilities):
        errors.append(f"required capability {cap!r} is not available in this core")
    if installed is None and workspace_id is not None:
        installed = dependencies.installed_packages(workspace_id)
    errors.extend(dependencies.resolve(req, installed or {}).errors())
    return errors
