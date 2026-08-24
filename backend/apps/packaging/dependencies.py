"""
Package dependency resolution.

Given a package's requirements and the set of packages currently installed in a workspace,
decide whether its declared ``requires_packages`` / ``conflicts_packages`` / ``optional_packages``
are satisfied. Version constraints are matched with :mod:`apps.packaging.semver`.

``installed`` is a mapping ``{slug: version}``. :func:`installed_packages` builds it from the
active ``InstalledSolution`` rows of a workspace (the registry's source of truth).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import semver
from .requirements import PackageRequirements


@dataclass
class DependencyResult:
    ok: bool = True
    missing_required: list = field(default_factory=list)   # [{slug, constraint, reason}]
    version_conflicts: list = field(default_factory=list)  # [{slug, installed, constraint}]
    active_conflicts: list = field(default_factory=list)   # [{slug, installed, constraint}]
    satisfied_required: list = field(default_factory=list)
    optional_present: list = field(default_factory=list)
    optional_absent: list = field(default_factory=list)

    def errors(self) -> list[str]:
        out = []
        for m in self.missing_required:
            out.append(f"required package {m['slug']!r} ({m['constraint']}) is not installed")
        for v in self.version_conflicts:
            out.append(
                f"required package {v['slug']!r} is installed at {v['installed']} which does "
                f"not satisfy {v['constraint']}")
        for c in self.active_conflicts:
            out.append(
                f"conflicting package {c['slug']!r} is installed (at {c['installed']})")
        return out

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "missing_required": self.missing_required,
            "version_conflicts": self.version_conflicts,
            "active_conflicts": self.active_conflicts,
            "satisfied_required": self.satisfied_required,
            "optional_present": self.optional_present,
            "optional_absent": self.optional_absent,
        }


def installed_packages(workspace_id) -> dict:
    """``{slug: version}`` for the workspace's active installed solutions."""
    from apps.solution_templates.models import InstalledSolution
    rows = InstalledSolution.objects.filter(
        workspace_id=workspace_id, status="active").values("solution_slug", "installed_version")
    result: dict = {}
    for r in rows:
        slug = r["solution_slug"]
        ver = r["installed_version"] or "0.0.0"
        # keep the highest installed version if a slug appears more than once
        if slug not in result or (semver.is_valid(ver) and semver.is_valid(result[slug])
                                  and semver.compare(ver, result[slug]) > 0):
            result[slug] = ver
    return result


def resolve(requirements: PackageRequirements, installed: dict) -> DependencyResult:
    installed = installed or {}
    res = DependencyResult()

    for ref in requirements.requires_packages:
        ver = installed.get(ref.slug)
        if ver is None:
            res.missing_required.append({"slug": ref.slug, "constraint": ref.version,
                                         "reason": "not_installed"})
            continue
        if not _ver_ok(ver, ref.version):
            res.version_conflicts.append(
                {"slug": ref.slug, "installed": ver, "constraint": ref.version})
        else:
            res.satisfied_required.append({"slug": ref.slug, "installed": ver,
                                           "constraint": ref.version})

    for ref in requirements.conflicts_packages:
        ver = installed.get(ref.slug)
        if ver is not None and _ver_ok(ver, ref.version):
            res.active_conflicts.append(
                {"slug": ref.slug, "installed": ver, "constraint": ref.version})

    for ref in requirements.optional_packages:
        ver = installed.get(ref.slug)
        if ver is not None and _ver_ok(ver, ref.version):
            res.optional_present.append({"slug": ref.slug, "installed": ver})
        else:
            res.optional_absent.append({"slug": ref.slug, "constraint": ref.version})

    res.ok = not (res.missing_required or res.version_conflicts or res.active_conflicts)
    return res


def _ver_ok(version: str, constraint: str) -> bool:
    try:
        return semver.satisfies(version, constraint)
    except semver.InvalidVersionError:
        # An unparseable installed version can't be proven to satisfy a real constraint.
        return constraint in ("", "*", "any")
