"""Template rendering + HTML sanitisation (PROJECT_HANDBOOK.md §22.1 / §22.6)."""
from apps.notifications.renderer import render_string, render_template, sanitize_html


class _Tpl:
    def __init__(self, subject, body):
        self.subject_template = subject
        self.body_template = body


def test_substitutes_variables():
    out = render_string("Hello ${actor_name}", {"actor_name": "Ada"})
    assert out == "Hello Ada"


def test_nested_context_flattened():
    out = render_string("By ${record_name}", {"record": {"name": "Lead-1"}})
    assert out == "By Lead-1"


def test_unknown_placeholder_left_intact():
    assert render_string("Hi ${missing}", {}) == "Hi ${missing}"


def test_sanitize_strips_script_and_iframe():
    dirty = "<b>hi</b><script>alert(1)</script><iframe src=x></iframe>"
    clean = sanitize_html(dirty)
    assert "<script" not in clean.lower()
    assert "<iframe" not in clean.lower()
    assert "alert(1)" not in clean
    assert "<b>hi</b>" in clean


def test_sanitize_strips_js_uri_and_handlers():
    dirty = '<a href="javascript:evil()" onclick="x()">link</a>'
    clean = sanitize_html(dirty)
    assert "javascript:" not in clean.lower()
    assert "onclick" not in clean.lower()


def test_render_template_returns_parts_and_sanitises():
    tpl = _Tpl("Hi ${actor_name}", "Welcome ${actor_name}<script>bad()</script>")
    out = render_template(tpl, {"actor_name": "Ada"})
    assert out["subject"] == "Hi Ada"
    assert "bad()" not in out["body"]
    assert out["short_body"].startswith("Welcome Ada")
