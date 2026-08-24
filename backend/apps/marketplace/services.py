"""
Marketplace & plugin installer (PROJECT_HANDBOOK.md §34.2).

Install applies a ``PluginVersion.manifest`` atomically: entities (+ physical
tables), workflows (+ steps/edges), business rules, reports, and notification
templates. The created object ids are tracked on ``InstalledPlugin`` so uninstall
can deactivate them cleanly. Schema additions are never auto-removed (data safety).
"""
from __future__ import annotations

import uuid

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.eventstore.events import DomainEventData, DomainEventFactory
from apps.metadata.models import EntityDefinition
from apps.schema_registry.services import SchemaRegistryService

from .models import InstalledPlugin, MarketplacePlugin, PluginVersion
from .validators import validate_manifest


class MarketplaceError(Exception):  # noqa: N818 — domain error
    pass


def _emit(workspace_id, aggregate_id, event_type, payload, actor_id):
    from apps.eventstore.models import DomainEvent
    agg = uuid.UUID(str(aggregate_id))
    version = DomainEvent.objects.filter(
        aggregate_id=agg, aggregate_type="installed_plugin").count() + 1
    DomainEventFactory.persist_one(DomainEventData(
        event_type=event_type, workspace_id=uuid.UUID(str(workspace_id)),
        aggregate_type="installed_plugin", aggregate_id=agg, version=version,
        payload=payload, actor_id=uuid.UUID(str(actor_id)) if actor_id else uuid.UUID(int=0)))


# ── manifest application ─────────────────────────────────────────────────────
def _entity_id_by_slug(workspace_id, slug):
    ent = EntityDefinition.objects.filter(workspace_id=workspace_id, slug=slug).first()
    return ent.id if ent else None


def _apply_entities(manifest, workspace_id, actor_id, *, existing_only=False) -> list[str]:
    """Create entities + fields. With existing_only, only add NEW fields to entities
    that already exist (used by upgrade — never removes or alters existing fields)."""
    created_ids: list[str] = []
    for ent in manifest.get("entities", []) or []:
        slug = ent["slug"]
        entity = EntityDefinition.objects.filter(workspace_id=workspace_id, slug=slug).first()
        if entity is None:
            if existing_only:
                # upgrade adds whole new entities too
                entity = SchemaRegistryService.create_entity(
                    workspace_id=workspace_id, slug=slug, name=ent.get("name", slug),
                    plural_name=ent.get("plural_name", ent.get("name", slug)),
                    description=ent.get("description", ""), created_by=actor_id)
                created_ids.append(str(entity.id))
            else:
                entity = SchemaRegistryService.create_entity(
                    workspace_id=workspace_id, slug=slug, name=ent.get("name", slug),
                    plural_name=ent.get("plural_name", ent.get("name", slug)),
                    description=ent.get("description", ""), created_by=actor_id)
                created_ids.append(str(entity.id))
        existing_fields = {fd.slug for fd in entity.fields.all()}
        for fd in ent.get("fields", []) or []:
            if fd["slug"] in existing_fields:
                continue  # never modify an existing field
            SchemaRegistryService.add_field(
                workspace_id=workspace_id, entity_slug=slug, slug=fd["slug"],
                name=fd.get("name", fd["slug"]), field_type=fd["field_type"],
                description=fd.get("description", ""),
                is_promoted=fd.get("is_promoted", False),
                is_required=fd.get("is_required", False),
                is_unique=fd.get("is_unique", False),
                is_filterable=fd.get("is_filterable", True),
                is_sortable=fd.get("is_sortable", True),
                config=fd.get("config"), updated_by=actor_id)
    return created_ids


def _apply_workflows(manifest, workspace_id) -> list[str]:
    from apps.workflows.models import WorkflowDefinition, WorkflowEdge, WorkflowStep
    created_ids: list[str] = []
    for wf in manifest.get("workflows", []) or []:
        wd = WorkflowDefinition.objects.create(
            workspace_id=workspace_id, name=wf.get("name", wf["slug"]), slug=wf["slug"],
            description=wf.get("description", ""), trigger_type=wf["trigger_type"],
            trigger_config=wf.get("trigger_config", {}), status="active",
            entity_id=_entity_id_by_slug(workspace_id, wf.get("entity_slug")))
        step_id_by_slug: dict = {}
        for s in wf.get("steps", []) or []:
            step = WorkflowStep.objects.create(
                workflow_id=wd.id, workspace_id=workspace_id, step_type=s["step_type"],
                name=s.get("name", s["slug"]), config=s.get("config", {}),
                is_entry=s.get("is_entry", False))
            step_id_by_slug[s["slug"]] = step.id
        for e in wf.get("edges", []) or []:
            WorkflowEdge.objects.create(
                workflow_id=wd.id, workspace_id=workspace_id,
                source_step_id=step_id_by_slug[e["source"]],
                target_step_id=step_id_by_slug[e["target"]],
                condition_label=e.get("condition_label", ""),
                condition_expr=e.get("condition_expr", ""))
        created_ids.append(str(wd.id))
    return created_ids


def _apply_rules(manifest, workspace_id) -> list[str]:
    from apps.rules.models import BusinessRule
    created_ids: list[str] = []
    for r in manifest.get("rules", []) or []:
        entity_id = _entity_id_by_slug(workspace_id, r.get("entity_slug"))
        if entity_id is None:
            continue
        rule = BusinessRule.objects.create(
            workspace_id=workspace_id, entity_id=entity_id, name=r.get("name", r["slug"]),
            slug=r["slug"], description=r.get("description", ""),
            trigger_on=r.get("trigger_on", "before_create"),
            watch_field_slug=r.get("watch_field_slug", ""),
            condition_nql=r.get("condition_nql", ""), actions=r.get("actions", []),
            priority=r.get("priority", 100), is_active=True)
        created_ids.append(str(rule.id))
    return created_ids


def _apply_reports(manifest, workspace_id) -> list[str]:
    from apps.nql.services import to_query
    from apps.reporting.models import Report
    created_ids: list[str] = []
    for rep in manifest.get("reports", []) or []:
        nql_ast = rep.get("nql_ast")
        if nql_ast is None and rep.get("nql_source"):
            nql_ast = {"entity": to_query(rep["nql_source"]).entity}
        report = Report.objects.create(
            workspace_id=workspace_id, name=rep.get("name", rep["slug"]), slug=rep["slug"],
            report_type=rep.get("report_type", "table"), nql_ast=nql_ast or {},
            nql_source=rep.get("nql_source", ""), display_config=rep.get("display_config", {}))
        created_ids.append(str(report.id))
    return created_ids


def _apply_notification_templates(manifest, workspace_id) -> None:
    from apps.notifications.models import NotificationTemplate
    for tmpl in manifest.get("notification_templates", []) or []:
        for channel in tmpl.get("channels", ["in_app"]) or ["in_app"]:
            NotificationTemplate.objects.get_or_create(
                workspace_id=workspace_id, slug=tmpl["slug"], channel=channel,
                defaults={"name": tmpl.get("name", tmpl["slug"]),
                          "subject_template": tmpl.get("subject_template", ""),
                          "body_template": tmpl.get("body_template", "")})


class MarketplaceService:
    # ── browse ────────────────────────────────────────────────────────────────
    @staticmethod
    def list_plugins(*, category=None, search=None, page=1, page_size=50):
        qs = MarketplacePlugin.objects.filter(status="published")
        if category:
            qs = qs.filter(category=category)
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(tagline__icontains=search)
                           | Q(description__icontains=search))
        qs = qs.order_by("-install_count", "name")
        page = max(int(page or 1), 1)
        start = (page - 1) * page_size
        return list(qs[start:start + page_size])

    @staticmethod
    def get_plugin(plugin_id):
        return MarketplacePlugin.objects.filter(id=plugin_id).first()

    # ── install ───────────────────────────────────────────────────────────────
    @staticmethod
    def install_plugin(*, plugin_id, version_id, workspace_id, installed_by) -> InstalledPlugin:
        plugin = MarketplacePlugin.objects.filter(id=plugin_id).first()
        if plugin is None:
            raise MarketplaceError("Plugin not found")
        if plugin.status != "published":
            raise MarketplaceError("Plugin is not published")
        version = PluginVersion.objects.filter(id=version_id, plugin_id=plugin_id).first()
        if version is None:
            raise MarketplaceError("Plugin version not found")
        if InstalledPlugin.objects.filter(
                workspace_id=workspace_id, plugin_slug=plugin.slug).exclude(
                status="uninstalling").exists():
            raise MarketplaceError("Plugin is already installed in this workspace")

        manifest_errors = validate_manifest(version.manifest)
        if manifest_errors:
            raise MarketplaceError("; ".join(manifest_errors))
        # Package-platform requirements gate (core version + required engines/capabilities +
        # package dependencies). No-op for manifests without a ``package`` block.
        from apps.packaging.preflight import requirement_errors
        req_errors = requirement_errors(version.manifest, workspace_id=workspace_id)
        if req_errors:
            raise MarketplaceError("; ".join(req_errors))

        manifest = version.manifest
        # Atomic: any failure rolls back ALL schema/object creation.
        with transaction.atomic():
            entity_ids = _apply_entities(manifest, workspace_id, installed_by)
            workflow_ids = _apply_workflows(manifest, workspace_id)
            rule_ids = _apply_rules(manifest, workspace_id)
            report_ids = _apply_reports(manifest, workspace_id)
            _apply_notification_templates(manifest, workspace_id)
            installed = InstalledPlugin.objects.create(
                workspace_id=workspace_id, plugin_id=plugin.id,
                plugin_version_id=version.id, plugin_slug=plugin.slug,
                installed_version=version.version, status="active",
                installed_by=installed_by, installed_at=timezone.now(),
                created_entity_ids=entity_ids, created_workflow_ids=workflow_ids,
                created_rule_ids=rule_ids, created_report_ids=report_ids)
            MarketplacePlugin.objects.filter(id=plugin.id).update(
                install_count=plugin.install_count + 1)
        _emit(workspace_id, installed.id, "plugin.installed",
              {"plugin_slug": plugin.slug, "version": version.version}, installed_by)
        return installed

    # ── uninstall ───────────────────────────────────────────────────────────────
    @staticmethod
    def uninstall_plugin(*, installed_plugin_id, workspace_id, actor_id,
                         hard=False) -> InstalledPlugin:
        ip = InstalledPlugin.objects.filter(
            id=installed_plugin_id, workspace_id=workspace_id).first()
        if ip is None:
            raise MarketplaceError("Installed plugin not found")
        from apps.rules.models import BusinessRule
        from apps.workflows.models import WorkflowDefinition
        with transaction.atomic():
            WorkflowDefinition.objects.filter(
                workspace_id=workspace_id, id__in=ip.created_workflow_ids).update(
                status="archived")
            BusinessRule.objects.filter(
                workspace_id=workspace_id, id__in=ip.created_rule_ids).update(is_active=False)
            if hard:
                # Soft-delete entity definitions; records remain in physical tables.
                EntityDefinition.objects.filter(
                    workspace_id=workspace_id, id__in=ip.created_entity_ids).update(
                    is_active=False)
            ip.status = "disabled"
            ip.save(update_fields=["status"])
        _emit(workspace_id, ip.id, "plugin.uninstalled",
              {"plugin_slug": ip.plugin_slug, "hard": hard}, actor_id)
        return ip

    # ── upgrade / rollback ──────────────────────────────────────────────────────
    @staticmethod
    def upgrade_plugin(*, installed_plugin_id, new_version_id, actor_id) -> InstalledPlugin:
        ip = InstalledPlugin.objects.filter(id=installed_plugin_id).first()
        if ip is None:
            raise MarketplaceError("Installed plugin not found")
        new_version = PluginVersion.objects.filter(
            id=new_version_id, plugin_id=ip.plugin_id).first()
        if new_version is None:
            raise MarketplaceError("Target version not found")
        errors = validate_manifest(new_version.manifest)
        if errors:
            raise MarketplaceError("; ".join(errors))

        with transaction.atomic():
            # additive only — never removes existing entities/fields (breaking change)
            new_entity_ids = _apply_entities(
                new_version.manifest, ip.workspace_id, actor_id, existing_only=True)
            config = dict(ip.config or {})
            config["previous_version_id"] = str(ip.plugin_version_id)
            ip.config = config
            ip.created_entity_ids = list(ip.created_entity_ids) + new_entity_ids
            ip.plugin_version_id = new_version.id
            ip.installed_version = new_version.version
            ip.status = "active"
            ip.save(update_fields=["config", "created_entity_ids", "plugin_version_id",
                                   "installed_version", "status"])
        _emit(ip.workspace_id, ip.id, "plugin.upgraded",
              {"plugin_slug": ip.plugin_slug, "version": new_version.version}, actor_id)
        return ip

    @staticmethod
    def rollback_plugin(*, installed_plugin_id, actor_id) -> InstalledPlugin:
        ip = InstalledPlugin.objects.filter(id=installed_plugin_id).first()
        if ip is None:
            raise MarketplaceError("Installed plugin not found")
        prev_id = (ip.config or {}).get("previous_version_id")
        if not prev_id:
            raise MarketplaceError("No previous version to roll back to")
        prev = PluginVersion.objects.filter(id=prev_id).first()
        if prev is None:
            raise MarketplaceError("Previous version no longer exists")
        from apps.rules.models import BusinessRule
        from apps.workflows.models import WorkflowDefinition
        with transaction.atomic():
            # Restore the prior version pointer; schema additions are NOT undone.
            # Re-activate the plugin's workflows/rules.
            WorkflowDefinition.objects.filter(
                workspace_id=ip.workspace_id, id__in=ip.created_workflow_ids).update(
                status="active")
            BusinessRule.objects.filter(
                workspace_id=ip.workspace_id, id__in=ip.created_rule_ids).update(is_active=True)
            ip.plugin_version_id = prev.id
            ip.installed_version = prev.version
            ip.status = "active"
            ip.save(update_fields=["plugin_version_id", "installed_version", "status"])
        _emit(ip.workspace_id, ip.id, "plugin.rolled_back",
              {"plugin_slug": ip.plugin_slug, "version": prev.version}, actor_id)
        return ip
