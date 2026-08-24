"""
Trigger dispatcher (PROJECT_HANDBOOK.md §21.4).

``dispatch_record_event`` is called by ``RecordService`` after every create/update/
delete. It registers a ``transaction.on_commit`` callback so workflows fire only
once the record write is durably committed (and so the engine reads committed data).

In tests, wrap the record op in ``django_capture_on_commit_callbacks(execute=True)``
to make the callback run, or call ``run_record_event`` directly for synchronous
dispatch.
"""
from __future__ import annotations

from django.db import transaction

from .models import WorkflowDefinition
from .services import WorkflowService


def dispatch_record_event(*, event_type, entity_slug, record_id, record_data,
                          workspace_id, entity_id=None, actor_id=None,
                          changed_fields=None) -> None:
    """Schedule workflow dispatch for a record event (fires post-commit)."""
    record = dict(record_data or {})
    record.setdefault("entity_slug", entity_slug)
    if changed_fields is not None:
        record["__changed_fields__"] = list(changed_fields)
    if actor_id is not None:
        record["__actor_id__"] = str(actor_id)

    def _fire():
        run_record_event(
            event_type=event_type, entity_slug=entity_slug, entity_id=entity_id,
            record_id=record_id, record=record, workspace_id=workspace_id,
            actor_id=actor_id)

    transaction.on_commit(_fire)


def run_record_event(*, event_type, entity_slug, record_id, record, workspace_id,
                     entity_id=None, actor_id=None) -> list:
    """Match active workflows and fire them now (synchronous). Returns run ids."""
    defs = WorkflowDefinition.objects.filter(
        workspace_id=workspace_id, trigger_type=event_type, status="active")
    runs = []
    for wf in defs:
        if wf.entity_id and entity_id and wf.entity_id != entity_id:
            continue
        cfg_slug = (wf.trigger_config or {}).get("entity_slug")
        if cfg_slug and cfg_slug != entity_slug:
            continue
        if not WorkflowService.evaluate_trigger(wf, event_type, record):
            continue
        context = {"record": record, "record_id": str(record_id),
                   "entity_slug": entity_slug, "event_type": event_type}
        run = WorkflowService.trigger_workflow(
            workflow_id=wf.id, record_id=record_id, context=context,
            workspace_id=workspace_id, initiated_by=actor_id, trigger_type=event_type)
        runs.append(run.id)
    return runs
