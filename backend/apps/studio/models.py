"""
Studio config objects (Phase 1.32) — the "build an app" layer.

Three workspace-scoped, JSON-config models (TenantModel + RLS migration 0002):
  - Application : a packaged surface (entities + navigation + home + theme + role gating).
  - HomeLayout : a widget grid resolved per workspace | app | role | personal.
  - Navigation : a permission-aware menu tree resolved per workspace | app | role.

Draft→Publish: ``is_published=False`` is a draft; ``publish`` flips it on. Switcher /
resolve endpoints only ever return published config.
"""
from django.db import models

from apps.core.models import TenantModel


class Application(TenantModel):
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=100, blank=True)
    color = models.CharField(max_length=20, blank=True)
    included_entity_ids = models.JSONField(default=list)
    navigation_id = models.UUIDField(null=True, blank=True)
    home_layout_id = models.UUIDField(null=True, blank=True)
    role_ids = models.JSONField(default=list)        # [] = visible to everyone
    theme_overrides = models.JSONField(default=dict)
    order = models.IntegerField(default=0)
    is_published = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "studio_applications"
        unique_together = [("workspace_id", "slug")]
        indexes = [models.Index(fields=["workspace_id", "is_published"])]


class HomeLayout(TenantModel):
    SCOPE_CHOICES = [
        ("workspace", "Workspace"),
        ("app", "Application"),
        ("role", "Role"),
        ("personal", "Personal"),
    ]
    name = models.CharField(max_length=150)
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default="workspace")
    target_id = models.UUIDField(null=True, blank=True)  # app_id / role_id / user_id; null=workspace
    widgets = models.JSONField(default=list)
    is_published = models.BooleanField(default=False)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "studio_home_layouts"
        indexes = [models.Index(fields=["workspace_id", "scope"])]


class Navigation(TenantModel):
    SCOPE_CHOICES = [
        ("workspace", "Workspace"),
        ("app", "Application"),
        ("role", "Role"),
    ]
    name = models.CharField(max_length=150)
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default="workspace")
    target_id = models.UUIDField(null=True, blank=True)  # app_id / role_id; null=workspace
    tree = models.JSONField(default=list)  # [{label, roles?, items:[{label,type,target,roles?,icon}]}]
    is_published = models.BooleanField(default=False)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "studio_navigations"
        indexes = [models.Index(fields=["workspace_id", "scope"])]
