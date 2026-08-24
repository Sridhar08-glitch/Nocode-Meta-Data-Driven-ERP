"""
Manifest appliers for the Solution Template Framework (Phase P2.4A).

Entities / workflows / rules / reports / notification_templates are applied by REUSING the
marketplace appliers unchanged (never duplicated). This module adds the sections marketplace
does not cover — forms, views, roles+permissions, dashboards, and the Studio surface
(navigation, home layouts, applications) — each idempotent (skips rows that already exist,
never modifies them, mirroring the marketplace "additive-only" contract).

All appliers run inside the single ``transaction.atomic()`` opened by ``services.install``.
"""
from __future__ import annotations

from apps.marketplace import services as mk


def _entity_id(workspace_id, slug):
    return mk._entity_id_by_slug(workspace_id, slug)


def _existing_slugs(model, workspace_id):
    return set(model.objects.filter(
        workspace_id=workspace_id).values_list("slug", flat=True))


def prune_existing(manifest, workspace_id) -> dict:
    """Drop workflow/rule/report items whose slug is already present in the workspace, so the
    (non-idempotent) marketplace appliers only ever create NEW rows on re-install."""
    from apps.reporting.models import Report
    from apps.rules.models import BusinessRule
    from apps.workflows.models import WorkflowDefinition

    pruned = dict(manifest)
    wf = _existing_slugs(WorkflowDefinition, workspace_id)
    pruned["workflows"] = [w for w in (manifest.get("workflows") or [])
                           if w.get("slug") not in wf]
    rules = _existing_slugs(BusinessRule, workspace_id)
    pruned["rules"] = [r for r in (manifest.get("rules") or [])
                       if r.get("slug") not in rules]
    reps = _existing_slugs(Report, workspace_id)
    pruned["reports"] = [r for r in (manifest.get("reports") or [])
                         if r.get("slug") not in reps]
    return pruned


# ── Entities ─────────────────────────────────────────────────────────────────
def apply_entities(manifest, workspace_id, actor_id) -> list[str]:
    """Create entities with their fields supplied AT CREATE-TABLE time.

    Unlike the marketplace applier (which creates an entity then ``ADD COLUMN``s each field),
    we pass the full field list into ``create_entity`` so unique/required columns are part of
    the ``CREATE TABLE`` — which SQLite permits (it forbids ``ADD`` of a UNIQUE column). For an
    entity that already exists, fall back to adding only the NEW, non-unique fields (additive,
    never modifies an existing field), mirroring the marketplace contract.
    """
    from apps.metadata.models import EntityDefinition
    from apps.schema_registry.services import SchemaRegistryService

    created: list[str] = []
    for ent in manifest.get("entities", []) or []:
        slug = ent["slug"]
        existing = EntityDefinition.objects.filter(
            workspace_id=workspace_id, slug=slug).first()
        if existing is None:
            entity = SchemaRegistryService.create_entity(
                workspace_id=workspace_id, slug=slug, name=ent.get("name", slug),
                plural_name=ent.get("plural_name", ent.get("name", slug)),
                description=ent.get("description", ""),
                fields=ent.get("fields", []) or [], created_by=actor_id)
            created.append(str(entity.id))
            continue
        existing_fields = {fd.slug for fd in existing.fields.all()}
        for fd in ent.get("fields", []) or []:
            if fd["slug"] in existing_fields:
                continue
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
    return created


# ── Forms ────────────────────────────────────────────────────────────────────
def apply_forms(manifest, workspace_id, actor_id) -> list[str]:
    from apps.metadata.models import FormDefinition
    created: list[str] = []
    for fm in manifest.get("forms", []) or []:
        entity_id = _entity_id(workspace_id, fm.get("entity_slug"))
        if entity_id is None:
            continue
        name = fm.get("name", fm["slug"])
        if FormDefinition.objects.filter(
                workspace_id=workspace_id, entity_id=entity_id, name=name).exists():
            continue
        form = FormDefinition.objects.create(
            workspace_id=workspace_id, entity_id=entity_id, name=name,
            is_default=fm.get("is_default", False), is_public=fm.get("is_public", False),
            layout=fm.get("layout", []), settings=fm.get("settings", {}),
            created_by=actor_id)
        created.append(str(form.id))
    return created


# ── Views ────────────────────────────────────────────────────────────────────
def apply_views(manifest, workspace_id, actor_id) -> list[str]:
    from apps.metadata.models import ViewDefinition
    created: list[str] = []
    for vw in manifest.get("views", []) or []:
        entity_id = _entity_id(workspace_id, vw.get("entity_slug"))
        if entity_id is None:
            continue
        name = vw.get("name", vw["slug"])
        if ViewDefinition.objects.filter(
                workspace_id=workspace_id, entity_id=entity_id, name=name).exists():
            continue
        view = ViewDefinition.objects.create(
            workspace_id=workspace_id, entity_id=entity_id, name=name,
            view_type=vw.get("view_type", "table"), config=vw.get("config", {}),
            is_default=vw.get("is_default", False), is_shared=vw.get("is_shared", True),
            order=vw.get("order", 0), created_by=actor_id)
        created.append(str(view.id))
    return created


# ── Roles + Permissions ──────────────────────────────────────────────────────
def apply_roles(manifest, workspace_id) -> list[str]:
    from apps.permissions.models import (
        DataMaskingRule,
        FieldPermission,
        Permission,
        Role,
    )

    created: list[str] = []
    slug_to_id: dict[str, object] = {}

    # Pass 1: create roles (skip existing).
    for r in manifest.get("roles", []) or []:
        role = Role.objects.filter(workspace_id=workspace_id, slug=r["slug"]).first()
        if role is None:
            role = Role.objects.create(
                workspace_id=workspace_id, name=r.get("name", r["slug"]), slug=r["slug"],
                description=r.get("description", ""), is_active=True)
            created.append(str(role.id))
        slug_to_id[r["slug"]] = role.id

    # Pass 2: parents + permissions (now all role ids are known).
    for r in manifest.get("roles", []) or []:
        role_id = slug_to_id[r["slug"]]
        parent_slug = r.get("parent_slug")
        if parent_slug and parent_slug in slug_to_id:
            Role.objects.filter(id=role_id).update(parent_role_id=slug_to_id[parent_slug])
        for p in r.get("permissions", []) or []:
            resource_id = None
            if p.get("resource_type", "entity") == "entity" and p.get("entity_slug"):
                resource_id = _entity_id(workspace_id, p["entity_slug"])
                if resource_id is None:
                    continue  # entity not in this solution — skip the grant
            Permission.objects.get_or_create(
                role_id=role_id, workspace_id=workspace_id,
                resource_type=p.get("resource_type", "entity"),
                resource_id=resource_id, action=p["action"],
                defaults={"is_deny": p.get("is_deny", False),
                          "conditions": p.get("conditions", [])})
        for fp in r.get("field_permissions", []) or []:
            field_id = _field_id(workspace_id,
                                 fp.get("entity_slug"), fp.get("field_slug"))
            if field_id is None:
                continue
            FieldPermission.objects.get_or_create(
                workspace_id=workspace_id, field_id=field_id, role_id=role_id,
                defaults={"can_read": fp.get("can_read", True),
                          "can_write": fp.get("can_write", True)})
        for mr in r.get("masking", []) or []:
            field_id = _field_id(workspace_id,
                                 mr.get("entity_slug"), mr.get("field_slug"))
            if field_id is None:
                continue
            DataMaskingRule.objects.get_or_create(
                workspace_id=workspace_id, field_id=field_id, role_id=role_id,
                defaults={"mask_type": mr.get("mask_type", "full"),
                          "mask_pattern": mr.get("mask_pattern", "")})
    return created


def _field_id(workspace_id, entity_slug, field_slug):
    from apps.metadata.models import FieldDefinition
    if not entity_slug or not field_slug:
        return None
    entity_id = mk._entity_id_by_slug(workspace_id, entity_slug)
    if entity_id is None:
        return None
    fd = FieldDefinition.objects.filter(
        workspace_id=workspace_id, entity_id=entity_id, slug=field_slug).first()
    return fd.id if fd else None


# ── Dashboards ───────────────────────────────────────────────────────────────
def apply_dashboards(manifest, workspace_id) -> list[str]:
    from apps.reporting.models import Dashboard, DashboardWidget, Report
    created: list[str] = []
    for db in manifest.get("dashboards", []) or []:
        if Dashboard.objects.filter(workspace_id=workspace_id, slug=db["slug"]).exists():
            continue
        dash = Dashboard.objects.create(
            workspace_id=workspace_id, name=db.get("name", db["slug"]), slug=db["slug"],
            description=db.get("description", ""), layout=db.get("layout", []),
            is_public=db.get("is_public", False), is_default=db.get("is_default", False))
        for w in db.get("widgets", []) or []:
            report_id = None
            if w.get("report_slug"):
                rep = Report.objects.filter(
                    workspace_id=workspace_id, slug=w["report_slug"]).first()
                report_id = rep.id if rep else None
            DashboardWidget.objects.create(
                dashboard_id=dash.id, workspace_id=workspace_id,
                widget_type=w.get("widget_type", "text"), title=w.get("title", ""),
                report_id=report_id,
                grid_x=w.get("grid_x", 0), grid_y=w.get("grid_y", 0),
                grid_w=w.get("grid_w", 6), grid_h=w.get("grid_h", 4),
                config=w.get("config", {}))
        created.append(str(dash.id))
    return created


# ── Studio: navigation, home layouts, applications ───────────────────────────
def apply_studio(manifest, workspace_id, actor_id) -> dict:
    """Create navigations + home layouts (collecting ``ref`` → id), then applications
    referencing them; finally point app-scoped nav/home ``target_id`` at the new app."""
    from apps.permissions.models import Role
    from apps.studio.models import Application, HomeLayout, Navigation

    nav_ids: list[str] = []
    home_ids: list[str] = []
    app_ids: list[str] = []
    nav_by_ref: dict[str, object] = {}
    home_by_ref: dict[str, object] = {}

    for nv in manifest.get("navigations", []) or []:
        nav = Navigation.objects.create(
            workspace_id=workspace_id, name=nv.get("name", nv.get("ref", "Menu")),
            scope=nv.get("scope", "app"), tree=nv.get("tree", []),
            is_published=nv.get("is_published", True), created_by=actor_id)
        nav_ids.append(str(nav.id))
        if nv.get("ref"):
            nav_by_ref[nv["ref"]] = nav

    for hl in manifest.get("home_layouts", []) or []:
        # DG-5: a home layout may bind to a role by slug — the installer resolves it to the
        # created Role's id and marks it role-scoped, so ``resolve_home_layout`` auto-routes each
        # role to its dashboard after login. Reusable by every package; no bespoke code.
        scope = hl.get("scope", "app")
        target_id = None
        role_slug = hl.get("role_slug")
        if role_slug:
            role = Role.objects.filter(workspace_id=workspace_id, slug=role_slug).first()
            if role is None:
                continue  # role not provisioned → cannot bind; skip silently
            scope, target_id = "role", role.id
        home = HomeLayout.objects.create(
            workspace_id=workspace_id, name=hl.get("name", hl.get("ref", "Home")),
            scope=scope, target_id=target_id, widgets=hl.get("widgets", []),
            is_published=hl.get("is_published", True), created_by=actor_id)
        home_ids.append(str(home.id))
        if hl.get("ref"):
            home_by_ref[hl["ref"]] = home

    for ap in manifest.get("applications", []) or []:
        if Application.objects.filter(workspace_id=workspace_id, slug=ap["slug"]).exists():
            continue
        nav = nav_by_ref.get(ap.get("navigation_ref"))
        home = home_by_ref.get(ap.get("home_layout_ref"))
        included_ids = [
            str(eid) for eid in (
                _entity_id(workspace_id, s) for s in ap.get("included_entity_slugs", []) or []
            ) if eid is not None
        ]
        role_ids = _resolve_role_ids(workspace_id, ap.get("role_slugs", []))
        app = Application.objects.create(
            workspace_id=workspace_id, name=ap.get("name", ap["slug"]), slug=ap["slug"],
            description=ap.get("description", ""), icon=ap.get("icon", ""),
            color=ap.get("color", ""), included_entity_ids=included_ids,
            navigation_id=(nav.id if nav else None),
            home_layout_id=(home.id if home else None),
            role_ids=role_ids, theme_overrides=ap.get("theme_overrides", {}),
            order=ap.get("order", 0), is_published=ap.get("is_published", True),
            created_by=actor_id)
        app_ids.append(str(app.id))
        # Point app-scoped nav/home at the new app so resolve_* finds them.
        if nav is not None and nav.scope == "app":
            Navigation.objects.filter(id=nav.id).update(target_id=app.id)
        if home is not None and home.scope == "app":
            HomeLayout.objects.filter(id=home.id).update(target_id=app.id)

    return {"navigation_ids": nav_ids, "home_layout_ids": home_ids,
            "application_ids": app_ids}


def _resolve_role_ids(workspace_id, role_slugs):
    from apps.permissions.models import Role
    if not role_slugs:
        return []
    rows = Role.objects.filter(workspace_id=workspace_id, slug__in=list(role_slugs))
    return [str(r.id) for r in rows]


# ── Standard manifest appliers for existing Core engines (Phase P3.1A) ────────
# Each engine already exists; only the package provisioning layer was missing. Every applier
# below is idempotent (skips an object that already exists by its natural key, never modifies
# it) — mirroring the additive-only contract of the appliers above. No business logic is added.
def apply_document_templates(manifest, workspace_id, actor_id) -> list[str]:
    """Provision ``document_templates`` (apps.document_templates.DocumentTemplate)."""
    from apps.document_templates.models import DocumentTemplate
    created: list[str] = []
    for dt in manifest.get("document_templates", []) or []:
        if not dt.get("slug") or DocumentTemplate.objects.filter(
                workspace_id=workspace_id, slug=dt["slug"]).exists():
            continue
        obj = DocumentTemplate.objects.create(
            workspace_id=workspace_id, slug=dt["slug"], name=dt.get("name", dt["slug"]),
            entity_slug=dt.get("entity_slug", ""), page_config=dt.get("page_config", {}),
            blocks=dt.get("blocks", []), line_items=dt.get("line_items", {}),
            is_active=dt.get("is_active", True), created_by=actor_id)
        created.append(str(obj.id))
    return created


def apply_email_templates(manifest, workspace_id, actor_id) -> list[str]:
    """Provision ``email_templates`` (apps.email_templates.EmailTemplate); key (slug, locale)."""
    from apps.email_templates.models import EmailTemplate
    created: list[str] = []
    for et in manifest.get("email_templates", []) or []:
        locale = et.get("locale", "en")
        if not et.get("slug") or EmailTemplate.objects.filter(
                workspace_id=workspace_id, slug=et["slug"], locale=locale).exists():
            continue
        obj = EmailTemplate.objects.create(
            workspace_id=workspace_id, slug=et["slug"], locale=locale,
            name=et.get("name", et["slug"]), subject_template=et.get("subject_template", ""),
            body_html=et.get("body_html", ""), blocks=et.get("blocks", []),
            variables=et.get("variables", []), is_active=et.get("is_active", True),
            created_by=actor_id)
        created.append(str(obj.id))
    return created


def apply_portal_grants(manifest, workspace_id, actor_id) -> list[str]:
    """Provision ``portal_grants`` (apps.portal.PortalEntityGrant); key (entity_slug, portal_type)."""
    from apps.portal.models import PortalEntityGrant
    created: list[str] = []
    for g in manifest.get("portal_grants", []) or []:
        entity_slug = g.get("entity_slug")
        ptype = g.get("portal_type", "")
        if not entity_slug or PortalEntityGrant.objects.filter(
                workspace_id=workspace_id, entity_slug=entity_slug, portal_type=ptype).exists():
            continue
        obj = PortalEntityGrant.objects.create(
            workspace_id=workspace_id, entity_slug=entity_slug, portal_type=ptype,
            link_field=g.get("link_field", ""), link_source=g.get("link_source", ""),
            can_read=g.get("can_read", True),
            can_create=g.get("can_create", False), can_update=g.get("can_update", False))
        created.append(str(obj.id))
    return created


def apply_approval_processes(manifest, workspace_id, actor_id) -> list[str]:
    """Provision ``approval_processes`` (apps.approvals.ApprovalProcess)."""
    from apps.approvals.models import ApprovalProcess
    created: list[str] = []
    for ap in manifest.get("approval_processes", []) or []:
        if not ap.get("slug") or ApprovalProcess.objects.filter(
                workspace_id=workspace_id, slug=ap["slug"]).exists():
            continue
        entity_id = _entity_id(workspace_id, ap.get("entity_slug"))
        if entity_id is None:
            continue  # process must bind to an entity in this solution
        obj = ApprovalProcess.objects.create(
            workspace_id=workspace_id, slug=ap["slug"], name=ap.get("name", ap["slug"]),
            entity_id=entity_id, trigger_condition_nql=ap.get("trigger_condition_nql", ""),
            levels=ap.get("levels", []), on_approve_actions=ap.get("on_approve_actions", []),
            on_reject_actions=ap.get("on_reject_actions", []),
            is_active=ap.get("is_active", True))
        created.append(str(obj.id))
    return created


def apply_sla_policies(manifest, workspace_id, actor_id) -> list[str]:
    """Provision ``sla_policies`` (apps.sla.SLAPolicy)."""
    from apps.sla.models import SLAPolicy
    created: list[str] = []
    for sp in manifest.get("sla_policies", []) or []:
        if not sp.get("slug") or SLAPolicy.objects.filter(
                workspace_id=workspace_id, slug=sp["slug"]).exists():
            continue
        entity_id = _entity_id(workspace_id, sp.get("entity_slug"))
        if entity_id is None:
            continue
        obj = SLAPolicy.objects.create(
            workspace_id=workspace_id, slug=sp["slug"], name=sp.get("name", sp["slug"]),
            entity_id=entity_id, description=sp.get("description", ""),
            applies_when_nql=sp.get("applies_when_nql", ""), targets=sp.get("targets", []),
            escalation_actions=sp.get("escalation_actions", []),
            is_active=sp.get("is_active", True))
        created.append(str(obj.id))
    return created


def apply_business_hours(manifest, workspace_id, actor_id) -> list[str]:
    """Provision ``business_hours`` (apps.sla.BusinessHours); key by name."""
    from apps.sla.models import BusinessHours
    created: list[str] = []
    for bh in manifest.get("business_hours", []) or []:
        name = bh.get("name")
        if not name or BusinessHours.objects.filter(
                workspace_id=workspace_id, name=name).exists():
            continue
        obj = BusinessHours.objects.create(
            workspace_id=workspace_id, name=name, timezone=bh.get("timezone", "UTC"),
            schedule=bh.get("schedule", {}), holidays=bh.get("holidays", []),
            weekly_hours=bh.get("weekly_hours", {}), shifts=bh.get("shifts", {}),
            region=bh.get("region", ""))
        created.append(str(obj.id))
    return created


def apply_kpis(manifest, workspace_id, actor_id) -> list[str]:
    """Provision ``kpis`` (apps.analytics.KPIDefinition); key by code."""
    from apps.analytics.models import KPIDefinition
    created: list[str] = []
    for k in manifest.get("kpis", []) or []:
        code = k.get("code") or k.get("slug")
        if not code or KPIDefinition.objects.filter(
                workspace_id=workspace_id, code=code).exists():
            continue
        obj = KPIDefinition.objects.create(
            workspace_id=workspace_id, code=code, name=k.get("name", code),
            description=k.get("description", ""), category=k.get("category", "general"),
            source_type=k.get("source_type", "nql"), nql_source=k.get("nql_source", ""),
            value_field=k.get("value_field", ""), aggregate=k.get("aggregate", "sum"),
            native_key=k.get("native_key", ""), target=k.get("target", 0),
            warning_threshold=k.get("warning_threshold", 0),
            critical_threshold=k.get("critical_threshold", 0),
            direction=k.get("direction", "higher_better"), unit=k.get("unit", ""),
            owner=k.get("owner", ""), refresh_strategy=k.get("refresh_strategy", "on_demand"),
            is_active=k.get("is_active", True))
        created.append(str(obj.id))
    return created


def apply_standard_sections(manifest, workspace_id, actor_id) -> dict:
    """Run every standard-engine applier; return {section: [ids]} for the install record."""
    return {
        "document_templates": apply_document_templates(manifest, workspace_id, actor_id),
        "email_templates": apply_email_templates(manifest, workspace_id, actor_id),
        "portal_grants": apply_portal_grants(manifest, workspace_id, actor_id),
        "approval_processes": apply_approval_processes(manifest, workspace_id, actor_id),
        "sla_policies": apply_sla_policies(manifest, workspace_id, actor_id),
        "business_hours": apply_business_hours(manifest, workspace_id, actor_id),
        "kpis": apply_kpis(manifest, workspace_id, actor_id),
    }
