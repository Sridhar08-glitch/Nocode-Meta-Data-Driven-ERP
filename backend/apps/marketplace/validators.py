"""
Plugin manifest validator (PROJECT_HANDBOOK.md §34.3).

``validate_manifest`` returns a list of human-readable errors (empty ⇒ valid). It
is intentionally pure (no DB writes) so it can gate both install and publish.
"""
from __future__ import annotations

import json
import re

from apps.metadata.models import FIELD_TYPE_VALUES
from apps.nql.ast import query_from_json
from apps.nql.exceptions import NQLError
from apps.nql.parser import parse_nql_text

SLUG_RE = re.compile(r"^[a-z][a-z0-9_]*$")
MAX_SLUG_LEN = 63
MAX_MANIFEST_BYTES = 512 * 1024  # 512 KB


def _check_slug(slug, label, seen, errors):
    if not isinstance(slug, str) or not SLUG_RE.match(slug) or len(slug) > MAX_SLUG_LEN:
        errors.append(f"invalid {label} slug {slug!r}")
        return
    if slug in seen:
        errors.append(f"duplicate {label} slug {slug!r}")
    seen.add(slug)


def _validate_nql(source, label, errors, *, entity_slug=None):
    try:
        if isinstance(source, dict):
            query_from_json(source)
        elif entity_slug is not None:
            parse_nql_text(f"FROM {entity_slug} WHERE {source}")
        else:
            parse_nql_text(source)
    except NQLError as exc:
        errors.append(f"{label}: invalid NQL ({exc})")
    except Exception as exc:  # noqa: BLE001 — any parse failure is a validation error
        errors.append(f"{label}: invalid NQL ({exc})")


def validate_manifest(manifest) -> list[str]:
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return ["manifest must be a JSON object"]

    try:
        size = len(json.dumps(manifest).encode("utf-8"))
    except (TypeError, ValueError):
        return ["manifest is not JSON-serializable"]
    if size > MAX_MANIFEST_BYTES:
        errors.append(f"manifest too large ({size} bytes > {MAX_MANIFEST_BYTES})")

    if manifest.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    # entities + fields
    entity_slugs: set = set()
    for ent in manifest.get("entities", []) or []:
        _check_slug(ent.get("slug"), "entity", entity_slugs, errors)
        field_slugs: set = set()
        for fd in ent.get("fields", []) or []:
            _check_slug(fd.get("slug"), "field", field_slugs, errors)
            ft = fd.get("field_type")
            if ft not in FIELD_TYPE_VALUES:
                errors.append(f"unknown field_type {ft!r} on field {fd.get('slug')!r}")

    # workflows + edge integrity
    wf_slugs: set = set()
    for wf in manifest.get("workflows", []) or []:
        _check_slug(wf.get("slug"), "workflow", wf_slugs, errors)
        step_slugs = {s.get("slug") for s in (wf.get("steps", []) or [])}
        for edge in wf.get("edges", []) or []:
            for end in ("source", "target"):
                if edge.get(end) not in step_slugs:
                    errors.append(
                        f"workflow {wf.get('slug')!r} edge {end} "
                        f"{edge.get(end)!r} references an unknown step")

    # rules
    rule_slugs: set = set()
    for rule in manifest.get("rules", []) or []:
        _check_slug(rule.get("slug"), "rule", rule_slugs, errors)
        nql = rule.get("condition_nql")
        if nql:
            _validate_nql(nql, f"rule {rule.get('slug')!r}", errors,
                          entity_slug=rule.get("entity_slug", "x"))

    # reports
    report_slugs: set = set()
    for rep in manifest.get("reports", []) or []:
        _check_slug(rep.get("slug"), "report", report_slugs, errors)
        if rep.get("nql_ast"):
            _validate_nql(rep["nql_ast"], f"report {rep.get('slug')!r}", errors)
        elif rep.get("nql_source"):
            _validate_nql(rep["nql_source"], f"report {rep.get('slug')!r}", errors)

    # notification templates
    tmpl_slugs: set = set()
    for tmpl in manifest.get("notification_templates", []) or []:
        _check_slug(tmpl.get("slug"), "notification_template", tmpl_slugs, errors)

    # permissions
    perm_slugs: set = set()
    for perm in manifest.get("permissions", []) or []:
        _check_slug(perm.get("slug"), "permission", perm_slugs, errors)

    return errors
