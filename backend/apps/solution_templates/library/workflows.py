"""
Standard Workflow Library — generic workflow templates (manifest ``workflows`` fragments).

Each is a reusable shape the Create-Solution Wizard binds to a concrete entity at compose
time (``entity_slug``). They use the existing workflow step types (approval, action_set_field,
action_send_notification, condition) so they run on the Phase 1.12 engine unchanged.
"""


def _wf(slug, name, trigger_type, steps, edges, *, entity_slug=None, trigger_config=None):
    return {
        "slug": slug, "name": name, "trigger_type": trigger_type,
        "trigger_config": trigger_config or {}, "entity_slug": entity_slug,
        "steps": steps, "edges": edges,
    }


# A linear two-step "start → approve" shape reused by the approval-style templates.
def _approval_steps(notify_template="approval_requested"):
    return (
        [
            {"slug": "start", "step_type": "condition", "name": "Start", "is_entry": True,
             "config": {}},
            {"slug": "approve", "step_type": "approval", "name": "Approval",
             "config": {}},
            {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
             "config": {"template_slug": notify_template}},
        ],
        [
            {"source": "start", "target": "approve"},
            {"source": "approve", "target": "notify"},
        ],
    )


_apr_steps, _apr_edges = _approval_steps()

WORKFLOW_LIBRARY: dict[str, dict] = {
    "approval": _wf("approval", "Approval", "record_created", _apr_steps, _apr_edges),
    "assignment": _wf(
        "assignment", "Assignment", "record_created",
        [{"slug": "assign", "step_type": "action_set_field", "name": "Auto-assign",
          "is_entry": True, "config": {"field": "status", "value": "open"}}],
        []),
    "escalation": _wf(
        "escalation", "Escalation", "schedule",
        [{"slug": "escalate", "step_type": "action_send_notification", "name": "Escalate",
          "is_entry": True, "config": {"template_slug": "escalation"}}],
        [], trigger_config={"cron": "0 * * * *"}),
    "review": _wf("review", "Review", "record_updated", *_approval_steps("review_requested")),
    "hiring": _wf("hiring", "Hiring", "record_created", *_approval_steps("hiring_started")),
    "onboarding": _wf(
        "onboarding", "Onboarding", "record_created",
        [{"slug": "welcome", "step_type": "action_send_notification", "name": "Welcome",
          "is_entry": True, "config": {"template_slug": "onboarding"}}],
        []),
    "offboarding": _wf(
        "offboarding", "Offboarding", "record_updated",
        [{"slug": "revoke", "step_type": "action_send_notification", "name": "Offboard",
          "is_entry": True, "config": {"template_slug": "offboarding"}}],
        []),
    "procurement_approval": _wf(
        "procurement_approval", "Procurement Approval", "record_created",
        *_approval_steps("procurement_approval")),
    "invoice_approval": _wf(
        "invoice_approval", "Invoice Approval", "record_created",
        *_approval_steps("invoice_approval")),
}
