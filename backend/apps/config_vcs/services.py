"""
Config VCS — "Git for Business Configuration" (master spec §26 / Pillar 5).

Phase-1 scope (§34 step 15): commit + diff + rollback over Entities, Fields,
Business Rules and Permissions. Branch + three-way merge are Phase 3.

A commit snapshots the full config state, hashes it (sha), and stores a structural
diff from its parent. Rollback re-applies a prior snapshot's metadata through the
ORM (mutable attributes only — no destructive DDL in v1).
"""
from __future__ import annotations

import hashlib
import json

from django.db import transaction
from django.utils import timezone

from apps.metadata.models import EntityDefinition, FieldDefinition
from apps.permissions.models import Permission, Role
from apps.rules.models import BusinessRule

from .models import ConfigBranch, ConfigCommit, ConfigMergeRequest

KINDS = ("entities", "fields", "rules", "roles", "permissions")


class ConfigVCSError(Exception):
    pass


# ── snapshot ─────────────────────────────────────────────────────────────────
def snapshot_config(workspace_id) -> dict:
    entities = [{
        "id": str(e.id), "slug": e.slug, "name": e.name, "plural_name": e.plural_name,
        "description": e.description, "is_active": e.is_active, "settings": e.settings,
        "title_field_slug": e.title_field_slug,
    } for e in EntityDefinition.objects.filter(workspace_id=workspace_id).order_by("slug")]

    fields = [{
        "id": str(f.id), "entity_id": str(f.entity_id), "slug": f.slug, "name": f.name,
        "field_type": f.field_type, "is_promoted": f.is_promoted, "is_required": f.is_required,
        "is_unique": f.is_unique, "config": f.config, "order": f.order, "is_deleted": f.is_deleted,
    } for f in FieldDefinition.objects.filter(workspace_id=workspace_id).order_by("entity_id", "slug")]

    rules = [{
        "id": str(r.id), "slug": r.slug, "name": r.name, "entity_id": str(r.entity_id),
        "trigger_on": r.trigger_on, "condition_nql": r.condition_nql, "actions": r.actions,
        "priority": r.priority, "is_active": r.is_active,
    } for r in BusinessRule.objects.filter(workspace_id=workspace_id).order_by("slug")]

    permissions = [{
        "id": str(p.id), "role_id": str(p.role_id), "resource_type": p.resource_type,
        "resource_id": str(p.resource_id) if p.resource_id else None, "action": p.action,
        "is_deny": p.is_deny, "conditions": p.conditions,
    } for p in Permission.objects.filter(workspace_id=workspace_id).order_by("id")]
    roles = [{
        "id": str(r.id), "slug": r.slug, "name": r.name,
        "parent_role_id": str(r.parent_role_id) if r.parent_role_id else None, "is_active": r.is_active,
    } for r in Role.objects.filter(workspace_id=workspace_id).order_by("slug")]

    return {"entities": entities, "fields": fields, "rules": rules,
            "roles": roles, "permissions": permissions}


def _sha(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _diff(old: dict, new: dict) -> dict:
    out = {}
    for kind in KINDS:
        old_by = {o["id"]: o for o in old.get(kind, [])}
        new_by = {o["id"]: o for o in new.get(kind, [])}
        added = [new_by[i] for i in new_by if i not in old_by]
        removed = [old_by[i] for i in old_by if i not in new_by]
        modified = [{"before": old_by[i], "after": new_by[i]}
                    for i in new_by if i in old_by and old_by[i] != new_by[i]]
        out[kind] = {"added": added, "removed": removed, "modified": modified}
    return out


# ── operations ───────────────────────────────────────────────────────────────
def commit(*, workspace_id, message, author_id=None, branch="main") -> ConfigCommit:
    payload = snapshot_config(workspace_id)
    branch_obj = ConfigBranch.objects.filter(workspace_id=workspace_id, name=branch).first()
    parent_sha = branch_obj.head_sha if branch_obj else ""
    parent = (ConfigCommit.objects.filter(workspace_id=workspace_id, sha=parent_sha).first()
              if parent_sha else None)
    if parent and parent.payload == payload:
        raise ConfigVCSError("No configuration changes to commit.")
    # Commit sha depends on parent + content + message (git-like), so a rollback to a
    # previous *content* still produces a distinct commit.
    content_sha = _sha(payload)
    sha = hashlib.sha256(f"{parent_sha}:{content_sha}:{message}".encode()).hexdigest()
    parent_payload = parent.payload if parent else {}
    with transaction.atomic():
        c = ConfigCommit.objects.create(
            workspace_id=workspace_id, sha=sha, parent_sha=parent_sha, message=message,
            branch=branch, payload=payload, diff=_diff(parent_payload, payload), author_id=author_id)
        if branch_obj:
            branch_obj.head_sha = sha
            branch_obj.save(update_fields=["head_sha"])
        else:
            ConfigBranch.objects.create(workspace_id=workspace_id, name=branch, head_sha=sha,
                                        base_sha=parent_sha, is_default=(branch == "main"),
                                        created_by=author_id)
    return c


def get_commit(workspace_id, sha) -> ConfigCommit:
    c = ConfigCommit.objects.filter(workspace_id=workspace_id, sha=sha).first()
    if c is None:
        raise ConfigVCSError(f"Commit {sha[:8]!r} not found")
    return c


def diff_commits(*, workspace_id, sha_a, sha_b) -> dict:
    return _diff(get_commit(workspace_id, sha_a).payload, get_commit(workspace_id, sha_b).payload)


def list_commits(*, workspace_id, branch="main", limit=50):
    return list(ConfigCommit.objects.filter(workspace_id=workspace_id, branch=branch)
                .order_by("-created_at")[:limit])


def rollback(*, workspace_id, sha, author_id=None) -> ConfigCommit:
    """Restore entity/field/rule metadata to *sha*'s snapshot (mutable attrs only),
    then record a new commit capturing the rolled-back state."""
    target = get_commit(workspace_id, sha)
    payload = target.payload
    with transaction.atomic():
        for e in payload.get("entities", []):
            EntityDefinition.objects.filter(workspace_id=workspace_id, id=e["id"]).update(
                name=e["name"], plural_name=e["plural_name"], description=e["description"],
                is_active=e["is_active"], settings=e["settings"], title_field_slug=e["title_field_slug"])
        for f in payload.get("fields", []):
            FieldDefinition.objects.filter(workspace_id=workspace_id, id=f["id"]).update(
                name=f["name"], config=f["config"], is_required=f["is_required"],
                order=f["order"], is_deleted=f["is_deleted"])
        for r in payload.get("rules", []):
            BusinessRule.objects.filter(workspace_id=workspace_id, id=r["id"]).update(
                name=r["name"], condition_nql=r["condition_nql"], actions=r["actions"],
                priority=r["priority"], is_active=r["is_active"])
    return commit(workspace_id=workspace_id, message=f"Rollback to {sha[:8]}",
                  author_id=author_id, branch=target.branch)


# ── branches ─────────────────────────────────────────────────────────────────
def get_branch(workspace_id, name) -> ConfigBranch:
    b = ConfigBranch.objects.filter(workspace_id=workspace_id, name=name).first()
    if b is None:
        raise ConfigVCSError(f"Branch {name!r} not found")
    return b


def list_branches(*, workspace_id):
    return list(ConfigBranch.objects.filter(workspace_id=workspace_id).order_by("name"))


def create_branch(*, workspace_id, name, from_branch="main", from_sha=None,
                  created_by=None) -> ConfigBranch:
    """Create a branch pointing at *from_sha* (or *from_branch*'s head)."""
    if not name:
        raise ConfigVCSError("Branch name is required.")
    if ConfigBranch.objects.filter(workspace_id=workspace_id, name=name).exists():
        raise ConfigVCSError(f"Branch {name!r} already exists.")
    head = (get_commit(workspace_id, from_sha).sha if from_sha
            else get_branch(workspace_id, from_branch).head_sha)
    return ConfigBranch.objects.create(
        workspace_id=workspace_id, name=name, head_sha=head, base_sha=head,
        created_by=created_by)


# ── three-way merge ──────────────────────────────────────────────────────────
def _ancestry(workspace_id, sha) -> list[str]:
    """Ordered sha chain from *sha* back to the root via parent_sha."""
    chain, seen, cur = [], set(), sha
    while cur and cur not in seen:
        seen.add(cur)
        chain.append(cur)
        c = ConfigCommit.objects.filter(workspace_id=workspace_id, sha=cur).first()
        cur = c.parent_sha if c else ""
    return chain


def _merge_base(workspace_id, sha_a, sha_b):
    """Most-recent common ancestor of two commits, or None."""
    b_set = set(_ancestry(workspace_id, sha_b))
    for s in _ancestry(workspace_id, sha_a):
        if s in b_set:
            return s
    return None


def _payload_for(workspace_id, sha) -> dict:
    return get_commit(workspace_id, sha).payload if sha else {}


def three_way_merge(base: dict, source: dict, target: dict, resolutions=None):
    """Per-object 3-way merge. Returns ``(merged_payload, conflicts)``.

    *resolutions* maps ``"{kind}:{id}"`` → ``"source"`` | ``"target"`` to settle a
    conflict; unresolved divergent edits land in *conflicts* (target kept provisionally).
    """
    resolutions = resolutions or {}
    merged, conflicts = {}, []
    for kind in KINDS:
        b = {o["id"]: o for o in base.get(kind, [])}
        s = {o["id"]: o for o in source.get(kind, [])}
        t = {o["id"]: o for o in target.get(kind, [])}
        out = {}
        for i in set(b) | set(s) | set(t):
            bo, so, to = b.get(i), s.get(i), t.get(i)
            src_changed = so != bo
            tgt_changed = to != bo
            if src_changed and tgt_changed and so != to:
                key = f"{kind}:{i}"
                choice = resolutions.get(key)
                if choice == "source":
                    chosen = so
                elif choice == "target":
                    chosen = to
                else:
                    conflicts.append({"key": key, "kind": kind, "id": i,
                                      "base": bo, "source": so, "target": to})
                    chosen = to  # provisional until resolved
            elif src_changed:
                chosen = so
            else:
                chosen = to
            if chosen is not None:
                out[i] = chosen
        merged[kind] = list(out.values())
    return merged, conflicts


def _create_commit(*, workspace_id, branch, payload, message, parent_sha,
                   author_id=None, tags=None) -> ConfigCommit:
    """Create a commit from an explicit *payload* (vs. a live snapshot)."""
    content_sha = _sha(payload)
    sha = hashlib.sha256(f"{parent_sha}:{content_sha}:{message}".encode()).hexdigest()
    parent = (ConfigCommit.objects.filter(workspace_id=workspace_id, sha=parent_sha).first()
              if parent_sha else None)
    return ConfigCommit.objects.create(
        workspace_id=workspace_id, sha=sha, parent_sha=parent_sha, message=message,
        branch=branch, payload=payload, diff=_diff(parent.payload if parent else {}, payload),
        author_id=author_id, tags=tags or [])


# ── merge requests ───────────────────────────────────────────────────────────
def get_merge_request(workspace_id, mr_id) -> ConfigMergeRequest:
    mr = ConfigMergeRequest.objects.filter(workspace_id=workspace_id, id=mr_id).first()
    if mr is None:
        raise ConfigVCSError("Merge request not found.")
    return mr


def list_merge_requests(*, workspace_id, status=None):
    qs = ConfigMergeRequest.objects.filter(workspace_id=workspace_id)
    if status:
        qs = qs.filter(status=status)
    return list(qs.order_by("-created_at"))


def open_merge_request(*, workspace_id, source_branch, target_branch, title,
                       description="", opened_by) -> ConfigMergeRequest:
    if source_branch == target_branch:
        raise ConfigVCSError("Source and target branches must differ.")
    get_branch(workspace_id, source_branch)
    get_branch(workspace_id, target_branch)
    if not title:
        raise ConfigVCSError("Title is required.")
    return ConfigMergeRequest.objects.create(
        workspace_id=workspace_id, title=title, description=description,
        source_branch=source_branch, target_branch=target_branch,
        status="open", opened_by=opened_by)


def merge(*, workspace_id, mr_id, merged_by=None, resolutions=None):
    """Perform the 3-way merge for a merge request.

    Returns ``(merge_request, conflicts)``. With unresolved conflicts the MR is marked
    ``conflict`` and no commit is made. On success a merge commit is created on the
    target branch, its head advances, and the MR is marked ``merged``.
    """
    mr = get_merge_request(workspace_id, mr_id)
    if mr.status == "merged":
        raise ConfigVCSError("Merge request is already merged.")
    if mr.status == "closed":
        raise ConfigVCSError("Merge request is closed.")

    source = get_branch(workspace_id, mr.source_branch)
    target = get_branch(workspace_id, mr.target_branch)
    base_sha = _merge_base(workspace_id, source.head_sha, target.head_sha)
    merged_payload, conflicts = three_way_merge(
        _payload_for(workspace_id, base_sha),
        _payload_for(workspace_id, source.head_sha),
        _payload_for(workspace_id, target.head_sha),
        resolutions=resolutions,
    )
    if conflicts:
        mr.status = "conflict"
        mr.conflict_details = conflicts
        mr.save(update_fields=["status", "conflict_details", "updated_at"])
        return mr, conflicts

    with transaction.atomic():
        msg = f"Merge '{mr.source_branch}' into '{mr.target_branch}' (#{str(mr.id)[:8]})"
        c = _create_commit(
            workspace_id=workspace_id, branch=target.name, payload=merged_payload,
            message=msg, parent_sha=target.head_sha, author_id=merged_by, tags=["merge"])
        target.head_sha = c.sha
        target.save(update_fields=["head_sha"])
        mr.status = "merged"
        mr.merged_by = merged_by
        mr.merged_at = timezone.now()
        mr.merge_commit_sha = c.sha
        mr.conflict_details = []
        if resolutions:
            mr.resolution = resolutions
        mr.save(update_fields=["status", "merged_by", "merged_at", "merge_commit_sha",
                               "conflict_details", "resolution", "updated_at"])
    return mr, []


def resolve_merge_request(*, workspace_id, mr_id, resolutions, merged_by=None):
    """Apply conflict *resolutions* and re-attempt the merge."""
    if not isinstance(resolutions, dict) or not resolutions:
        raise ConfigVCSError("resolutions must be a non-empty object of {kind:id: choice}.")
    for choice in resolutions.values():
        if choice not in ("source", "target"):
            raise ConfigVCSError("Each resolution choice must be 'source' or 'target'.")
    return merge(workspace_id=workspace_id, mr_id=mr_id, merged_by=merged_by,
                 resolutions=resolutions)
