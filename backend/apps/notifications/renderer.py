"""
Notification template rendering (PROJECT_HANDBOOK.md §22.1).

Templates use Python's ``string.Template`` — **never** Jinja2/eval/exec, so a
template string can substitute ``${var}`` placeholders but can never execute code.
The rendered HTML body is sanitised: ``<script>``/``<iframe>`` blocks, ``javascript:``
URIs and inline ``on*=`` event handlers are stripped before storage.
"""
from __future__ import annotations

import re
from string import Template

_SCRIPT_RE = re.compile(r"<\s*script\b[^>]*>.*?<\s*/\s*script\s*>", re.IGNORECASE | re.DOTALL)
_IFRAME_RE = re.compile(r"<\s*iframe\b[^>]*>.*?<\s*/\s*iframe\s*>", re.IGNORECASE | re.DOTALL)
_OPEN_SCRIPT_RE = re.compile(r"<\s*/?\s*(script|iframe)\b[^>]*>", re.IGNORECASE)
_JS_URI_RE = re.compile(r"javascript\s*:", re.IGNORECASE)
_ON_ATTR_RE = re.compile(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")


def sanitize_html(html: str) -> str:
    """Strip script/iframe blocks, javascript: URIs and on*= handlers."""
    if not html:
        return ""
    out = _SCRIPT_RE.sub("", html)
    out = _IFRAME_RE.sub("", out)
    out = _OPEN_SCRIPT_RE.sub("", out)   # unbalanced/standalone script/iframe tags
    out = _ON_ATTR_RE.sub("", out)
    out = _JS_URI_RE.sub("", out)
    return out


def _flatten(context: dict, prefix: str = "") -> dict:
    """Flatten nested dicts into ``parent_child`` string keys for ${} substitution."""
    flat: dict[str, str] = {}
    for key, value in (context or {}).items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(_flatten(value, prefix=f"{name}_"))
        elif isinstance(value, (list | tuple)):
            flat[name] = ", ".join(str(v) for v in value)
        elif value is None:
            flat[name] = ""
        else:
            flat[name] = str(value)
    return flat


def render_string(template_str: str, context: dict) -> str:
    """Safe ``${var}`` substitution; unknown placeholders are left intact."""
    if not template_str:
        return ""
    return Template(template_str).safe_substitute(_flatten(context))


def render_template(template, context: dict) -> dict:
    """Render a :class:`NotificationTemplate` against ``context``.

    Returns ``{"subject", "body", "short_body"}``. The body is HTML-sanitised; the
    short body is a plain-text, 140-char preview.
    """
    subject = render_string(template.subject_template, context)
    body = sanitize_html(render_string(template.body_template, context))
    plain = _TAG_RE.sub("", body).strip()
    short = plain[:140]
    return {"subject": subject, "body": body, "short_body": short}
