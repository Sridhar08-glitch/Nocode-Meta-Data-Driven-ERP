"""
Email-template rendering + test-send (Phase 1.33).

Rendering reuses the notifications renderer (safe ``${var}`` substitution + HTML
sanitisation). Test-send goes through Django mail (backend per settings); the from-name
is taken from workspace branding when present, the address from ``DEFAULT_FROM_EMAIL``.
Content edits bump ``version``.
"""
from __future__ import annotations

from django.conf import settings

from apps.notifications.renderer import render_string, sanitize_html

from .models import EmailTemplate

_VERSIONED_FIELDS = {"subject_template", "body_html", "blocks"}


class EmailTemplateError(Exception):  # noqa: N818 — domain error
    pass


def render(template: EmailTemplate, context: dict | None = None) -> dict:
    """Render to ``{"subject", "html"}`` against *context* (HTML sanitised)."""
    context = context or {}
    return {
        "subject": render_string(template.subject_template, context),
        "html": sanitize_html(render_string(template.body_html, context)),
    }


def apply_version_bump(template: EmailTemplate, updates: dict) -> None:
    """Increment ``version`` when any content field actually changes."""
    if any(f in updates and updates[f] != getattr(template, f) for f in _VERSIONED_FIELDS):
        template.version = (template.version or 1) + 1


def _from_address(workspace_id) -> str:
    default = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@nexuserp.local")
    try:
        from apps.branding.models import WorkspaceBranding
        b = WorkspaceBranding.objects.filter(workspace_id=workspace_id).first()
        if b and getattr(b, "email_from_name", ""):
            # keep the configured address, prepend the branded display name
            return f"{b.email_from_name} <{default}>"
    except Exception:  # noqa: BLE001 — branding is optional
        pass
    return default


def test_send(template: EmailTemplate, *, to_email: str, context: dict | None = None) -> dict:
    """Render and send a one-off test email. Returns a small status dict."""
    if not to_email:
        raise EmailTemplateError("A recipient email is required.")
    from django.core.mail import EmailMultiAlternatives
    rendered = render(template, context)
    msg = EmailMultiAlternatives(
        subject=rendered["subject"] or "(no subject)",
        body=rendered["html"],
        from_email=_from_address(template.workspace_id),
        to=[to_email],
    )
    msg.attach_alternative(rendered["html"], "text/html")
    msg.send(fail_silently=False)
    return {"sent": True, "to": to_email, "subject": rendered["subject"]}
