"""
Studio resolution (Phase 1.32).

- App switcher: published+active apps the caller may see (role-gated).
- Home layout: most-specific published layout — personal > role > app > workspace.
- Navigation: the published nav for the context (app → workspace fallback), with groups
  and items filtered to the caller's role tokens (permission-aware menu).

``role_tokens`` is the caller's identity set used for gating: the system role string
(owner/admin/…) plus every custom Role id in the inheritance chain, all as strings.
"""
from __future__ import annotations

from .models import Application, HomeLayout, Navigation


class StudioError(Exception):  # noqa: N818 — domain error
    pass


def role_tokens(member) -> set:
    """System role + custom-role chain ids (as strings) for gating."""
    from apps.permissions.services import _role_chain_ids
    tokens = {str(getattr(member, "role", "") or "")}
    tokens.update(str(r) for r in _role_chain_ids(member))
    tokens.discard("")
    return tokens


# Owner/admin always see every app, home layout and nav item, regardless of an
# item's role gating — mirrors the RBAC owner/admin bypass. Without this, an app
# scoped to a package's custom roles (e.g. School's teacher/principal) would be
# hidden from the workspace owner, who isn't assigned any of those custom roles.
_PRIVILEGED = {"owner", "admin"}


def _allowed(item_roles, tokens: set) -> bool:
    """An item/app with no role restriction is open; otherwise needs a matching token.
    Owner/admin bypass the gate entirely."""
    if not item_roles or (tokens & _PRIVILEGED):
        return True
    return bool({str(r) for r in item_roles} & tokens)


# ── applications ──────────────────────────────────────────────────────────────
def app_switcher(*, workspace_id, tokens: set) -> list[Application]:
    apps = Application.objects.filter(
        workspace_id=workspace_id, is_published=True, is_active=True).order_by("order", "name")
    return [a for a in apps if _allowed(a.role_ids, tokens)]


# ── home layouts ──────────────────────────────────────────────────────────────
def resolve_home_layout(*, workspace_id, user_id=None, role_ids=None, app_id=None):
    """Return the most-specific published HomeLayout for the caller, or None."""
    role_ids = {str(r) for r in (role_ids or [])}
    published = HomeLayout.objects.filter(workspace_id=workspace_id, is_published=True)

    personal = published.filter(scope="personal", target_id=user_id).first() if user_id else None
    if personal:
        return personal
    for layout in published.filter(scope="role"):
        if str(layout.target_id) in role_ids:
            return layout
    if app_id:
        app_layout = published.filter(scope="app", target_id=app_id).first()
        if app_layout:
            return app_layout
    return published.filter(scope="workspace").order_by("created_at").first()


# ── navigation ────────────────────────────────────────────────────────────────
def resolve_navigation(*, workspace_id, tokens: set, app_id=None) -> dict | None:
    """Pick the published nav for the context and filter it to the caller's roles."""
    published = Navigation.objects.filter(workspace_id=workspace_id, is_published=True)
    nav = None
    if app_id:
        nav = published.filter(scope="app", target_id=app_id).first()
    if nav is None:
        nav = published.filter(scope="workspace").order_by("created_at").first()
    if nav is None:
        return None

    groups = []
    for group in nav.tree or []:
        if not _allowed(group.get("roles"), tokens):
            continue
        items = [it for it in (group.get("items") or []) if _allowed(it.get("roles"), tokens)]
        if not items and not group.get("items"):
            # a deliberately empty group is kept; a group whose items were all filtered out is dropped
            groups.append({**group, "items": []})
        elif items:
            groups.append({**group, "items": items})
    return {"id": str(nav.id), "name": nav.name, "scope": nav.scope, "groups": groups}
