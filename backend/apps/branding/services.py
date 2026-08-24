"""
BrandingService (PROJECT_HANDBOOK.md §32.1).

White-label branding (one row per workspace) with **CSS sanitisation**
(`url()`/`@import`/`expression()`/`javascript:` stripped) and hex-colour
validation, plus per-workspace SMTP config whose password is held **by reference
only** and an SMTP connection test.
"""
from __future__ import annotations

import os
import re

from django.utils import timezone

from .models import EmailSMTPConfig, WorkspaceBranding

_HEX_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_URL_RE = re.compile(r"url\s*\(", re.IGNORECASE)
_IMPORT_RE = re.compile(r"@import[^;]*;?", re.IGNORECASE)
_EXPR_RE = re.compile(r"expression\s*\(", re.IGNORECASE)
_JS_RE = re.compile(r"javascript\s*:", re.IGNORECASE)
_COLOR_FIELDS = ["color_primary", "color_secondary", "color_accent", "color_background",
                 "color_surface", "color_text_primary", "color_text_muted"]
_NAMED = {"black", "white", "red", "green", "blue", "transparent", "inherit", "currentcolor"}


class BrandingError(Exception):  # noqa: N818 — domain error
    pass


def sanitize_css(css: str) -> str:
    """Strip dangerous CSS constructs (external fetches + script execution)."""
    if not css:
        return ""
    out = _IMPORT_RE.sub("", css)
    out = _URL_RE.sub("blocked(", out)        # neutralise url(...) fetches
    out = _EXPR_RE.sub("blocked(", out)       # neutralise IE expression()
    out = _JS_RE.sub("", out)
    return out


def _validate_color(value: str) -> bool:
    if not value:
        return True
    return bool(_HEX_RE.match(value)) or value.lower() in _NAMED


def resolve_secret(ref: str) -> str:
    return os.environ.get(ref, "") if ref else ""


def _smtp_test(config) -> dict:
    """Attempt an SMTP connection + login. Isolated for tests."""
    import smtplib
    password = resolve_secret(config.password_ref)
    try:
        server = (smtplib.SMTP_SSL(config.host, config.port, timeout=10) if config.use_ssl
                  else smtplib.SMTP(config.host, config.port, timeout=10))
        try:
            if config.use_tls and not config.use_ssl:
                server.starttls()
            if config.username:
                server.login(config.username, password)
        finally:
            server.quit()
        return {"success": True}
    except Exception as exc:  # noqa: BLE001 — report failure to the caller, never the password
        return {"success": False, "error": str(exc)}


class BrandingService:
    @staticmethod
    def get_or_create(workspace_id) -> WorkspaceBranding:
        obj, _ = WorkspaceBranding.objects.get_or_create(workspace_id=workspace_id)
        return obj

    @staticmethod
    def update_branding(workspace_id, data: dict) -> WorkspaceBranding:
        obj = BrandingService.get_or_create(workspace_id)
        for field in _COLOR_FIELDS:
            if field in data and not _validate_color(data[field]):
                raise BrandingError(f"Invalid colour for {field}: {data[field]!r}")
        allowed = {
            "logo_url", "favicon_url", "app_name", *_COLOR_FIELDS,
            "font_family_heading", "font_family_body", "default_theme",
            "allow_theme_toggle", "ui_density", "border_radius",
            "login_headline", "login_subtext",
            "login_background_url", "email_from_name", "email_header_html",
            "email_footer_html",
        }
        for key, value in data.items():
            if key in allowed:
                setattr(obj, key, value)
        if "locked_fields" in data:
            lf = data["locked_fields"]
            if not isinstance(lf, list) or not all(isinstance(x, str) for x in lf):
                raise BrandingError("locked_fields must be a list of strings")
            obj.locked_fields = lf
        if "custom_css" in data:
            obj.custom_css = sanitize_css(data["custom_css"])
        obj.save()
        return obj

    @staticmethod
    def get_smtp(workspace_id) -> EmailSMTPConfig | None:
        return EmailSMTPConfig.objects.filter(workspace_id=workspace_id).first()

    @staticmethod
    def save_smtp_config(workspace_id, data: dict) -> EmailSMTPConfig:
        # The raw password is NEVER persisted — only a reference name is stored.
        defaults = {k: data[k] for k in (
            "host", "port", "username", "password_ref", "use_tls", "use_ssl",
            "from_email", "from_name") if k in data}
        obj, _ = EmailSMTPConfig.objects.update_or_create(
            workspace_id=workspace_id, defaults=defaults)
        return obj

    @staticmethod
    def test_smtp(workspace_id) -> dict:
        config = BrandingService.get_smtp(workspace_id)
        if config is None:
            raise BrandingError("No SMTP configuration for this workspace")
        result = _smtp_test(config)
        config.last_test_at = timezone.now()
        config.last_test_result = "success" if result["success"] else "failed"
        config.is_verified = result["success"]
        if result["success"]:
            config.verified_at = timezone.now()
        config.save(update_fields=["last_test_at", "last_test_result", "is_verified",
                                   "verified_at"])
        return result
