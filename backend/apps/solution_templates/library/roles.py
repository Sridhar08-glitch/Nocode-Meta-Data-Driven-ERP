"""
Standard Role Library — role specs (manifest ``roles`` fragments).

Each role carries coarse capability grants expressed against resource_type="entity" with
``resource_id`` left to the applier to resolve (None = all entities of the solution, or a
named ``entity_slug``). The five standard roles mirror the spec: Administrator, Manager,
User, Approver, Auditor. They sit ALONGSIDE the built-in system roles (owner/admin/member/
viewer) — these are custom, solution-scoped roles.
"""


def _role(slug, name, description, actions, *, parent_slug=None):
    """actions → one wildcard-entity Permission per action (resource_id=None = all)."""
    return {
        "slug": slug, "name": name, "description": description, "parent_slug": parent_slug,
        "permissions": [{"resource_type": "entity", "action": a} for a in actions],
    }


ROLE_LIBRARY: dict[str, dict] = {
    "administrator": _role(
        "administrator", "Administrator", "Full control of the solution's data and config.",
        ["create", "read", "update", "delete", "export", "import", "share", "admin"]),
    "manager": _role(
        "manager", "Manager", "Manage records and team output.",
        ["create", "read", "update", "delete", "export"]),
    "user": _role(
        "user", "User", "Create and work day-to-day records.",
        ["create", "read", "update"]),
    "approver": _role(
        "approver", "Approver", "Read records and act on approvals.",
        ["read", "update"]),
    "auditor": _role(
        "auditor", "Auditor", "Read-only oversight and export.",
        ["read", "export"]),
}
