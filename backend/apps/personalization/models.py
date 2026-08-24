"""
Personalization (Phase P0) — per-user appearance & accessibility preferences.

One owner-scoped row per (workspace, user); ``values`` is a validated key/value
bag governed by ``apps.personalization.registry``. Built exactly like the ERP's
existing per-user stores (``views_saved.SavedView`` / ``notifications.NotificationPreference``):
``TenantModel`` + RLS (migration 0002). Workspace-level appearance defaults and the
admin lock policy live on ``branding.WorkspaceBranding`` — this table only holds a
user's personal overrides.
"""
from django.db import models

from apps.core.models import TenantModel


class UserPreference(TenantModel):
    user_id = models.UUIDField(db_index=True)   # accounts.User.id
    values = models.JSONField(default=dict)      # registry-governed appearance overrides

    class Meta:
        db_table = "user_preferences"
        unique_together = [("workspace_id", "user_id")]
        indexes = [models.Index(fields=["workspace_id", "user_id"])]

    def __str__(self):
        return f"prefs({self.user_id})"
