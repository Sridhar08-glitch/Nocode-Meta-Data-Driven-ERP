"""
Document-template rendering (Phase 1.33).

Resolves a bound record (through RecordService → RBAC/ABAC/masking apply), maps the
template's header blocks to metric lines and the optional line-item config to a table,
then renders a PDF via the pluggable engine from Phase 1.31. Content edits bump version.
"""
from __future__ import annotations

from .models import DocumentTemplate

_VERSIONED_FIELDS = {"page_config", "blocks", "line_items", "entity_slug"}


class DocumentTemplateError(Exception):  # noqa: N818 — domain error
    pass


def apply_version_bump(template: DocumentTemplate, updates: dict) -> None:
    if any(f in updates and updates[f] != getattr(template, f) for f in _VERSIONED_FIELDS):
        template.version = (template.version or 1) + 1


def _line_item_table(template, workspace_id, member, record_id) -> dict | None:
    cfg = template.line_items or {}
    slug = cfg.get("entity_slug")
    relation_field = cfg.get("relation_field")
    columns = cfg.get("columns") or []
    if not (slug and relation_field and columns):
        return None
    from apps.records.services import RecordService, resolve_entity
    entity = resolve_entity(workspace_id, slug)
    rows = RecordService.list_records(
        workspace_id=workspace_id, member=member, entity=entity,
        filter_source={"field": relation_field, "op": "=", "value": str(record_id)})
    return {"title": cfg.get("title", "Line Items"), "columns": columns, "rows": rows}


def render(template: DocumentTemplate, *, workspace_id, record_id, member) -> bytes:
    """Render the template for one record → PDF bytes."""
    from apps.records.services import RecordService, resolve_entity
    from apps.reporting.pdf import render_pdf
    from apps.reporting.services import workspace_watermark

    entity = resolve_entity(workspace_id, template.entity_slug)
    record = RecordService.retrieve_record(
        workspace_id=workspace_id, member=member, entity=entity, record_id=record_id)

    metrics = []
    for block in template.blocks or []:
        field = block.get("field")
        if field:
            metrics.append({"label": block.get("label", field), "value": record.get(field)})

    tables = []
    line_table = _line_item_table(template, workspace_id, member, record_id)
    if line_table:
        tables.append(line_table)

    page = template.page_config or {}
    return render_pdf({
        "title": page.get("title") or template.name,
        "subtitle": page.get("subtitle", ""),
        "watermark": workspace_watermark(workspace_id),
        "metrics": metrics,
        "tables": tables,
    })
