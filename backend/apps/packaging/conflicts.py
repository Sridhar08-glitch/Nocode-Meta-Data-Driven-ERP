"""
Install-time conflict detection.

Scans a manifest against the *live* configuration of a target workspace and reports objects
whose slug/name already exists: entities, applications/navigations, roles (RBAC), workflows,
reports, dashboards. These are classified as **warnings**, not hard errors, because every
applier in the platform is idempotent (it skips an object that already exists and never
modifies it) — so re-installing or installing an overlapping package is safe by design. The
report lets an operator *see* the overlap before committing.

A genuine hard block (missing dependency, version mismatch, conflicting package, missing
engine, incompatible core) is handled by :mod:`apps.packaging.dependencies` /
:mod:`apps.packaging.preflight`, not here.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConflictResult:
    entities: list = field(default_factory=list)
    applications: list = field(default_factory=list)
    navigations: list = field(default_factory=list)
    roles: list = field(default_factory=list)
    workflows: list = field(default_factory=list)
    reports: list = field(default_factory=list)
    dashboards: list = field(default_factory=list)

    def any(self) -> bool:
        return any((self.entities, self.applications, self.navigations, self.roles,
                    self.workflows, self.reports, self.dashboards))

    def warnings(self) -> list[str]:
        out = []
        for label, items in (("entity", self.entities), ("application", self.applications),
                             ("navigation", self.navigations), ("role", self.roles),
                             ("workflow", self.workflows), ("report", self.reports),
                             ("dashboard", self.dashboards)):
            for slug in items:
                out.append(f"{label} {slug!r} already exists in this workspace — "
                           f"it will be reused, not replaced")
        return out

    def as_dict(self) -> dict:
        return {
            "entities": self.entities, "applications": self.applications,
            "navigations": self.navigations, "roles": self.roles,
            "workflows": self.workflows, "reports": self.reports,
            "dashboards": self.dashboards,
        }


def _existing(model, workspace_id, field_name, values):
    if not values:
        return []
    present = set(model.objects.filter(
        workspace_id=workspace_id, **{f"{field_name}__in": list(values)}
    ).values_list(field_name, flat=True))
    return [v for v in values if v in present]


def detect(manifest, workspace_id) -> ConflictResult:
    from apps.metadata.models import EntityDefinition
    from apps.permissions.models import Role
    from apps.reporting.models import Dashboard, Report
    from apps.studio.models import Application, Navigation
    from apps.workflows.models import WorkflowDefinition

    m = manifest or {}

    def slugs(section):
        return [it.get("slug") for it in (m.get(section, []) or []) if it.get("slug")]

    def names(section, key="name"):
        return [it.get(key) for it in (m.get(section, []) or []) if it.get(key)]

    res = ConflictResult()
    res.entities = _existing(EntityDefinition, workspace_id, "slug", slugs("entities"))
    res.applications = _existing(Application, workspace_id, "slug", slugs("applications"))
    res.navigations = _existing(Navigation, workspace_id, "name", names("navigations"))
    res.roles = _existing(Role, workspace_id, "slug", slugs("roles"))
    res.workflows = _existing(WorkflowDefinition, workspace_id, "slug", slugs("workflows"))
    res.reports = _existing(Report, workspace_id, "slug", slugs("reports"))
    res.dashboards = _existing(Dashboard, workspace_id, "slug", slugs("dashboards"))
    return res
