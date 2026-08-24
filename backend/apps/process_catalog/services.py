"""
Process-catalog service (Phase 1.34).

Browse/preview published blueprints and install one into a workspace. Install validates
the manifest and applies it via the marketplace manifest applier (entities + workflows +
rules + reports + notification templates) in a single transaction, then records a Config-VCS
commit so the change is captured in config history (Draft→Publish).
"""
from __future__ import annotations

from django.db import transaction

from apps.marketplace import services as mk
from apps.marketplace.validators import validate_manifest

from .models import ProcessBlueprint


class ProcessCatalogError(Exception):  # noqa: N818 — domain error
    pass


def list_blueprints(*, category=None, search=None):
    qs = ProcessBlueprint.objects.filter(is_published=True)
    if category:
        qs = qs.filter(category=category)
    if search:
        qs = qs.filter(name__icontains=search)
    return list(qs.order_by("-install_count", "name"))


def get_blueprint(blueprint_id) -> ProcessBlueprint:
    bp = ProcessBlueprint.objects.filter(id=blueprint_id).first()
    if bp is None:
        raise ProcessCatalogError("Blueprint not found.")
    return bp


def preview(blueprint: ProcessBlueprint) -> dict:
    errors = validate_manifest(blueprint.manifest)
    m = blueprint.manifest or {}
    return {
        "id": str(blueprint.id), "slug": blueprint.slug, "name": blueprint.name,
        "valid": not errors, "errors": errors,
        "summary": {
            "entities": len(m.get("entities", []) or []),
            "workflows": len(m.get("workflows", []) or []),
            "rules": len(m.get("rules", []) or []),
            "reports": len(m.get("reports", []) or []),
            "notification_templates": len(m.get("notification_templates", []) or []),
        },
        "manifest": m,
    }


def install(*, blueprint_id, workspace_id, installed_by) -> dict:
    bp = get_blueprint(blueprint_id)
    if not bp.is_published:
        raise ProcessCatalogError("Blueprint is not published.")
    errors = validate_manifest(bp.manifest)
    if errors:
        raise ProcessCatalogError(f"Invalid manifest: {'; '.join(errors)}")

    manifest = bp.manifest
    with transaction.atomic():
        entity_ids = mk._apply_entities(manifest, workspace_id, installed_by)
        workflow_ids = mk._apply_workflows(manifest, workspace_id)
        rule_ids = mk._apply_rules(manifest, workspace_id)
        report_ids = mk._apply_reports(manifest, workspace_id)
        mk._apply_notification_templates(manifest, workspace_id)
        ProcessBlueprint.objects.filter(id=bp.id).update(install_count=bp.install_count + 1)

    # Capture the installed config in VCS history (best-effort; never breaks the install).
    try:
        from apps.config_vcs import services as cvcs
        cvcs.commit(workspace_id=workspace_id,
                    message=f"Installed process blueprint: {bp.slug}", author_id=installed_by)
    except Exception:  # noqa: BLE001
        pass

    return {"blueprint": bp.slug, "entity_ids": entity_ids, "workflow_ids": workflow_ids,
            "rule_ids": rule_ids, "report_ids": report_ids}
