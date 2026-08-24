"""
Solution Template Framework service (Phase P2.4A).

Browse / preview / install / uninstall full end-to-end solutions. ``install`` applies the
extended manifest in ONE ``transaction.atomic()`` — reusing the marketplace appliers for
entities/workflows/rules/reports/notification_templates and this app's appliers for forms/
views/roles+permissions/dashboards/studio — records what it provisioned on an
``InstalledSolution``, emits a domain event, and captures a Config-VCS commit. ``uninstall``
is soft by default: it deactivates workflows/rules/applications but NEVER deletes data.
"""
from __future__ import annotations

import uuid

from django.db import transaction

from apps.eventstore.events import DomainEventData, DomainEventFactory
from apps.marketplace import services as mk

from . import appliers
from .models import InstalledSolution, SolutionTemplate
from .validators import validate_solution_manifest


class SolutionTemplateError(Exception):  # noqa: N818 — domain error
    pass


def _emit(workspace_id, aggregate_id, event_type, payload, actor_id):
    from apps.eventstore.models import DomainEvent
    agg = uuid.UUID(str(aggregate_id))
    version = DomainEvent.objects.filter(
        aggregate_id=agg, aggregate_type="installed_solution").count() + 1
    DomainEventFactory.persist_one(DomainEventData(
        event_type=event_type, workspace_id=uuid.UUID(str(workspace_id)),
        aggregate_type="installed_solution", aggregate_id=agg, version=version,
        payload=payload, actor_id=uuid.UUID(str(actor_id)) if actor_id else uuid.UUID(int=0)))


# ── browse ───────────────────────────────────────────────────────────────────
def list_templates(*, category=None, search=None):
    qs = SolutionTemplate.objects.filter(is_published=True)
    if category:
        qs = qs.filter(category=category)
    if search:
        qs = qs.filter(name__icontains=search)
    return list(qs.order_by("-install_count", "name"))


def get_template(template_id) -> SolutionTemplate:
    tpl = SolutionTemplate.objects.filter(id=template_id).first()
    if tpl is None:
        raise SolutionTemplateError("Solution template not found.")
    return tpl


def _summary(manifest) -> dict:
    m = manifest or {}
    keys = ["entities", "forms", "views", "workflows", "rules", "reports",
            "notification_templates", "roles", "dashboards", "applications",
            "navigations", "home_layouts", "document_templates", "email_templates",
            "portal_grants", "approval_processes", "sla_policies", "business_hours", "kpis"]
    return {k: len(m.get(k, []) or []) for k in keys}


def preview(template: SolutionTemplate) -> dict:
    errors = validate_solution_manifest(template.manifest)
    return {
        "id": str(template.id), "slug": template.slug, "name": template.name,
        "category": template.category, "version": template.version,
        "valid": not errors, "errors": errors,
        "summary": _summary(template.manifest), "manifest": template.manifest or {},
    }


# ── install ──────────────────────────────────────────────────────────────────
def _apply_all(manifest, workspace_id, actor_id) -> dict:
    """Apply every manifest section idempotently through the existing appliers (reused, never
    duplicated). Returns the created-id lists. Used by both first install and upgrade — so
    there is exactly one provisioning routine."""
    entity_ids = appliers.apply_entities(manifest, workspace_id, actor_id)
    form_ids = appliers.apply_forms(manifest, workspace_id, actor_id)
    view_ids = appliers.apply_views(manifest, workspace_id, actor_id)
    new_items = appliers.prune_existing(manifest, workspace_id)
    workflow_ids = mk._apply_workflows(new_items, workspace_id)
    rule_ids = mk._apply_rules(new_items, workspace_id)
    report_ids = mk._apply_reports(new_items, workspace_id)
    mk._apply_notification_templates(manifest, workspace_id)
    role_ids = appliers.apply_roles(manifest, workspace_id)
    dashboard_ids = appliers.apply_dashboards(manifest, workspace_id)
    studio = appliers.apply_studio(manifest, workspace_id, actor_id)
    # Standard manifest sections backed by existing Core engines (Phase P3.1A).
    extra = appliers.apply_standard_sections(manifest, workspace_id, actor_id)

    # Accounting auto-provisioning (P2.15 Blocker 1): every installed solution gets a
    # ready-to-post chart of accounts + account mappings + default posting rules. Idempotent.
    from apps.ledger.provisioning import provision_accounting
    provision_accounting(workspace_id, actor_id=actor_id)

    return {
        "entity_ids": entity_ids, "form_ids": form_ids, "view_ids": view_ids,
        "workflow_ids": workflow_ids, "rule_ids": rule_ids, "report_ids": report_ids,
        "role_ids": role_ids, "dashboard_ids": dashboard_ids,
        "application_ids": studio["application_ids"],
        "navigation_ids": studio["navigation_ids"],
        "home_layout_ids": studio["home_layout_ids"],
        "extra_ids": extra,
    }


def _preflight_or_raise(manifest, *, workspace_id):
    """Run the package-platform preflight gate; raise on any hard error. Conflicts/absent
    optional deps are warnings and never block (the appliers are idempotent)."""
    from apps.packaging.preflight import preflight
    result = preflight(manifest, workspace_id=workspace_id)
    if not result.ok:
        raise SolutionTemplateError("Preflight failed: " + "; ".join(result.errors))
    return result


def _install_manifest(*, manifest, workspace_id, installed_by, solution_slug,
                      solution_name, installed_version="1.0.0",
                      solution_template_id=None) -> InstalledSolution:
    """THE authoritative provisioning path — used by both catalog install and the Create
    Solution Wizard. Applies the whole manifest in one transaction (reusing marketplace +
    this app's appliers), records an ``InstalledSolution``, emits an event, and captures a
    Config-VCS commit. There is no other install path."""
    with transaction.atomic():
        ids = _apply_all(manifest, workspace_id, installed_by)
        installed = InstalledSolution.objects.create(
            workspace_id=workspace_id, solution_template_id=solution_template_id,
            solution_slug=solution_slug, solution_name=solution_name,
            installed_version=installed_version, status="active",
            created_entity_ids=ids["entity_ids"], created_form_ids=ids["form_ids"],
            created_view_ids=ids["view_ids"], created_workflow_ids=ids["workflow_ids"],
            created_rule_ids=ids["rule_ids"], created_report_ids=ids["report_ids"],
            created_role_ids=ids["role_ids"], created_dashboard_ids=ids["dashboard_ids"],
            created_application_ids=ids["application_ids"],
            created_navigation_ids=ids["navigation_ids"],
            created_home_layout_ids=ids["home_layout_ids"],
            created_extra_ids=ids["extra_ids"],
            installed_manifest=manifest, applied_migrations=[],
            summary=_summary(manifest), created_by=installed_by)

    _emit(workspace_id, installed.id, "solution_template.installed",
          {"solution_slug": solution_slug, "summary": installed.summary}, installed_by)

    # Capture in Config-VCS history (best-effort; never breaks the install).
    try:
        from apps.config_vcs import services as cvcs
        cvcs.commit(workspace_id=workspace_id,
                    message=f"Installed solution: {solution_slug}", author_id=installed_by)
    except Exception:  # noqa: BLE001
        pass

    return installed


def install(*, template_id, workspace_id, installed_by) -> InstalledSolution:
    tpl = get_template(template_id)
    if not tpl.is_published:
        raise SolutionTemplateError("Solution template is not published.")
    _preflight_or_raise(tpl.manifest, workspace_id=workspace_id)

    installed = _install_manifest(
        manifest=tpl.manifest, workspace_id=workspace_id, installed_by=installed_by,
        solution_slug=tpl.slug, solution_name=tpl.name,
        installed_version=tpl.version, solution_template_id=tpl.id)
    SolutionTemplate.objects.filter(id=tpl.id).update(install_count=tpl.install_count + 1)
    return installed


# ── upgrade / rollback / enable ──────────────────────────────────────────────
def upgrade(*, installed_id, workspace_id, actor_id, to_template_id=None,
            manifest=None, version=None) -> InstalledSolution:
    """Additively upgrade an installed solution to a new manifest version: provisions new
    entities/fields/objects (never removes existing ones), runs any pending declarative
    package migrations, and records the new version. The prior manifest is retained so the
    upgrade can be rolled back. Schema additions are never auto-removed (data safety)."""
    from apps.packaging import package_migrations as pm

    obj = get_installed(installed_id=installed_id, workspace_id=workspace_id)
    if to_template_id is not None:
        tpl = get_template(to_template_id)
        manifest, version = tpl.manifest, (version or tpl.version)
    if manifest is None:
        raise SolutionTemplateError("upgrade requires a target template or manifest.")
    version = version or obj.installed_version

    _preflight_or_raise(manifest, workspace_id=workspace_id)

    old_manifest = obj.installed_manifest or {}
    old_version = obj.installed_version
    new_migrations = (manifest.get("package", {}) or {}).get("migrations", [])

    with transaction.atomic():
        _apply_all(manifest, workspace_id, actor_id)
        applied = pm.run_pending(
            new_migrations, workspace_id=workspace_id, from_version=old_version,
            actor_id=actor_id, already_applied=obj.applied_migrations)
        obj.previous_manifest = old_manifest
        obj.installed_manifest = manifest
        obj.installed_version = version
        obj.applied_migrations = list(obj.applied_migrations or []) + applied
        obj.status = "active"
        obj.summary = _summary(manifest)
        obj.save(update_fields=["previous_manifest", "installed_manifest", "installed_version",
                                "applied_migrations", "status", "summary", "updated_at"])

    _emit(workspace_id, obj.id, "solution_template.upgraded",
          {"solution_slug": obj.solution_slug, "from": old_version, "to": version,
           "migrations_applied": applied}, actor_id)
    return obj


def rollback(*, installed_id, workspace_id, actor_id) -> InstalledSolution:
    """Restore the previously-installed manifest version pointer. Schema additions made by the
    newer version are NOT undone (data safety) — mirroring the marketplace contract."""
    from apps.packaging import requirements as rq

    obj = get_installed(installed_id=installed_id, workspace_id=workspace_id)
    prev = obj.previous_manifest or {}
    if not prev:
        raise SolutionTemplateError("No previous version to roll back to.")
    prev_version = rq.extract(prev).version if rq.extract(prev).present else obj.installed_version

    with transaction.atomic():
        obj.installed_manifest = prev
        obj.previous_manifest = {}
        obj.installed_version = prev_version
        obj.status = "active"
        obj.summary = _summary(prev)
        obj.save(update_fields=["installed_manifest", "previous_manifest", "installed_version",
                                "status", "summary", "updated_at"])
    _emit(workspace_id, obj.id, "solution_template.rolled_back",
          {"solution_slug": obj.solution_slug, "to": prev_version}, actor_id)
    return obj


def enable(*, installed_id, workspace_id, actor_id) -> InstalledSolution:
    """Re-activate a soft-uninstalled solution: un-archive its workflows, re-activate its
    rules, re-publish its applications, and mark it active. The inverse of soft uninstall."""
    from apps.rules.models import BusinessRule
    from apps.studio.models import Application
    from apps.workflows.models import WorkflowDefinition

    obj = get_installed(installed_id=installed_id, workspace_id=workspace_id)
    if obj.status == "active":
        return obj
    with transaction.atomic():
        WorkflowDefinition.objects.filter(
            workspace_id=workspace_id, id__in=obj.created_workflow_ids).update(status="active")
        BusinessRule.objects.filter(
            workspace_id=workspace_id, id__in=obj.created_rule_ids).update(is_active=True)
        Application.objects.filter(
            workspace_id=workspace_id, id__in=obj.created_application_ids).update(
                is_published=True, is_active=True)
        from apps.metadata.models import EntityDefinition
        EntityDefinition.objects.filter(
            workspace_id=workspace_id, id__in=obj.created_entity_ids).update(is_active=True)
        obj.status = "active"
        obj.save(update_fields=["status", "updated_at"])
    _emit(workspace_id, obj.id, "solution_template.enabled",
          {"solution_slug": obj.solution_slug}, actor_id)
    return obj


# ── installed + uninstall ────────────────────────────────────────────────────
def list_installed(*, workspace_id):
    return list(InstalledSolution.objects.filter(
        workspace_id=workspace_id).order_by("-created_at"))


def get_installed(*, installed_id, workspace_id) -> InstalledSolution:
    obj = InstalledSolution.objects.filter(
        id=installed_id, workspace_id=workspace_id).first()
    if obj is None:
        raise SolutionTemplateError("Installed solution not found.")
    return obj


def uninstall(*, installed_id, workspace_id, actor_id, hard=False) -> InstalledSolution:
    """Soft by default: archive workflows, deactivate rules, unpublish applications.
    Data (entities/records) is ALWAYS preserved. ``hard`` additionally deactivates the
    solution's entity definitions (records remain)."""
    obj = get_installed(installed_id=installed_id, workspace_id=workspace_id)
    if obj.status == "disabled":
        return obj

    from apps.rules.models import BusinessRule
    from apps.studio.models import Application
    from apps.workflows.models import WorkflowDefinition

    WorkflowDefinition.objects.filter(
        workspace_id=workspace_id, id__in=obj.created_workflow_ids).update(status="archived")
    BusinessRule.objects.filter(
        workspace_id=workspace_id, id__in=obj.created_rule_ids).update(is_active=False)
    Application.objects.filter(
        workspace_id=workspace_id, id__in=obj.created_application_ids).update(
            is_published=False, is_active=False)
    if hard:
        from apps.metadata.models import EntityDefinition
        EntityDefinition.objects.filter(
            workspace_id=workspace_id, id__in=obj.created_entity_ids).update(is_active=False)

    obj.status = "disabled"
    obj.save(update_fields=["status", "updated_at"])
    _emit(workspace_id, obj.id, "solution_template.uninstalled",
          {"solution_slug": obj.solution_slug, "hard": hard}, actor_id)
    return obj
