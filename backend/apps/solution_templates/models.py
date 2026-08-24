"""
Solution Template Framework (Phase P2.4A) — the foundation for ALL no-code solutions.

A ``SolutionTemplate`` is a GLOBAL catalog row (like ``ProcessBlueprint``) carrying an
EXTENDED manifest that spans the WHOLE stack: entities/relationships, forms, views,
workflows, rules, reports, notification templates, roles+permissions, dashboards, and the
Studio surface (applications / navigation / home layouts). Installing one auto-provisions
a working module into a workspace with ZERO Studio setup — reusing every existing engine
(metadata / schema registry / workflows / rules / reporting / studio / permissions); it
never duplicates platform functionality.

``InstalledSolution`` is the per-workspace record of what a given install provisioned, so
the framework can report and (soft-)uninstall cleanly while always preserving data.
"""
from django.db import models

from apps.core.models import TenantModel, TimestampMixin, UUIDPrimaryKeyMixin


class SolutionTemplate(UUIDPrimaryKeyMixin, TimestampMixin):
    """A packaged, installable end-to-end solution. Global (no workspace_id)."""

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=100, unique=True)
    category = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    publisher = models.CharField(max_length=200, blank=True)
    icon = models.CharField(max_length=100, blank=True)
    color = models.CharField(max_length=20, blank=True)
    version = models.CharField(max_length=20, default="1.0.0")
    manifest = models.JSONField(default=dict)   # extended solution manifest
    is_system = models.BooleanField(default=False)   # shipped with Sridhar ERP
    is_published = models.BooleanField(default=False)
    install_count = models.IntegerField(default=0)

    class Meta:
        db_table = "solution_templates"
        indexes = [models.Index(fields=["is_published", "category"])]

    def __str__(self):
        return f"{self.slug} ({'published' if self.is_published else 'draft'})"


class InstalledSolution(TenantModel):
    """Per-workspace record of a provisioned solution (TenantModel + RLS migration 0002)."""

    solution_template_id = models.UUIDField(null=True, blank=True, db_index=True)
    solution_slug = models.CharField(max_length=100)
    solution_name = models.CharField(max_length=200, blank=True)
    installed_version = models.CharField(max_length=20, default="")
    status = models.CharField(max_length=20, default="active")  # active | disabled

    # Package-platform lifecycle state (Phase P3.0): the manifest as installed (so upgrade can
    # diff and rollback can restore), the manifest of the prior version, and the package
    # migration versions already applied in this workspace.
    installed_manifest = models.JSONField(default=dict, blank=True)
    previous_manifest = models.JSONField(default=dict, blank=True)
    applied_migrations = models.JSONField(default=list, blank=True)

    created_entity_ids = models.JSONField(default=list)
    created_form_ids = models.JSONField(default=list)
    created_view_ids = models.JSONField(default=list)
    created_workflow_ids = models.JSONField(default=list)
    created_rule_ids = models.JSONField(default=list)
    created_report_ids = models.JSONField(default=list)
    created_role_ids = models.JSONField(default=list)
    created_dashboard_ids = models.JSONField(default=list)
    created_application_ids = models.JSONField(default=list)
    created_navigation_ids = models.JSONField(default=list)
    created_home_layout_ids = models.JSONField(default=list)
    # {section: [ids]} for the standard-engine sections (Phase P3.1A): document_templates,
    # email_templates, portal_grants, approval_processes, sla_policies, business_hours, kpis.
    created_extra_ids = models.JSONField(default=dict, blank=True)
    summary = models.JSONField(default=dict)

    class Meta:
        db_table = "installed_solutions"
        indexes = [models.Index(fields=["workspace_id", "status"])]
