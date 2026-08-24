"""
Workflow step executors (PROJECT_HANDBOOK.md §21.2).

One executor per step type. Each has the signature
``executor(step, run, ctx, member) -> dict`` and returns ``output_data`` that is
merged into the run context and persisted on the :class:`WorkflowStepRun`.

A return value containing ``HALT_KEY`` tells the engine *not* to auto-complete the
step — the run pauses until an external event resumes it (``approval`` waits for a
decision, ``wait`` waits for its resume task). Everything else auto-advances along
the graph edges.

Collaborators that belong to later phases (Notifications 1.13, Approvals 1.18,
SLA 1.19, Integrations 1.21) are reached through thin, monkeypatch-friendly
wrappers that degrade gracefully when those services are not yet wired — the
executor itself is always fully implemented.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass

from apps.computed.services import ComputedError, safe_eval
from apps.nql.services import execute_nql

from . import conditions
from .events import emit_workflow_event

HALT_KEY = "__halt__"


# ── actor / entity resolution ────────────────────────────────────────────────
@dataclass
class SystemMember:
    """Synthetic workspace member used when the engine acts autonomously.

    Carries the attributes :mod:`apps.permissions.services` reads. Automation runs
    with ``owner`` authority; record-level RBAC/ABAC + RLS still apply at the DAL.
    """
    user_id: uuid.UUID
    id: uuid.UUID
    role: str = "owner"
    custom_role_id = None


def member_for_run(run) -> SystemMember:
    actor = run.initiated_by or uuid.UUID(int=0)
    return SystemMember(user_id=actor, id=actor)


def _entity_by_id(entity_id):
    from apps.metadata.models import EntityDefinition
    return EntityDefinition.objects.filter(id=entity_id).first()


def _entity_by_slug(workspace_id, slug):
    from apps.metadata.models import EntityDefinition
    return EntityDefinition.objects.filter(workspace_id=workspace_id, slug=slug).first()


def _trigger_entity(run):
    if run.entity_id:
        return _entity_by_id(run.entity_id)
    slug = (run.context or {}).get("entity_slug")
    if slug:
        return _entity_by_slug(run.workspace_id, slug)
    return None


def _record_view(run, ctx) -> dict:
    """Flat record dict for condition evaluation: trigger record + scalar context."""
    rec = dict(ctx.get("record") or {})
    for k, v in ctx.items():
        if not isinstance(v, (dict | list)):
            rec.setdefault(k, v)
    return rec


def _resolve(value, ctx, run):
    return conditions.resolve_value(value, ctx, workspace_id=run.workspace_id,
                                    user_id=run.initiated_by)


def _resolve_map(mapping, ctx, run):
    return conditions.resolve_mapping(mapping, ctx, workspace_id=run.workspace_id,
                                      user_id=run.initiated_by)


# ── optional, monkeypatch-friendly collaborator seams ────────────────────────
def _send_notification(*, workspace_id, recipient_id, channel, template_slug,
                       context, member):
    """Dispatch through NotificationService when present (Phase 1.13)."""
    try:
        from apps.notifications.services import NotificationService
    except Exception:  # noqa: BLE001 — service module is empty until Phase 1.13
        return {"dispatched": False, "reason": "notifications_unavailable"}
    if not hasattr(NotificationService, "send"):
        return {"dispatched": False, "reason": "notifications_unavailable"}
    NotificationService.send(
        recipient_id=recipient_id, recipient_type="member",
        template_slug=template_slug, context=context,
        workspace_id=workspace_id, channels=[channel])
    return {"dispatched": True, "channel": channel}


def _http_post(url, body, headers, timeout=10):
    """Outbound HTTP POST. Isolated so tests can monkeypatch without a network."""
    import requests
    resp = requests.post(url, data=body, headers=headers, timeout=timeout)
    out = {"status": resp.status_code}
    try:
        out["body"] = resp.json()
    except Exception:  # noqa: BLE001
        out["body"] = resp.text
    return out


def _create_approval(*, workspace_id, process_id, record_id, entity_slug,
                     requested_by, workflow_run_id, step_run_id, context):
    try:
        from apps.approvals.services import ApprovalService
    except Exception:  # noqa: BLE001 — Phase 1.18
        return None
    if not hasattr(ApprovalService, "create_request"):
        return None
    try:
        req = ApprovalService.create_request(
            process_id=process_id, record_id=record_id, entity_slug=entity_slug,
            requested_by=requested_by, workspace_id=workspace_id,
            workflow_run_id=workflow_run_id, step_run_id=step_run_id, context=context)
    except Exception:  # noqa: BLE001 — no/invalid process ⇒ halt for manual external resolution
        return None
    return getattr(req, "id", None)


def _sla_call(method, *, record_id, entity_slug, workspace_id):
    try:
        from apps.sla.services import SLAService
    except Exception:  # noqa: BLE001 — Phase 1.19
        return {"applied": False, "reason": "sla_unavailable"}
    fn = getattr(SLAService, method, None)
    if fn is None:
        return {"applied": False, "reason": "sla_unavailable"}
    fn(record_id=record_id, workspace_id=workspace_id)
    return {"applied": True}


# ── record actions ───────────────────────────────────────────────────────────
def exec_create_record(step, run, ctx, member):
    from apps.records.services import RecordService, resolve_entity
    cfg = step.config or {}
    slug = cfg.get("entity_slug") or (ctx.get("entity_slug"))
    if not slug:
        ent = _trigger_entity(run)
        slug = ent.slug if ent else None
    if not slug:
        raise ExecutorError("create_record requires entity_slug")
    entity = resolve_entity(run.workspace_id, slug)
    data = _resolve_map(cfg.get("data") or {}, ctx, run)
    rec = RecordService.create_record(workspace_id=run.workspace_id, member=member,
                                      entity=entity, data=data)
    return {"created_id": str(rec.get("id")), "entity_slug": slug}


def _target_record(step, run, ctx):
    """Resolve the (entity, record_id) a record-action step operates on. ``record_id`` may be a
    ``{{record.field}}`` template, so a workflow can act on a RELATED record (e.g. a parent record
    reached through a lookup field) — not only its own trigger record. A plain value passes
    through ``_resolve`` unchanged."""
    cfg = step.config or {}
    raw = cfg.get("record_id")
    rid = (_resolve(raw, ctx, run) if raw else None) or run.record_id or ctx.get("record_id")
    slug = cfg.get("entity_slug")
    entity = _entity_by_slug(run.workspace_id, slug) if slug else _trigger_entity(run)
    return entity, rid


def exec_update_record(step, run, ctx, member):
    from apps.records.services import RecordService, resolve_entity
    cfg = step.config or {}
    entity, rid = _target_record(step, run, ctx)
    if entity is None or not rid:
        raise ExecutorError("update_record requires a target record")
    entity = resolve_entity(run.workspace_id, entity.slug)
    data = _resolve_map(cfg.get("data") or {}, ctx, run)
    RecordService.update_record(workspace_id=run.workspace_id, member=member,
                                entity=entity, record_id=rid, data=data)
    return {"updated_id": str(rid), "fields": list(data.keys())}


def exec_delete_record(step, run, ctx, member):
    from apps.records.services import RecordService, resolve_entity
    entity, rid = _target_record(step, run, ctx)
    if entity is None or not rid:
        raise ExecutorError("delete_record requires a target record")
    entity = resolve_entity(run.workspace_id, entity.slug)
    RecordService.delete_record(workspace_id=run.workspace_id, member=member,
                                entity=entity, record_id=rid)
    return {"deleted_id": str(rid)}


def exec_set_field(step, run, ctx, member):
    from apps.records.services import RecordService, resolve_entity
    cfg = step.config or {}
    field = cfg.get("field")
    if not field:
        raise ExecutorError("set_field requires 'field'")
    entity, rid = _target_record(step, run, ctx)
    if entity is None or not rid:
        raise ExecutorError("set_field requires a target record")
    entity = resolve_entity(run.workspace_id, entity.slug)
    value = _resolve(cfg.get("value"), ctx, run)
    RecordService.update_record(workspace_id=run.workspace_id, member=member,
                                entity=entity, record_id=rid, data={field: value})
    return {"field": field, "value": value}


def exec_assign(step, run, ctx, member):
    from apps.records.services import RecordService, resolve_entity
    cfg = step.config or {}
    field = cfg.get("field", "assigned_to")
    value = _resolve(cfg.get("value") or cfg.get("user_id") or cfg.get("assignee"), ctx, run)
    entity, rid = _target_record(step, run, ctx)
    if entity is None or not rid:
        raise ExecutorError("assign requires a target record")
    entity = resolve_entity(run.workspace_id, entity.slug)
    RecordService.update_record(workspace_id=run.workspace_id, member=member,
                                entity=entity, record_id=rid, data={field: value})
    return {"assigned_field": field, "assignee": value}


def exec_add_tag(step, run, ctx, member):
    from apps.tagging import services as tagging
    cfg = step.config or {}
    entity, rid = _target_record(step, run, ctx)
    if entity is None or not rid:
        raise ExecutorError("add_tag requires a target record")
    slug = cfg.get("tag_slug") or cfg.get("slug")
    name = cfg.get("tag_name") or cfg.get("name") or slug
    if not slug:
        raise ExecutorError("add_tag requires 'tag_slug'")
    tag = tagging.create_tag(workspace_id=run.workspace_id, name=name, slug=slug,
                             color=cfg.get("color", "#6366f1"))
    tagging.attach(workspace_id=run.workspace_id, tag_id=tag.id,
                   entity_id=entity.id, record_id=rid, by=member.user_id)
    return {"tag_id": str(tag.id), "tag_slug": slug}


def exec_stage_transition(step, run, ctx, member):
    from apps.records.services import RecordService, resolve_entity
    cfg = step.config or {}
    field = cfg.get("stage_field", "stage")
    to_stage = _resolve(cfg.get("to_stage") or cfg.get("value"), ctx, run)
    entity, rid = _target_record(step, run, ctx)
    if entity is None or not rid:
        raise ExecutorError("stage_transition requires a target record")
    entity = resolve_entity(run.workspace_id, entity.slug)
    RecordService.update_record(workspace_id=run.workspace_id, member=member,
                                entity=entity, record_id=rid, data={field: to_stage})
    emit_workflow_event(event_type="record.stage_entered", workspace_id=run.workspace_id,
                        run_id=run.id, actor_id=member.user_id,
                        payload={"record_id": str(rid), "entity_slug": entity.slug,
                                 "stage": to_stage})
    return {"stage": to_stage, "field": field}


# ── messaging actions ─────────────────────────────────────────────────────────
def exec_send_email(step, run, ctx, member):
    cfg = step.config or {}
    recipient = _resolve(cfg.get("recipient") or cfg.get("recipient_id"), ctx, run)
    return _send_notification(
        workspace_id=run.workspace_id, recipient_id=recipient, channel="email",
        template_slug=cfg.get("template_slug", ""), context=ctx, member=member)


def exec_send_notification(step, run, ctx, member):
    cfg = step.config or {}
    recipient = _resolve(cfg.get("recipient") or cfg.get("recipient_id"), ctx, run)
    if not recipient:
        # Degrade gracefully (matches this module's collaborator-seam contract): a step with no
        # resolvable recipient is a no-op, never a crash that rolls back the whole run.
        return {"dispatched": False, "reason": "no_recipient"}
    return _send_notification(
        workspace_id=run.workspace_id, recipient_id=recipient, channel="in_app",
        template_slug=cfg.get("template_slug", ""), context=ctx, member=member)


def exec_send_webhook(step, run, ctx, member):
    cfg = step.config or {}
    url = _resolve(cfg.get("url"), ctx, run)
    if not url:
        raise ExecutorError("send_webhook requires 'url'")
    payload = {"event": cfg.get("event", "workflow.webhook"),
               "workspace_id": str(run.workspace_id),
               "run_id": str(run.id),
               "data": _resolve_map(cfg.get("payload") or {}, ctx, run)}
    body = json.dumps(payload, default=str)
    headers = {"Content-Type": "application/json"}
    secret = cfg.get("signing_secret")
    if secret:
        sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        headers["X-Nexus-Signature"] = f"sha256={sig}"
    result = _http_post(url, body, headers, timeout=cfg.get("timeout", 10))
    return {"webhook_status": result.get("status")}


def exec_call_api(step, run, ctx, member):
    cfg = step.config or {}
    connector_id = cfg.get("connector_id")
    method = (cfg.get("method") or "GET").upper()
    body = _resolve_map(cfg.get("body") or {}, ctx, run)
    if connector_id:
        try:
            from apps.integrations.models import HTTPConnector
            from apps.integrations.services import HTTPConnectorService
        except Exception:  # noqa: BLE001 — Phase 1.21
            HTTPConnectorService = None
        if HTTPConnectorService is not None and hasattr(HTTPConnectorService, "request"):
            connector = HTTPConnector.objects.filter(
                id=connector_id, workspace_id=run.workspace_id).first()
            if connector is not None:
                res = HTTPConnectorService.request(
                    connector, method, cfg.get("path", ""), body=body or None,
                    timeout=cfg.get("timeout", 10))
                key = cfg.get("into", "api_result")
                ctx[key] = res
                return {"status": res.get("status"), "into": key}
    url = _resolve(cfg.get("url"), ctx, run)
    if not url:
        raise ExecutorError("call_api requires 'url' or a usable connector_id")
    headers = {"Content-Type": "application/json"}
    result = _http_post(url, json.dumps(body, default=str), headers,
                        timeout=cfg.get("timeout", 10))
    key = cfg.get("into", "api_result")
    ctx[key] = result
    return {"status": result.get("status"), "into": key}


# ── sub-process / control actions ─────────────────────────────────────────────
def exec_run_workflow(step, run, ctx, member):
    from .services import WorkflowService
    cfg = step.config or {}
    child_id = cfg.get("workflow_id")
    if not child_id and cfg.get("workflow_slug"):
        child = _child_definition(run.workspace_id, cfg["workflow_slug"])
        child_id = child.id if child else None
    if not child_id:
        raise ExecutorError("run_workflow requires 'workflow_id' or 'workflow_slug'")
    child_ctx = _resolve_map(cfg.get("context") or {}, ctx, run) or dict(ctx)
    child_run = WorkflowService.trigger_workflow(
        workflow_id=child_id, record_id=run.record_id, context=child_ctx,
        workspace_id=run.workspace_id, initiated_by=member.user_id,
        parent_run_id=run.id)
    return {"child_run_id": str(child_run.id) if child_run else None}


def _child_definition(workspace_id, slug):
    from .models import WorkflowDefinition
    return WorkflowDefinition.objects.filter(workspace_id=workspace_id, slug=slug).first()


def exec_run_script(step, run, ctx, member):
    """Safe server "script": evaluate arithmetic/boolean expressions (NO eval()).

    config = {"assignments": {"out_key": "qty * price"}}. Expressions are parsed by
    the computed-fields safe AST evaluator (PROJECT_HANDBOOK.md §2 forbids raw user code).
    """
    cfg = step.config or {}
    record = _record_view(run, ctx)
    names = {k: v for k, v in record.items() if isinstance(v, (int | float))}
    out = {}
    for key, expr in (cfg.get("assignments") or {}).items():
        try:
            out[key] = safe_eval(str(expr), names)
        except ComputedError as exc:
            raise ExecutorError(f"run_script: {exc}") from exc
        ctx[key] = out[key]
    return {"assignments": out}


def exec_transform(step, run, ctx, member):
    """Map/compute context fields. ``{{path}}`` templates or safe expressions."""
    cfg = step.config or {}
    record = _record_view(run, ctx)
    names = {k: v for k, v in record.items() if isinstance(v, (int | float))}
    out = {}
    for target, spec in (cfg.get("mappings") or {}).items():
        if isinstance(spec, str) and spec.strip().startswith("{{"):
            out[target] = _resolve(spec, ctx, run)
        elif isinstance(spec, str):
            try:
                out[target] = safe_eval(spec, names)
            except ComputedError:
                out[target] = _resolve(spec, ctx, run)
        else:
            out[target] = _resolve(spec, ctx, run)
        ctx[target] = out[target]
    return {"transform": out}


def exec_condition(step, run, ctx, member):
    cfg = step.config or {}
    record = _record_view(run, ctx)
    matched = conditions.evaluate(
        cfg.get("condition_nql") or cfg.get("condition") or "", record,
        workspace_id=run.workspace_id, user_id=run.initiated_by,
        entity_slug=ctx.get("entity_slug", ""))
    return {"branch": "true" if matched else "false", "matched": matched}


def exec_nql_query(step, run, ctx, member):
    cfg = step.config or {}
    source = cfg.get("nql") or cfg.get("query")
    if not source:
        raise ExecutorError("nql_query requires 'nql' or 'query'")
    rows = execute_nql(workspace_id=run.workspace_id, source=source,
                       user_id=run.initiated_by)
    key = cfg.get("into", "query_result")
    ctx[key] = rows
    return {"into": key, "count": len(rows)}


def exec_loop(step, run, ctx, member):
    """Run a configured inner action once per item in a list.

    config = {"items": <list|"{{path}}">, "action": {"type": ..., "config": {...}}}.
    Each iteration exposes the item at ``ctx["loop_item"]``.
    """
    cfg = step.config or {}
    items = _resolve(cfg.get("items"), ctx, run)
    if not isinstance(items, list):
        items = []
    inner = cfg.get("action") or {}
    inner_type = inner.get("type")
    results = []
    if inner_type and inner_type in REGISTRY:
        inner_step = _InlineStep(inner_type, inner.get("config") or {})
        for item in items:
            ctx["loop_item"] = item
            results.append(REGISTRY[inner_type](inner_step, run, ctx, member))
        ctx.pop("loop_item", None)
    return {"iterations": len(items), "results": results}


def exec_parallel(step, run, ctx, member):
    """Marker step: fan-out is handled by the engine (all outgoing edges)."""
    return {"branch": "parallel"}


def exec_join(step, run, ctx, member):
    """Marker step: arrival counting is handled by the engine before dispatch."""
    return {"joined": True}


def exec_approval(step, run, ctx, member):
    cfg = step.config or {}
    entity = _trigger_entity(run)
    req_id = _create_approval(
        workspace_id=run.workspace_id, process_id=cfg.get("process_id"),
        record_id=run.record_id, entity_slug=entity.slug if entity else "",
        requested_by=member.user_id, workflow_run_id=run.id,
        step_run_id=ctx.get("__step_run_id__"), context=ctx)
    return {HALT_KEY: True, "approval_request_id": str(req_id) if req_id else None,
            "status": "waiting_approval"}


def exec_wait(step, run, ctx, member):
    from .tasks import resume_workflow_after_wait
    cfg = step.config or {}
    seconds = int(cfg.get("seconds", 0)) + int(cfg.get("minutes", 0)) * 60 \
        + int(cfg.get("hours", 0)) * 3600
    eta = _dt.datetime.now(_dt.UTC) + _dt.timedelta(seconds=seconds)
    # step_run id is set by the engine before dispatch (ctx carries it transiently)
    step_run_id = ctx.get("__step_run_id__")
    resume_workflow_after_wait.apply_async(
        args=[str(run.id), str(step_run_id)], eta=eta)
    return {HALT_KEY: True, "resume_at": eta.isoformat(), "status": "waiting"}


def exec_sla_pause(step, run, ctx, member):
    entity = _trigger_entity(run)
    return _sla_call("pause_record", record_id=run.record_id,
                     entity_slug=entity.slug if entity else "",
                     workspace_id=run.workspace_id)


def exec_sla_resume(step, run, ctx, member):
    entity = _trigger_entity(run)
    return _sla_call("resume_record", record_id=run.record_id,
                     entity_slug=entity.slug if entity else "",
                     workspace_id=run.workspace_id)


# ── accounting: post a balanced journal through the GL engine (reused, never duplicated) ──
def _as_date(value):
    from django.utils import timezone
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return _dt.date.fromisoformat(value.strip()[:10])
        except ValueError:
            pass
    return timezone.now().date()


def _journal_lines(cfg, ctx, run):
    """Build GLBus line dicts from step config: an explicit ``lines`` list, or the common
    two-line shorthand (account_debit / account_credit / amount). Account codes are static
    config; amounts may be ``{{record.field}}`` templates resolved from the run context. An
    optional per-line ``partner_ref`` (analytic dimension) is passed through to the ledger."""
    raw = cfg.get("lines")
    if raw:
        lines = []
        for ln in raw:
            line = {}
            if ln.get("account_code") is not None:
                line["account_code"] = str(ln["account_code"])
            if ln.get("account_id") is not None:
                line["account_id"] = str(ln["account_id"])
            line["debit"] = _resolve(ln.get("debit", 0), ctx, run) or 0
            line["credit"] = _resolve(ln.get("credit", 0), ctx, run) or 0
            if ln.get("memo"):
                line["memo"] = str(_resolve(ln["memo"], ctx, run) or "")
            dim = ln.get("partner_ref", ln.get("dimension"))
            if dim is not None:
                line["partner_ref"] = str(_resolve(dim, ctx, run) or "")
            lines.append(line)
        return lines
    amount = _resolve(cfg.get("amount", 0), ctx, run)
    dr, cr = cfg.get("account_debit"), cfg.get("account_credit")
    if dr is None or cr is None:
        raise ExecutorError(
            "post_journal requires 'posting_rule', 'lines', or "
            "account_debit + account_credit + amount")
    dim = cfg.get("partner_ref", cfg.get("dimension"))
    partner = str(_resolve(dim, ctx, run) or "") if dim is not None else ""
    return [
        {"account_code": str(dr), "debit": amount or 0, "credit": 0, "partner_ref": partner},
        {"account_code": str(cr), "debit": 0, "credit": amount or 0, "partner_ref": partner},
    ]


def exec_post_journal(step, run, ctx, member):
    """Post a balanced journal entry through ``apps.ledger`` (GLBus) — the platform's single
    accounting engine. No-code packages use this to turn a business document (a fee invoice, a
    sale, a folio) into real accounting WITHOUT shipping native code or duplicating the ledger.

    Three config modes, all metadata-driven (no package-specific fields):
      • ``posting_rule``: delegate to a configured ``PostingRule`` (reuses PostingRule +
        AccountingSettings) via ``GLBus.post_event`` — returns posted=False/no_posting_rule when
        no rule is configured, keeping packages decoupled.
      • ``lines``: an explicit balanced line list.
      • shorthand: ``account_debit`` + ``account_credit`` + ``amount``.

    Idempotent on (source_module, source_ref) — running the workflow twice never double-posts.
    Skips zero-value entries gracefully. Workspace isolation, numbering, audit + the
    ``ledger.journal.posted`` domain event are all handled inside GLBus (never re-implemented)."""
    from decimal import Decimal

    from apps.ledger.models import JournalEntry
    from apps.ledger.services import GLBus, LedgerError

    cfg = step.config or {}
    source_module = str(cfg.get("source_module", "workflow"))
    source_ref = str(_resolve(cfg.get("source_ref", ""), ctx, run) or "")

    # Idempotency: never double-post for the same (source_module, source_ref).
    if source_ref:
        existing = JournalEntry.objects.filter(
            workspace_id=run.workspace_id, source_module=source_module,
            source_ref=source_ref).exclude(status=JournalEntry.REVERSED).first()
        if existing is not None:
            return {"journal_entry_id": str(existing.id), "posted": False,
                    "reason": "already_posted"}

    memo = str(_resolve(cfg.get("memo", ""), ctx, run) or "")
    date = _as_date(_resolve(cfg.get("date"), ctx, run))
    currency = str(cfg.get("currency", "") or "")

    # Mode A — delegate to a configured PostingRule (reuses PostingRule + AccountingSettings).
    posting_rule = cfg.get("posting_rule")
    if posting_rule:
        rule_ctx = _resolve_map(cfg.get("context", {}) or {}, ctx, run)
        rule_ctx.setdefault("memo", memo)
        if currency:
            rule_ctx.setdefault("currency", currency)
        if source_ref:
            rule_ctx.setdefault("source_ref", source_ref)
        try:
            entry = GLBus.post_event(
                run.workspace_id, str(posting_rule), rule_ctx, date=date,
                source_module=source_module, source_ref=source_ref, actor_id=run.initiated_by)
        except LedgerError as exc:
            raise ExecutorError(f"post_journal failed: {exc}") from exc
        if entry is None:
            return {"posted": False, "reason": "no_posting_rule"}
        return {"journal_entry_id": str(entry.id), "posted": True}

    # Mode B/C — explicit lines or two-line shorthand.
    lines = _journal_lines(cfg, ctx, run)
    total = sum((Decimal(str(ln.get("debit", 0) or 0)) for ln in lines), Decimal("0"))
    if total == 0:
        return {"posted": False, "reason": "zero_amount"}
    try:
        entry = GLBus.post(
            run.workspace_id, date=date, lines=lines, memo=memo, currency=currency,
            source_module=source_module, source_ref=source_ref, actor_id=run.initiated_by)
    except LedgerError as exc:
        raise ExecutorError(f"post_journal failed: {exc}") from exc
    return {"journal_entry_id": str(entry.id), "posted": True, "amount": str(total)}


def exec_generate_document(step, run, ctx, member):
    """Render a metadata-defined document template to PDF for the triggering record and attach
    it to that record — reusing ``apps.document_templates.render`` (the single PDF render engine)
    and ``apps.documents.DocumentService`` (storage + audit + the ``document.uploaded`` /
    ``file.attached`` domain events). No-code packages use this to produce a document from any
    record WITHOUT shipping native code or duplicating rendering/storage. Config is fully
    metadata-driven:

      template_slug : the DocumentTemplate to render (required)
      record_id     : target record (resolvable; defaults to the trigger record)
      entity_slug   : override the template's bound entity (optional)
      filename      : output name (resolvable; defaults to ``<template>-<record>.pdf``)
      folder_id     : destination folder (optional)

    Idempotent on (record, filename): running the workflow twice never creates a duplicate.
    Workspace isolation + read permission are enforced inside the render (RecordService) and the
    document store."""
    import io

    from apps.document_templates.models import DocumentTemplate
    from apps.document_templates.services import render
    from apps.documents.models import Document
    from apps.documents.services import DocumentService
    from apps.records.services import resolve_entity

    cfg = step.config or {}
    slug = cfg.get("template_slug")
    if not slug:
        raise ExecutorError("generate_document requires 'template_slug'")
    template = DocumentTemplate.objects.filter(
        workspace_id=run.workspace_id, slug=slug, is_active=True).first()
    if template is None:
        raise ExecutorError(f"generate_document: document template {slug!r} not found")

    raw_rid = cfg.get("record_id")
    record_id = _resolve(raw_rid, ctx, run) if raw_rid else (run.record_id or ctx.get("record_id"))
    if not record_id:
        return {"generated": False, "reason": "no_record"}

    entity_slug = cfg.get("entity_slug") or template.entity_slug
    entity = resolve_entity(run.workspace_id, entity_slug) if entity_slug else None
    entity_id = entity.id if entity else None

    filename = str(_resolve(cfg.get("filename"), ctx, run) or f"{slug}-{record_id}.pdf")

    # Idempotency: a non-deleted document with this name already attached to this record → skip.
    existing = Document.objects.filter(
        workspace_id=run.workspace_id, record_id=record_id, name=filename,
        deleted_at__isnull=True).first()
    if existing is not None:
        return {"generated": False, "reason": "already_generated",
                "document_id": str(existing.id)}

    try:
        pdf = render(template, workspace_id=run.workspace_id, record_id=record_id, member=member)
    except Exception as exc:  # noqa: BLE001 — surface a render failure as an executor error
        raise ExecutorError(f"generate_document: render failed: {exc}") from exc

    doc = DocumentService.upload_document(
        file_obj=io.BytesIO(pdf), filename=filename, folder_id=cfg.get("folder_id"),
        entity_id=entity_id, record_id=record_id, uploaded_by=run.initiated_by,
        workspace_id=run.workspace_id, mime_type="application/pdf")
    return {"generated": True, "document_id": str(doc.id), "filename": filename}


def _credit_step(step, run, ctx, kind_override=None):
    """Shared body for the credit workflow steps — issue a credit through the Core Credit Engine
    (``apps.credits``). Idempotent per step run (``external_ref`` defaults to
    ``workflow:<run>:<step>``) so a retry never double-credits / double-posts."""
    from decimal import Decimal

    from apps.credits.services import CreditError, CreditService

    cfg = step.config or {}
    kind = kind_override or str(cfg.get("kind", "discount"))
    raw_amount = _resolve(cfg.get("amount"), ctx, run)
    try:
        amount = Decimal(str(raw_amount or 0))
    except (ValueError, TypeError, ArithmeticError):
        amount = Decimal("0")
    if amount <= 0:
        return {"applied": False, "reason": "zero_amount"}
    step_id = getattr(step, "id", "inline")
    external_ref = str(_resolve(cfg.get("external_ref"), ctx, run)
                       or f"workflow:{run.id}:{step_id}")
    try:
        note = CreditService.issue(
            workspace_id=run.workspace_id, kind=kind, amount=amount,
            subject_ref=str(_resolve(cfg.get("subject_ref"), ctx, run) or ""),
            applies_to_ref=str(_resolve(cfg.get("applies_to_ref"), ctx, run) or ""),
            reason=str(_resolve(cfg.get("reason", ""), ctx, run) or ""),
            external_ref=external_ref,
            debit_account=cfg.get("debit_account"), credit_account=cfg.get("credit_account"),
            currency=str(cfg.get("currency", "") or ""),
            date=_as_date(_resolve(cfg.get("date"), ctx, run)), actor_id=run.initiated_by)
    except CreditError as exc:
        raise ExecutorError(f"apply_credit failed: {exc}") from exc
    return {"applied": True, "credit_id": str(note.id), "number": note.number,
            "kind": note.kind, "amount": str(note.amount)}


def exec_apply_credit(step, run, ctx, member):
    """Apply a credit — discount / scholarship / waiver / credit_note / write_off — via the Core
    Credit Engine (``apps.credits``). No-code packages reduce a receivable WITHOUT shipping any
    crediting code: the balanced GL post, gapless number, idempotency, and ``credit.*`` event all
    live in the engine. ``kind`` (config) selects the credit type; defaults to ``discount``."""
    return _credit_step(step, run, ctx)


def exec_issue_refund(step, run, ctx, member):
    """Issue a refund (Dr revenue/refund, Cr cash) via the Core Credit Engine. Same config as
    ``action_apply_credit`` but ``kind`` is fixed to ``refund``."""
    return _credit_step(step, run, ctx, kind_override="refund")


def exec_create_installment_plan(step, run, ctx, member):
    """Create a due schedule (installments / payment plan) via the Core Collections Engine
    (``apps.collections``). No-code packages split a receivable into scheduled dues WITHOUT
    shipping scheduling code — numbering, the schedule build, reminders, late fees and dunning
    all live in the engine. Idempotent per step run via ``external_ref``."""
    from apps.collections_engine.services import CollectionsError, CollectionsService

    cfg = step.config or {}
    step_id = getattr(step, "id", "inline")
    external_ref = str(_resolve(cfg.get("external_ref"), ctx, run)
                       or f"workflow:{run.id}:{step_id}")
    def _int(key, default):
        try:
            return int(_resolve(cfg.get(key, default), ctx, run) or default)
        except (ValueError, TypeError):
            return default
    try:
        plan = CollectionsService.create_plan(
            workspace_id=run.workspace_id,
            total_amount=_resolve(cfg.get("total_amount"), ctx, run) or 0,
            num_installments=_int("num_installments", 1),
            start_date=_as_date(_resolve(cfg.get("start_date"), ctx, run))
            or _dt.datetime.now(tz=_dt.UTC).date(),
            frequency=str(_resolve(cfg.get("frequency", "monthly"), ctx, run) or "monthly"),
            interval_days=_int("interval_days", 0),
            subject_ref=str(_resolve(cfg.get("subject_ref"), ctx, run) or ""),
            source_document_ref=str(_resolve(cfg.get("source_document_ref"), ctx, run) or ""),
            notify_ref=str(_resolve(cfg.get("notify_ref"), ctx, run) or ""),
            grace_days=_int("grace_days", 0),
            late_fee_type=str(_resolve(cfg.get("late_fee_type", "none"), ctx, run) or "none"),
            late_fee_value=_resolve(cfg.get("late_fee_value"), ctx, run) or 0,
            currency=str(cfg.get("currency", "") or ""),
            external_ref=external_ref, actor_id=run.initiated_by)
    except CollectionsError as exc:
        raise ExecutorError(f"create_installment_plan failed: {exc}") from exc
    return {"plan_created": True, "plan_id": str(plan.id), "number": plan.number,
            "installments": plan.num_installments}


def exec_calculate_tax(step, run, ctx, member):
    """Compute tax via the Core Tax Engine (``apps.taxes``) and inject the result into the workflow
    context — the platform's single tax engine. No-code packages price a taxable document WITHOUT
    shipping any tax code: inclusive/exclusive, compound groups, exemptions and temporal rates all
    live in the engine (§ Gap G1). Config (all metadata-driven):

      amount       : the taxable amount (resolvable, required)
      tax_code     : a TaxCode code/id  (or)
      tax_group    : a TaxGroup code/id
      partner_ref  : the customer/vendor record (for exemption lookup)
      inclusive    : override tax-inclusive pricing
      on_date      : the rate-effective date
      result_key   : context key to store the result under (default ``tax``)

    Writes ``{result_key}`` = {net,total_tax,gross,components,…} into the run context so a following
    ``action_post_journal`` can post the full document (net + tax lines)."""
    from apps.taxes.services import TaxError, TaxService

    cfg = step.config or {}
    amount = _resolve(cfg.get("amount"), ctx, run)
    if amount in (None, ""):
        return {"calculated": False, "reason": "no_amount"}
    try:
        calc = TaxService.calculate(
            run.workspace_id, amount=amount,
            tax_code=(_resolve(cfg.get("tax_code"), ctx, run) or None),
            tax_group=(_resolve(cfg.get("tax_group"), ctx, run) or None),
            on_date=_as_date(_resolve(cfg.get("on_date"), ctx, run)),
            partner_ref=str(_resolve(cfg.get("partner_ref"), ctx, run) or ""),
            inclusive=cfg.get("inclusive"))
    except TaxError as exc:
        raise ExecutorError(f"calculate_tax failed: {exc}") from exc
    out = {"net": str(calc["net"]), "total_tax": str(calc["total_tax"]),
           "gross": str(calc["gross"]), "inclusive": calc["inclusive"], "exempt": calc["exempt"],
           "components": [{"code": c["code"], "rate": str(c["rate"]), "amount": str(c["amount"])}
                         for c in calc["components"]]}
    key = str(cfg.get("result_key", "tax") or "tax")
    if isinstance(ctx, dict):
        ctx[key] = out
    return {"calculated": True, **out}


def exec_post_tax(step, run, ctx, member):
    """Record the immutable tax subledger (``TaxTransaction`` — the basis of the tax return) and,
    when an ``offset_account`` is configured, post a balanced tax journal via ``GLBus`` — the Core
    Tax Engine. Idempotent on ``external_ref``. Config: amount|calculation, tax_code|tax_group,
    direction (output/input), source_module, source_ref, partner_ref, offset_account, on_date."""
    from apps.taxes.services import TaxError, TaxService

    cfg = step.config or {}
    step_id = getattr(step, "id", "inline")
    external_ref = str(_resolve(cfg.get("external_ref"), ctx, run)
                       or f"workflow:{run.id}:{step_id}")
    try:
        result = TaxService.post(
            run.workspace_id, amount=_resolve(cfg.get("amount"), ctx, run),
            tax_code=(_resolve(cfg.get("tax_code"), ctx, run) or None),
            tax_group=(_resolve(cfg.get("tax_group"), ctx, run) or None),
            direction=str(cfg.get("direction", "output") or "output"),
            source_module=str(cfg.get("source_module", "workflow")),
            source_ref=str(_resolve(cfg.get("source_ref", ""), ctx, run) or ""),
            partner_ref=str(_resolve(cfg.get("partner_ref"), ctx, run) or ""),
            currency=str(cfg.get("currency", "") or ""),
            offset_account=cfg.get("offset_account"),
            on_date=_as_date(_resolve(cfg.get("on_date"), ctx, run)),
            external_ref=external_ref, actor_id=run.initiated_by)
    except TaxError as exc:
        raise ExecutorError(f"post_tax failed: {exc}") from exc
    return result


def exec_reverse_tax(step, run, ctx, member):
    """Reverse a document's tax (a GL reversal + subledger reversal) via the Core Tax Engine — for
    credit notes / cancellations. Idempotent. Config: source_module + source_ref, or external_ref."""
    from apps.taxes.services import TaxError, TaxService

    cfg = step.config or {}
    try:
        return TaxService.reverse(
            run.workspace_id, source_module=str(cfg.get("source_module", "workflow")),
            source_ref=str(_resolve(cfg.get("source_ref", ""), ctx, run) or ""),
            external_ref=str(_resolve(cfg.get("external_ref", ""), ctx, run) or ""),
            reason=str(_resolve(cfg.get("reason", ""), ctx, run) or ""), actor_id=run.initiated_by)
    except TaxError as exc:
        raise ExecutorError(f"reverse_tax failed: {exc}") from exc


def exec_bank_transfer(step, run, ctx, member):
    """Post a transfer between own bank/cash accounts via the Core Cash Management engine
    (``apps.cash``) — a real cash movement that posts ONE GL entry (Dr dest / Cr source) through
    GLBus. Idempotent on ``external_ref``. Config: from_account, to_account (BankAccount ids), amount,
    transfer_date, memo."""
    from apps.cash.services import CashError, CashService

    cfg = step.config or {}
    step_id = getattr(step, "id", "inline")
    amount = _resolve(cfg.get("amount"), ctx, run)
    if amount in (None, ""):
        return {"transferred": False, "reason": "no_amount"}
    try:
        xfer = CashService.post_transfer(
            workspace_id=run.workspace_id,
            from_account=_resolve(cfg.get("from_account"), ctx, run),
            to_account=_resolve(cfg.get("to_account"), ctx, run), amount=amount,
            transfer_date=_as_date(_resolve(cfg.get("transfer_date"), ctx, run)),
            memo=str(_resolve(cfg.get("memo", ""), ctx, run) or ""),
            external_ref=str(_resolve(cfg.get("external_ref"), ctx, run)
                             or f"workflow:{run.id}:{step_id}"),
            actor_id=run.initiated_by)
    except CashError as exc:
        raise ExecutorError(f"bank_transfer failed: {exc}") from exc
    return {"transferred": True, "transfer_id": str(xfer.id), "number": xfer.number}


def exec_auto_reconcile(step, run, ctx, member):
    """Run deterministic auto-matching on a bank reconciliation via the Core Cash engine. Config:
    reconciliation_id, amount_tolerance, date_tolerance_days."""
    from apps.cash.services import CashError, MatchingService

    cfg = step.config or {}
    rec_id = _resolve(cfg.get("reconciliation_id"), ctx, run)
    if not rec_id:
        return {"reconciled": False, "reason": "no_reconciliation"}
    try:
        return MatchingService.auto_match(
            workspace_id=run.workspace_id, reconciliation_id=rec_id,
            amount_tolerance=_resolve(cfg.get("amount_tolerance", 0), ctx, run) or 0,
            date_tolerance_days=int(_resolve(cfg.get("date_tolerance_days", 5), ctx, run) or 5),
            actor_id=run.initiated_by)
    except CashError as exc:
        raise ExecutorError(f"auto_reconcile failed: {exc}") from exc


def exec_register_settlement_document(step, run, ctx, member):
    """Register an open item in the Core Settlement sub-ledger (``apps.settlement``) — an invoice/
    charge (debit) or a payment/credit/deposit (credit) — so it can be matched. No-code packages get
    invoice-matched aging + partial/split settlement WITHOUT shipping matching code. Idempotent on
    ``external_ref``. Config: partner_ref, direction (debit/credit), amount, doc_type, document_ref,
    document_date, due_date, account_code."""
    from apps.settlement.services import SettlementError, SettlementService

    cfg = step.config or {}
    step_id = getattr(step, "id", "inline")
    amount = _resolve(cfg.get("amount"), ctx, run)
    if amount in (None, ""):
        return {"registered": False, "reason": "no_amount"}
    try:
        doc = SettlementService.register_document(
            workspace_id=run.workspace_id,
            partner_ref=str(_resolve(cfg.get("partner_ref"), ctx, run) or ""),
            direction=str(cfg.get("direction", "debit") or "debit"), amount=amount,
            doc_type=str(cfg.get("doc_type", "invoice") or "invoice"),
            document_ref=str(_resolve(cfg.get("document_ref", ""), ctx, run) or ""),
            document_date=_as_date(_resolve(cfg.get("document_date"), ctx, run)),
            due_date=_as_date(_resolve(cfg.get("due_date"), ctx, run)),
            account_code=str(cfg.get("account_code", "") or ""),
            currency=str(cfg.get("currency", "") or ""),
            source_module=str(cfg.get("source_module", "workflow")),
            external_ref=str(_resolve(cfg.get("external_ref"), ctx, run)
                             or f"workflow:{run.id}:{step_id}"),
            actor_id=run.initiated_by)
    except SettlementError as exc:
        raise ExecutorError(f"register_settlement_document failed: {exc}") from exc
    return {"registered": True, "document_id": str(doc.id), "outstanding": str(doc.outstanding)}


def exec_auto_allocate(step, run, ctx, member):
    """Auto-match a partner's open credits to their oldest open debits (FIFO) via the Core Settlement
    engine. Config: partner_ref."""
    from apps.settlement.services import SettlementError, SettlementService

    cfg = step.config or {}
    partner = str(_resolve(cfg.get("partner_ref"), ctx, run) or "")
    if not partner:
        return {"allocated": False, "reason": "no_partner"}
    try:
        return SettlementService.auto_allocate(
            workspace_id=run.workspace_id, partner_ref=partner, actor_id=run.initiated_by)
    except SettlementError as exc:
        raise ExecutorError(f"auto_allocate failed: {exc}") from exc


def exec_create_revenue_schedule(step, run, ctx, member):
    """Create a deferred-revenue recognition schedule via the Core Revenue Engine (``apps.revenue``).
    No-code packages defer revenue WITHOUT shipping recognition code. Config: total_amount, method
    (straight_line/immediate/milestone), num_periods, start_date, frequency, source_module,
    source_ref, partner_ref, deferred_account, revenue_account. Idempotent on ``external_ref``."""
    from apps.revenue.services import RevenueError, RevenueService

    cfg = step.config or {}
    step_id = getattr(step, "id", "inline")
    external_ref = str(_resolve(cfg.get("external_ref"), ctx, run)
                       or f"workflow:{run.id}:{step_id}")
    total = _resolve(cfg.get("total_amount"), ctx, run)
    if total in (None, ""):
        return {"created": False, "reason": "no_amount"}

    def _int(key, default):
        try:
            return int(_resolve(cfg.get(key, default), ctx, run) or default)
        except (ValueError, TypeError):
            return default
    try:
        sched = RevenueService.create_schedule(
            workspace_id=run.workspace_id, total_amount=total,
            method=str(cfg.get("method", "straight_line") or "straight_line"),
            num_periods=_int("num_periods", 1),
            start_date=_as_date(_resolve(cfg.get("start_date"), ctx, run)),
            frequency=str(cfg.get("frequency", "monthly") or "monthly"),
            source_module=str(cfg.get("source_module", "workflow")),
            source_ref=str(_resolve(cfg.get("source_ref", ""), ctx, run) or ""),
            external_ref=external_ref,
            partner_ref=str(_resolve(cfg.get("partner_ref"), ctx, run) or ""),
            currency=str(cfg.get("currency", "") or ""),
            deferred_account=cfg.get("deferred_account"),
            revenue_account=cfg.get("revenue_account"), actor_id=run.initiated_by)
    except RevenueError as exc:
        raise ExecutorError(f"create_revenue_schedule failed: {exc}") from exc
    return {"created": True, "schedule_id": str(sched.id), "number": sched.number,
            "periods": sched.num_periods}


def exec_recognize_revenue(step, run, ctx, member):
    """Recognise due deferred revenue (post Dr Deferred / Cr Revenue per period) via the Core Revenue
    Engine. Config: schedule_id (optional — else all active), as_of (optional). Idempotent per line."""
    from apps.revenue.services import RevenueError, RevenueService

    cfg = step.config or {}
    try:
        return RevenueService.recognize_due(
            workspace_id=run.workspace_id,
            schedule_id=(_resolve(cfg.get("schedule_id"), ctx, run) or None),
            as_of=_as_date(_resolve(cfg.get("as_of"), ctx, run)), actor_id=run.initiated_by)
    except RevenueError as exc:
        raise ExecutorError(f"recognize_revenue failed: {exc}") from exc


def exec_guard(step, run, ctx, member):
    """Declarative cross-record validation guard (Platform Gap A) — the Workflow engine as the
    FIRST consumer of the reusable Core ``apps.guards.GuardService``. Resolves ``{{record.*}}``
    templates in the guard config (reusing the existing ``resolve_value``) so each guard queries
    records RELATED to the trigger record, then delegates the query/aggregate/compare to the
    domain-agnostic GuardService. Branches like ``condition``: ``true`` when all block-severity
    guards pass, ``false`` when a block guard fails — so edges route to confirm/reject paths.
    Warnings never block. The framework knows nothing about the domain (see apps/guards)."""
    from apps.guards.services import GuardError, GuardService

    cfg = step.config or {}
    # Resolve record/ctx templates recursively (resolve_value descends dict/list, exact-match {{…}}).
    guards = _resolve(cfg.get("guards", []) or [], ctx, run)
    source = str(cfg.get("source") or f"workflow:{run.id}:{getattr(step, 'id', 'inline')}")
    try:
        result = GuardService.evaluate(
            workspace_id=run.workspace_id, guards=guards, user_id=run.initiated_by, source=source,
            fail_fast=bool(cfg.get("fail_fast", False)), lock=bool(cfg.get("lock", False)))
    except GuardError as exc:
        raise ExecutorError(f"guard failed: {exc}") from exc
    return {"branch": "true" if result.passed else "false", "passed": result.passed,
            "failures": result.failures, "warnings": result.warnings}


def exec_aggregate(step, run, ctx, member):
    """Declarative cross-record aggregation + calculation + persistence (Platform Gap CG-2) — the
    Workflow engine as the FIRST consumer of the reusable Core ``apps.aggregation.AggregationService``
    (the compute-and-persist sibling of ``action_guard``). Resolves ``{{record.*}}`` templates in the
    measures/computes (reusing the existing ``resolve_value``) so each aggregate is scoped to the
    trigger record, delegates the query/aggregate/calculate to the domain-agnostic service, injects
    the outputs into the run context (under ``into``, default ``agg``), and — when ``target`` is set —
    PERSISTS them to a record via ``RecordService`` (the SAME path ``action_update_record`` uses, so a
    workflow can write to the trigger record OR a related record). Knows nothing about any domain."""
    from apps.aggregation.services import AggregationError, AggregationService
    from apps.records.services import RecordService, resolve_entity

    cfg = step.config or {}
    measures = _resolve(cfg.get("measures", []) or [], ctx, run)
    computes = _resolve(cfg.get("computes", []) or [], ctx, run)
    source = str(cfg.get("source") or f"workflow:{run.id}:{getattr(step, 'id', 'inline')}")
    try:
        result = AggregationService.compute(
            workspace_id=run.workspace_id, measures=measures, computes=computes,
            user_id=run.initiated_by, source=source)
    except AggregationError as exc:
        raise ExecutorError(f"aggregate failed: {exc}") from exc

    into = cfg.get("into", "agg")
    ctx[into] = result.outputs                       # downstream steps + target.data can read {{agg.*}}
    persisted = False
    target = cfg.get("target")
    if isinstance(target, dict) and target.get("data"):
        entity, rid = _target_record(_InlineStep("action_update_record", target), run, ctx)
        if entity is not None and rid:
            entity = resolve_entity(run.workspace_id, entity.slug)
            data = _resolve_map(target.get("data") or {}, ctx, run)
            RecordService.update_record(workspace_id=run.workspace_id, member=member,
                                        entity=entity, record_id=rid, data=data)
            persisted = True
    return {"outputs": result.outputs, "persisted": persisted, "errors": result.errors}


class ExecutorError(Exception):
    """Raised by an executor on a configuration / runtime problem (triggers retry)."""


@dataclass
class _InlineStep:
    """Lightweight stand-in for a WorkflowStep used by ``loop`` inner actions."""
    step_type: str
    config: dict


# ── registry: every model step type + every PROJECT_HANDBOOK.md §21.2 alias ────────────
REGISTRY = {
    # model STEP_TYPES (17)
    "action_update_record": exec_update_record,
    "action_create_record": exec_create_record,
    "action_delete_record": exec_delete_record,
    "action_send_email": exec_send_email,
    "action_send_notification": exec_send_notification,
    "action_send_webhook": exec_send_webhook,
    "action_call_api": exec_call_api,
    "action_run_workflow": exec_run_workflow,
    "action_run_script": exec_run_script,
    "action_assign": exec_assign,
    "action_add_tag": exec_add_tag,
    "action_post_journal": exec_post_journal,
    "action_generate_document": exec_generate_document,
    "action_wait": exec_wait,
    "condition": exec_condition,
    "approval": exec_approval,
    "loop": exec_loop,
    "parallel": exec_parallel,
    "join": exec_join,
    # spec aliases / extra executors
    "action_set_field": exec_set_field,
    "action_webhook": exec_send_webhook,
    "http_request": exec_call_api,
    "subworkflow": exec_run_workflow,
    "wait": exec_wait,
    "transform": exec_transform,
    "nql_query": exec_nql_query,
    "stage_transition": exec_stage_transition,
    "sla_pause": exec_sla_pause,
    "sla_resume": exec_sla_resume,
    "post_journal_entry": exec_post_journal,
    "accounting_post": exec_post_journal,
    "generate_document": exec_generate_document,
    # Credit Engine (F3) — reusable crediting steps for every package.
    "action_apply_credit": exec_apply_credit,
    "action_issue_refund": exec_issue_refund,
    "apply_credit": exec_apply_credit,
    "issue_refund": exec_issue_refund,
    # Collections Engine (F2) — reusable due-schedule step for every package.
    "action_create_installment_plan": exec_create_installment_plan,
    "create_installment_plan": exec_create_installment_plan,
    # Tax Engine (Gap G1) — reusable tax calc/post/reverse for every package (no package tax code).
    "action_calculate_tax": exec_calculate_tax,
    "action_post_tax": exec_post_tax,
    "action_reverse_tax": exec_reverse_tax,
    "calculate_tax": exec_calculate_tax,
    "post_tax": exec_post_tax,
    "reverse_tax": exec_reverse_tax,
    # Revenue Recognition Engine (F5) — reusable deferred-revenue for every package.
    "action_create_revenue_schedule": exec_create_revenue_schedule,
    "action_recognize_revenue": exec_recognize_revenue,
    "create_revenue_schedule": exec_create_revenue_schedule,
    "recognize_revenue": exec_recognize_revenue,
    # Settlement / Payment-Allocation Engine — reusable invoice↔payment matching for every package.
    "action_register_settlement_document": exec_register_settlement_document,
    "action_auto_allocate": exec_auto_allocate,
    "register_settlement_document": exec_register_settlement_document,
    "auto_allocate": exec_auto_allocate,
    # Cash Management & Bank Reconciliation (F8) — reusable transfers + matching for every package.
    "action_bank_transfer": exec_bank_transfer,
    "action_auto_reconcile": exec_auto_reconcile,
    "bank_transfer": exec_bank_transfer,
    "auto_reconcile": exec_auto_reconcile,
    # Guard Framework (Platform Gap A) — declarative cross-record validation for every package.
    "action_guard": exec_guard,
    "guard": exec_guard,
    # Aggregation Framework (Platform Gap CG-2) — cross-record aggregate+calc+persist for every package.
    "action_aggregate": exec_aggregate,
    "aggregate": exec_aggregate,
}


def get_executor(step_type: str):
    executor = REGISTRY.get(step_type)
    if executor is None:
        raise ExecutorError(f"No executor for step type {step_type!r}")
    return executor
