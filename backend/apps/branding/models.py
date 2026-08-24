"""
Branding — per-workspace white-label customization.
"""
from django.db import models

from apps.core.models import TenantModel


class WorkspaceBranding(TenantModel):
    """
    Single white-label branding record per workspace.
    Enforced unique at service layer (one row per workspace_id).
    """
    # Visual identity
    logo_url = models.CharField(max_length=2000, blank=True)
    favicon_url = models.CharField(max_length=2000, blank=True)
    app_name = models.CharField(max_length=100, blank=True)

    # Colour palette
    color_primary = models.CharField(max_length=7, default="#6366f1")   # indigo
    color_secondary = models.CharField(max_length=7, default="#8b5cf6")
    color_accent = models.CharField(max_length=7, default="#06b6d4")
    color_background = models.CharField(max_length=7, default="#ffffff")
    color_surface = models.CharField(max_length=7, default="#f8fafc")
    color_text_primary = models.CharField(max_length=7, default="#0f172a")
    color_text_muted = models.CharField(max_length=7, default="#64748b")

    # Typography
    font_family_heading = models.CharField(max_length=100, default="Inter")
    font_family_body = models.CharField(max_length=100, default="Inter")

    # Theme
    default_theme = models.CharField(
        max_length=10,
        choices=[("light", "Light"), ("dark", "Dark"), ("system", "System")],
        default="system",
    )
    allow_theme_toggle = models.BooleanField(default=True)

    # Workspace UX personalization (applied at runtime via CSS variables / data attributes)
    ui_density = models.CharField(
        max_length=12,
        choices=[("comfortable", "Comfortable"), ("compact", "Compact")],
        default="comfortable",
    )
    border_radius = models.CharField(
        max_length=8,
        choices=[("none", "None"), ("sm", "Small"), ("md", "Medium"), ("lg", "Large"), ("xl", "Extra Large")],
        default="md",
    )

    # Personalization governance — appearance keys an admin has locked so members
    # cannot override them (see apps.personalization.registry for lockable keys).
    locked_fields = models.JSONField(default=list, blank=True)

    # Custom CSS (scoped, sanitized at save time)
    custom_css = models.TextField(blank=True)

    # Login page customization
    login_headline = models.CharField(max_length=255, blank=True)
    login_subtext = models.CharField(max_length=500, blank=True)
    login_background_url = models.CharField(max_length=2000, blank=True)

    # Email template header/footer
    email_from_name = models.CharField(max_length=100, blank=True)
    email_header_html = models.TextField(blank=True)
    email_footer_html = models.TextField(blank=True)

    class Meta:
        db_table = "workspace_branding"
        # One row per workspace — enforced at service layer
        unique_together = [("workspace_id",)]


class EmailSMTPConfig(TenantModel):
    """
    Custom SMTP configuration for outbound email.
    Password stored as reference only.
    """
    host = models.CharField(max_length=253)
    port = models.IntegerField(default=587)
    username = models.CharField(max_length=255)
    password_ref = models.CharField(max_length=255)   # reference to secrets store
    use_tls = models.BooleanField(default=True)
    use_ssl = models.BooleanField(default=False)
    from_email = models.EmailField()
    from_name = models.CharField(max_length=100, blank=True)
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    last_test_at = models.DateTimeField(null=True, blank=True)
    last_test_result = models.CharField(max_length=20, blank=True)

    class Meta:
        db_table = "email_smtp_configs"
        unique_together = [("workspace_id",)]
