"""
RBAC + ABAC permission engine (master spec §14 / PROJECT_HANDBOOK.md §6.5).

Two layers, evaluated before any data is touched (RLS is the third, DB-level
backstop):

  RBAC  — system role defaults + custom Role/Permission rows, explicit deny wins,
          parent-role inheritance.
  ABAC  — per-record attribute conditions (``{field, op, value}`` with ``$user.*``
          substitution), evaluated on a record and injected as NQL filters for lists.

Field-level masking (FieldPermission / DataMaskingRule) is applied to output.
"""
from __future__ import annotations

from django.db.models import Q

from .models import DataMaskingRule, FieldPermission, Permission, Role

ALL_ACTIONS = {"create", "read", "update", "delete", "restore", "export", "import"}
SYSTEM_ROLE_ACTIONS = {
    "owner": set(ALL_ACTIONS),
    "admin": set(ALL_ACTIONS),
    "member": {"create", "read", "update", "delete", "restore"},
    "viewer": {"read"},
    "portal": set(),
}


class PermissionError(Exception):
    """Raised (optionally) when a permission check fails."""


# ── role resolution ─────────────────────────────────────────────────────────
def _role_chain_ids(member) -> list:
    """Custom role id + its parent chain (inheritance), cycle-safe."""
    if not getattr(member, "custom_role_id", None):
        return []
    ids, seen = [], set()
    role = Role.objects.filter(id=member.custom_role_id).first()
    while role and role.id not in seen:
        seen.add(role.id)
        ids.append(role.id)
        role = role.parent_role
    return ids


def _matching_perms(member, entity, action) -> list:
    role_ids = _role_chain_ids(member)
    if not role_ids:
        return []
    return list(
        Permission.objects.filter(
            role_id__in=role_ids,
            workspace_id=entity.workspace_id,
            resource_type="entity",
        )
        .filter(Q(resource_id=entity.id) | Q(resource_id__isnull=True))
        .filter(Q(action=action) | Q(action="*"))
    )


# ── ABAC condition evaluation ────────────────────────────────────────────────
def _subst(value, member):
    if value in ("$user.id", "$me"):
        return str(member.user_id)
    if value == "$user.member_id":
        return str(member.id)
    return value


def _eval_condition(cond, record, member) -> bool:
    field = cond.get("field")
    op = (cond.get("op") or "=").lower()
    rhs = _subst(cond.get("value"), member)
    lhs = record.get(field)
    if op == "is null":
        return lhs is None
    if op == "is not null":
        return lhs is not None
    if op == "in":
        return str(lhs) in [str(v) for v in (rhs or [])]
    if op == "not in":
        return str(lhs) not in [str(v) for v in (rhs or [])]
    if op == "contains":
        return rhs is not None and str(rhs) in str(lhs or "")
    if lhs is None:
        return False
    if op == "=":
        return str(lhs) == str(rhs)
    if op == "!=":
        return str(lhs) != str(rhs)
    try:
        lf, rf = float(lhs), float(rhs)
    except (TypeError, ValueError):
        return False
    return {">": lf > rf, ">=": lf >= rf, "<": lf < rf, "<=": lf <= rf}.get(op, False)


def _matches(conditions, record, member) -> bool:
    return all(_eval_condition(c, record, member) for c in conditions)


# ── public API ───────────────────────────────────────────────────────────────
def check(member, entity, action) -> bool:
    """Entity-level RBAC gate (no specific record). Unconditioned deny wins.

    A member assigned a scoped custom role is governed *solely* by that role's grants
    (explicit + wildcard) — there is no permissive system-role fallback — so e.g. a
    ``teacher`` sees only the entities their role grants, not every entity in the
    workspace. Owners/admins always keep their full system-role access (even with a
    custom role), and a plain member with no custom role still uses the system default.
    """
    role = getattr(member, "role", "")
    perms = _matching_perms(member, entity, action)
    if any(p.is_deny and not p.conditions for p in perms):
        return False
    if any(not p.is_deny for p in perms):
        return True
    if getattr(member, "custom_role_id", None) and role not in ("owner", "admin"):
        return False
    return action in SYSTEM_ROLE_ACTIONS.get(role, set())


def check_record(member, entity, action, record: dict) -> bool:
    """RBAC + ABAC for a specific record."""
    if not check(member, entity, action):
        return False
    perms = _matching_perms(member, entity, action)
    # conditioned deny that matches this record → deny
    for p in perms:
        if p.is_deny and p.conditions and _matches(p.conditions, record, member):
            return False
    allows = [p for p in perms if not p.is_deny]
    if any(not p.conditions for p in allows):
        return True
    conditioned = [p for p in allows if p.conditions]
    if conditioned:
        return any(_matches(p.conditions, record, member) for p in conditioned)
    # no matching custom allow ⇒ a scoped custom-role member is denied; others use the system role
    role = getattr(member, "role", "")
    if getattr(member, "custom_role_id", None) and role not in ("owner", "admin"):
        return False
    return action in SYSTEM_ROLE_ACTIONS.get(role, set())


def require(member, entity, action, record: dict | None = None) -> None:
    """Raise PermissionError if not allowed."""
    ok = check_record(member, entity, action, record) if record is not None else check(member, entity, action)
    if not ok:
        raise PermissionError(f"Not permitted to {action} {entity.slug}")


def abac_list_conditions(member, entity, action="read"):
    """Return NQL filter conditions restricting a list to ABAC-allowed records,
    or ``None`` when unrestricted (RBAC governs)."""
    perms = _matching_perms(member, entity, action)
    allows = [p for p in perms if not p.is_deny]
    if not allows or any(not p.conditions for p in allows):
        return None
    groups = []
    for p in allows:
        conds = [{"field": c["field"], "op": (c.get("op") or "=").lower(),
                  "value": _subst(c.get("value"), member)} for c in p.conditions]
        groups.append({"op": "and", "conditions": conds})
    return {"op": "or", "conditions": groups} if groups else None


# ── field masking ────────────────────────────────────────────────────────────
def _mask_value(value, mask_type: str, pattern: str):
    if value is None:
        return None
    s = str(value)
    if mask_type == "full":
        return "*" * max(len(s), 4)
    if mask_type == "first_n_chars":
        n = int(pattern) if str(pattern).isdigit() else 2
        return s[:n] + "*" * max(len(s) - n, 0)
    if mask_type == "last_n_chars":
        n = int(pattern) if str(pattern).isdigit() else 4
        return "*" * max(len(s) - n, 0) + s[-n:]
    return "***"


def mask_record(member, entity, record: dict) -> dict:
    """Drop non-readable fields and mask masked fields for *member*'s role."""
    if getattr(member, "role", "") in ("owner", "admin"):
        return record
    role_ids = _role_chain_ids(member)
    if not role_ids:
        return record
    # field_id -> slug
    slug_by_id = {str(fd_id): slug for fd_id, slug in
                  entity.fields.filter(is_deleted=False).values_list("id", "slug")}
    out = dict(record)
    for fp in FieldPermission.objects.filter(role_id__in=role_ids, can_read=False,
                                             workspace_id=entity.workspace_id):
        slug = slug_by_id.get(str(fp.field_id))
        out.pop(slug, None)
    for rule in DataMaskingRule.objects.filter(role_id__in=role_ids,
                                               workspace_id=entity.workspace_id):
        slug = slug_by_id.get(str(rule.field_id))
        if slug in out:
            out[slug] = _mask_value(out[slug], rule.mask_type, rule.mask_pattern)
    return out
