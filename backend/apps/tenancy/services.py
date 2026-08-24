"""
Workspace & Identity Administration service (P2.17 readiness remediation).

The tenant + identity lifecycle that was previously only reachable via the ORM is
exposed here as a single, audited, permission-gated service:

  * ``create_workspace`` — self-service tenant provisioning (the caller becomes owner).
  * ``update_workspace`` — workspace identity / plan / limits / settings.
  * member management — ``add_member`` (creates the user if absent), ``assign_role``,
    ``suspend_member`` / ``reactivate_member``, ``remove_member``.
  * ``transfer_ownership`` — owner → another active member.
  * ``admin_reset_password`` — admin-initiated password reset for a member.

Workspace/WorkspaceMember are RLS-exempt identity tables (membership is how RLS is
itself decided), so isolation is enforced here in-service: every workspace-scoped
operation resolves the workspace explicitly and verifies the caller's role.
"""
from __future__ import annotations

import uuid
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts import services as auth_services
from apps.accounts.crypto import generate_token, hash_token
from apps.accounts.models import User
from apps.eventstore.events import DomainEventData, DomainEventFactory

from .emails import send_invitation_email, send_member_invite_email
from .models import Workspace, WorkspaceInvitation, WorkspaceMember

ADMIN_ROLES = {"owner", "admin"}
ASSIGNABLE_ROLES = {"admin", "member", "viewer"}
INVITE_TTL = timedelta(days=7)
PURGE_TTL = timedelta(days=30)          # soft-deleted workspaces purge after this
PURGE_TOKEN_TTL = timedelta(minutes=30)  # hard-delete confirmation token lifetime


def _invitation_or_expire(invitation: WorkspaceInvitation) -> WorkspaceInvitation:
    """Lazily flip a past-due pending invitation to ``expired``."""
    if invitation.status == "pending" and invitation.expires_at <= timezone.now():
        invitation.status = "expired"
        invitation.save(update_fields=["status", "updated_at"])
    return invitation


class WorkspaceError(Exception):  # noqa: N818 — domain error, not an *Error wrapper
    """Raised on an invalid workspace/identity operation."""


class WorkspacePermissionError(WorkspaceError):
    """Raised when the caller lacks the required workspace role."""


def _emit(workspace_id, event_type, payload, actor_id=None):
    from apps.eventstore.models import DomainEvent
    agg = uuid.UUID(str(workspace_id))
    version = DomainEvent.objects.filter(
        aggregate_id=agg, aggregate_type="workspace").count() + 1
    DomainEventFactory.persist_one(DomainEventData(
        event_type=event_type, workspace_id=agg, aggregate_type="workspace",
        aggregate_id=agg, version=version, payload=payload,
        actor_id=uuid.UUID(str(actor_id)) if actor_id else uuid.UUID(int=0)))


def _unique_slug(base: str) -> str:
    base = slugify(base or "")[:50] or "workspace"
    slug, n = base, 1
    while Workspace.objects.filter(slug=slug).exists():
        n += 1
        slug = f"{base}-{n}"[:63]
    return slug


def _member(workspace, member_id) -> WorkspaceMember:
    m = WorkspaceMember.objects.filter(workspace=workspace, id=member_id).first()
    if m is None:
        raise WorkspaceError("Member not found.")
    return m


def _active_owner_count(workspace, exclude_id=None) -> int:
    qs = WorkspaceMember.objects.filter(workspace=workspace, role="owner", status="active")
    if exclude_id is not None:
        qs = qs.exclude(id=exclude_id)
    return qs.count()


class WorkspaceService:
    # ── tenant provisioning ────────────────────────────────────────────────────
    @staticmethod
    def create_workspace(*, user, name, slug=None, plan="free") -> Workspace:
        """Provision a new tenant. The creating user becomes its active owner."""
        name = (name or "").strip()
        if not name:
            raise WorkspaceError("Workspace name is required.")
        with transaction.atomic():
            workspace = Workspace.objects.create(
                name=name, slug=_unique_slug(slug or name), plan=plan, owner=user)
            WorkspaceMember.objects.create(
                workspace=workspace, user=user, role="owner", status="active",
                joined_at=timezone.now())
        _emit(workspace.id, "workspace.created",
              {"name": workspace.name, "slug": workspace.slug}, user.id)
        return workspace

    @staticmethod
    def get_role(workspace, user) -> str | None:
        m = WorkspaceMember.objects.filter(
            workspace=workspace, user=user, status="active").first()
        return m.role if m else None

    @staticmethod
    def require_admin(workspace, user) -> WorkspaceMember:
        m = WorkspaceMember.objects.filter(
            workspace=workspace, user=user, status="active").first()
        if m is None or m.role not in ADMIN_ROLES:
            raise WorkspacePermissionError("Admin privileges are required.")
        return m

    @staticmethod
    def require_owner(workspace, user) -> WorkspaceMember:
        m = WorkspaceMember.objects.filter(
            workspace=workspace, user=user, status="active").first()
        if m is None or m.role != "owner":
            raise WorkspacePermissionError("Owner privileges are required.")
        return m

    @staticmethod
    def update_workspace(*, workspace, actor_user, data) -> Workspace:
        """Update workspace identity (name/logo), plan and numeric limits, and merge
        ``settings``. Admin-gated; limit changes are owner-only."""
        member = WorkspaceService.require_admin(workspace, actor_user)
        fields = []
        for f in ("name", "logo_url", "plan"):
            if data.get(f) is not None:
                setattr(workspace, f, data[f])
                fields.append(f)
        if isinstance(data.get("settings"), dict):
            merged = dict(workspace.settings or {})
            merged.update(data["settings"])
            workspace.settings = merged
            fields.append("settings")
        limit_fields = ("max_members", "max_entities", "max_records", "max_storage_bytes")
        if any(data.get(f) is not None for f in limit_fields):
            if member.role != "owner":
                raise WorkspacePermissionError("Only the owner can change plan limits.")
            for f in limit_fields:
                if data.get(f) is not None:
                    setattr(workspace, f, int(data[f]))
                    fields.append(f)
        if fields:
            workspace.save(update_fields=[*set(fields), "updated_at"])
            _emit(workspace.id, "workspace.updated", {"fields": sorted(set(fields))},
                  actor_user.id)
        return workspace

    # ── member management ──────────────────────────────────────────────────────
    @staticmethod
    def list_members(*, workspace) -> list[WorkspaceMember]:
        return list(WorkspaceMember.objects.filter(workspace=workspace)
                    .select_related("user").order_by("role", "user__email"))

    @staticmethod
    def add_member(*, workspace, actor_user, email, full_name="", role="member"):
        """Seat a teammate. If no user has this email, an account is created
        (unusable password + a set-password link emailed). The membership is active
        immediately under the admin's authority. Returns ``(member, created_user)``."""
        WorkspaceService.require_admin(workspace, actor_user)
        if role not in ASSIGNABLE_ROLES:
            raise WorkspaceError(f"Role must be one of {sorted(ASSIGNABLE_ROLES)}.")
        email = (email or "").strip().lower()
        if not email:
            raise WorkspaceError("Email is required.")

        set_password_token = None
        with transaction.atomic():
            user = User.objects.filter(email=email).first()
            created_user = user is None
            if created_user:
                user = User.objects.create_user(
                    email=email, password=None, full_name=full_name, is_verified=True)
                user.set_unusable_password()
                user.save(update_fields=["password"])
            existing = WorkspaceMember.objects.filter(
                workspace=workspace, user=user).first()
            if existing and existing.status == "active":
                raise WorkspaceError("This user is already a member.")
            active_count = WorkspaceMember.objects.filter(
                workspace=workspace, status="active").count()
            if active_count >= workspace.max_members:
                raise WorkspaceError("Workspace member limit reached.")
            member = existing or WorkspaceMember(workspace=workspace, user=user)
            member.role = role
            member.status = "active"
            member.invited_by = actor_user.id
            member.joined_at = timezone.now()
            member.save()
            if created_user:
                set_password_token, _ = auth_services.create_password_reset_token(user)
        send_member_invite_email(workspace, user, role,
                                 set_password_token=set_password_token)
        _emit(workspace.id, "workspace.member.added",
              {"member_id": str(member.id), "email": email, "role": role,
               "created_user": created_user}, actor_user.id)
        return member, created_user

    @staticmethod
    def assign_role(*, workspace, actor_user, member_id, role=None, custom_role_id=...):
        """Change a member's system role and/or assign a custom permission Role."""
        WorkspaceService.require_admin(workspace, actor_user)
        member = _member(workspace, member_id)
        fields = []
        if role is not None:
            if role not in ASSIGNABLE_ROLES:
                raise WorkspaceError(
                    "Role must be admin/member/viewer (use transfer-ownership for owner).")
            if member.role == "owner" and _active_owner_count(workspace, member.id) == 0:
                raise WorkspaceError("Cannot demote the last owner; transfer ownership first.")
            member.role = role
            fields.append("role")
        if custom_role_id is not ...:
            member.custom_role_id = uuid.UUID(str(custom_role_id)) if custom_role_id else None
            fields.append("custom_role_id")
        if fields:
            member.save(update_fields=[*fields, "updated_at"])
            _emit(workspace.id, "workspace.member.role_changed",
                  {"member_id": str(member.id), "role": member.role}, actor_user.id)
        return member

    @staticmethod
    def suspend_member(*, workspace, actor_user, member_id) -> WorkspaceMember:
        """Deactivate a member (status=suspended) — they lose all workspace access
        (the tenant middleware only admits ``status="active"`` members)."""
        WorkspaceService.require_admin(workspace, actor_user)
        member = _member(workspace, member_id)
        if member.role == "owner" and _active_owner_count(workspace, member.id) == 0:
            raise WorkspaceError("Cannot suspend the last owner; transfer ownership first.")
        member.status = "suspended"
        member.save(update_fields=["status", "updated_at"])
        _emit(workspace.id, "workspace.member.suspended",
              {"member_id": str(member.id)}, actor_user.id)
        return member

    @staticmethod
    def reactivate_member(*, workspace, actor_user, member_id) -> WorkspaceMember:
        WorkspaceService.require_admin(workspace, actor_user)
        member = _member(workspace, member_id)
        member.status = "active"
        member.joined_at = member.joined_at or timezone.now()
        member.save(update_fields=["status", "joined_at", "updated_at"])
        _emit(workspace.id, "workspace.member.reactivated",
              {"member_id": str(member.id)}, actor_user.id)
        return member

    @staticmethod
    def remove_member(*, workspace, actor_user, member_id) -> None:
        WorkspaceService.require_admin(workspace, actor_user)
        member = _member(workspace, member_id)
        if member.role == "owner":
            raise WorkspaceError("Cannot remove an owner; transfer ownership first.")
        member.delete()
        _emit(workspace.id, "workspace.member.removed",
              {"member_id": str(member_id)}, actor_user.id)

    @staticmethod
    def transfer_ownership(*, workspace, actor_user, member_id) -> WorkspaceMember:
        """Make another active member the owner and demote the current owner to admin."""
        owner = WorkspaceService.require_owner(workspace, actor_user)
        target = _member(workspace, member_id)
        if target.status != "active":
            raise WorkspaceError("The new owner must be an active member.")
        if target.id == owner.id:
            return owner
        with transaction.atomic():
            target.role = "owner"
            target.save(update_fields=["role", "updated_at"])
            owner.role = "admin"
            owner.save(update_fields=["role", "updated_at"])
            workspace.owner = target.user
            workspace.save(update_fields=["owner", "updated_at"])
        _emit(workspace.id, "workspace.ownership_transferred",
              {"from_member": str(owner.id), "to_member": str(target.id)}, actor_user.id)
        return target

    @staticmethod
    def admin_reset_password(*, workspace, actor_user, member_id) -> WorkspaceMember:
        """Admin-initiated password reset: emails the member a reset link (the admin
        never sees or sets the password)."""
        WorkspaceService.require_admin(workspace, actor_user)
        member = _member(workspace, member_id)
        raw, _ = auth_services.create_password_reset_token(member.user)
        auth_services.send_password_reset_email(member.user, raw)
        _emit(workspace.id, "workspace.member.password_reset_sent",
              {"member_id": str(member.id)}, actor_user.id)
        return member

    # ── workspace lifecycle (archive / delete / restore) ───────────────────────
    @staticmethod
    def archive_workspace(*, workspace, actor_user) -> Workspace:
        """Owner-only: make the workspace dormant (is_active=False). Reversible via
        restore. Archived workspaces drop out of the active membership listing and
        the tenant middleware refuses them, but no data is removed."""
        WorkspaceService.require_owner(workspace, actor_user)
        workspace.is_active = False
        workspace.save(update_fields=["is_active", "updated_at"])
        _emit(workspace.id, "workspace.archived", {"slug": workspace.slug}, actor_user.id)
        return workspace

    @staticmethod
    def soft_delete_workspace(*, workspace, actor_user) -> Workspace:
        """Owner-only: soft-delete (sets ``deleted_at`` + deactivates). Recoverable
        until the retention window elapses, then a beat purges it permanently."""
        WorkspaceService.require_owner(workspace, actor_user)
        workspace.is_active = False
        workspace.deleted_at = timezone.now()
        workspace.save(update_fields=["is_active", "deleted_at", "updated_at"])
        _emit(workspace.id, "workspace.deleted",
              {"slug": workspace.slug,
               "purge_after": (timezone.now() + PURGE_TTL).isoformat()}, actor_user.id)
        return workspace

    @staticmethod
    def restore_workspace(*, workspace, actor_user) -> Workspace:
        """Owner-only: un-archive / un-delete a workspace (clears deleted_at + reactivates)."""
        WorkspaceService.require_owner(workspace, actor_user)
        workspace.is_active = True
        workspace.deleted_at = None
        workspace.save(update_fields=["is_active", "deleted_at", "updated_at"])
        _emit(workspace.id, "workspace.restored", {"slug": workspace.slug}, actor_user.id)
        return workspace

    @staticmethod
    def request_hard_delete(*, workspace, actor_user) -> str:
        """Owner-only: mint a one-time confirmation token for irreversible deletion.
        Only its hash + expiry are stored (on the workspace settings). Returns the raw
        token once."""
        WorkspaceService.require_owner(workspace, actor_user)
        raw = generate_token()
        settings_ = dict(workspace.settings or {})
        settings_["_purge"] = {
            "hash": hash_token(raw),
            "expires": (timezone.now() + PURGE_TOKEN_TTL).isoformat(),
        }
        workspace.settings = settings_
        workspace.save(update_fields=["settings", "updated_at"])
        _emit(workspace.id, "workspace.purge_requested", {"slug": workspace.slug}, actor_user.id)
        return raw

    @staticmethod
    def confirm_hard_delete(*, workspace, actor_user, token) -> None:
        """Owner-only: verify the confirmation token and permanently delete the
        workspace + its FK-cascaded identity rows (members, orgs, invitations…)."""
        WorkspaceService.require_owner(workspace, actor_user)
        purge = (workspace.settings or {}).get("_purge") or {}
        if not purge.get("hash") or purge["hash"] != hash_token(token):
            raise WorkspaceError("Invalid or missing confirmation token.")
        from django.utils.dateparse import parse_datetime
        exp = parse_datetime(purge.get("expires", ""))
        if exp is None or exp <= timezone.now():
            raise WorkspaceError("Confirmation token has expired; request deletion again.")
        ws_id, slug = workspace.id, workspace.slug
        # Emit the audit event BEFORE the row is gone (event store is independent).
        _emit(ws_id, "workspace.purged", {"slug": slug}, actor_user.id)
        workspace.delete()  # cascades members/orgs/teams/branches/invitations

    @staticmethod
    def list_archived(*, user):
        """Workspaces the user owns that are archived or soft-deleted (for the
        restore UI)."""
        memberships = WorkspaceMember.objects.filter(
            user=user, role="owner", status="active").select_related("workspace")
        out = []
        for m in memberships:
            w = m.workspace
            if (not w.is_active) or (w.deleted_at is not None):
                out.append(w)
        return out

    @staticmethod
    def purge_expired_workspaces() -> int:
        """Background cleanup: permanently delete workspaces whose retention window
        has elapsed. Returns the count purged."""
        cutoff = timezone.now() - PURGE_TTL
        expired = list(Workspace.objects.filter(deleted_at__lt=cutoff))
        for w in expired:
            _emit(w.id, "workspace.purged", {"slug": w.slug, "reason": "retention"}, None)
            w.delete()
        return len(expired)

    # ── invitation lifecycle ───────────────────────────────────────────────────
    @staticmethod
    def invite_member(*, workspace, actor_user, email, role="member"):
        """Send a pending invitation. Re-inviting an email with an open invitation
        refreshes its token + expiry (no duplicate rows). Returns ``(invitation, raw)``."""
        WorkspaceService.require_admin(workspace, actor_user)
        if role not in ASSIGNABLE_ROLES:
            raise WorkspaceError(f"Role must be one of {sorted(ASSIGNABLE_ROLES)}.")
        email = (email or "").strip().lower()
        if not email:
            raise WorkspaceError("Email is required.")
        existing_user = User.objects.filter(email=email).first()
        if existing_user and WorkspaceMember.objects.filter(
                workspace=workspace, user=existing_user, status="active").exists():
            raise WorkspaceError("That user is already an active member.")

        raw = generate_token()
        with transaction.atomic():
            inv = WorkspaceInvitation.objects.filter(
                workspace=workspace, email=email, status="pending").first()
            if inv is None:
                inv = WorkspaceInvitation(workspace=workspace, email=email)
            inv.role = role
            inv.status = "pending"
            inv.token_hash = hash_token(raw)
            inv.invited_by = actor_user.id
            inv.expires_at = timezone.now() + INVITE_TTL
            inv.responded_at = None
            inv.accepted_by = None
            inv.save()
        send_invitation_email(workspace, email, role, raw)
        _emit(workspace.id, "workspace.invitation.created",
              {"invitation_id": str(inv.id), "email": email, "role": role}, actor_user.id)
        return inv, raw

    @staticmethod
    def list_invitations(*, workspace, status=None):
        qs = WorkspaceInvitation.objects.filter(workspace=workspace)
        if status:
            qs = qs.filter(status=status)
        return [_invitation_or_expire(i) for i in qs.order_by("-created_at")]

    @staticmethod
    def _find_pending_by_token(raw_token) -> WorkspaceInvitation:
        inv = WorkspaceInvitation.objects.filter(token_hash=hash_token(raw_token)).first()
        if inv is None:
            raise WorkspaceError("Invitation not found.")
        inv = _invitation_or_expire(inv)
        if inv.status != "pending":
            raise WorkspaceError(f"This invitation is {inv.status}.")
        return inv

    @staticmethod
    def accept_invitation(*, user, raw_token) -> WorkspaceMember:
        """The authenticated invitee accepts: a membership is created/activated.
        The caller's email must match the invitation (prevents token sharing)."""
        inv = WorkspaceService._find_pending_by_token(raw_token)
        if user.email.lower() != inv.email.lower():
            raise WorkspacePermissionError("This invitation was sent to a different email.")
        workspace = inv.workspace
        with transaction.atomic():
            member = WorkspaceMember.objects.filter(workspace=workspace, user=user).first()
            if member and member.status == "active":
                inv.status = "accepted"
                inv.accepted_by = user.id
                inv.responded_at = timezone.now()
                inv.save(update_fields=["status", "accepted_by", "responded_at", "updated_at"])
                return member
            active_count = WorkspaceMember.objects.filter(
                workspace=workspace, status="active").count()
            if active_count >= workspace.max_members:
                raise WorkspaceError("Workspace member limit reached.")
            member = member or WorkspaceMember(workspace=workspace, user=user)
            member.role = inv.role
            member.status = "active"
            member.invited_by = inv.invited_by
            member.joined_at = timezone.now()
            member.save()
            inv.status = "accepted"
            inv.accepted_by = user.id
            inv.responded_at = timezone.now()
            inv.save(update_fields=["status", "accepted_by", "responded_at", "updated_at"])
        _emit(workspace.id, "workspace.invitation.accepted",
              {"invitation_id": str(inv.id), "member_id": str(member.id)}, user.id)
        return member

    @staticmethod
    def reject_invitation(*, user, raw_token) -> WorkspaceInvitation:
        inv = WorkspaceService._find_pending_by_token(raw_token)
        if user.email.lower() != inv.email.lower():
            raise WorkspacePermissionError("This invitation was sent to a different email.")
        inv.status = "rejected"
        inv.responded_at = timezone.now()
        inv.save(update_fields=["status", "responded_at", "updated_at"])
        _emit(inv.workspace_id, "workspace.invitation.rejected",
              {"invitation_id": str(inv.id)}, user.id)
        return inv

    @staticmethod
    def resend_invitation(*, workspace, actor_user, invitation_id):
        WorkspaceService.require_admin(workspace, actor_user)
        inv = WorkspaceInvitation.objects.filter(
            workspace=workspace, id=invitation_id).first()
        if inv is None:
            raise WorkspaceError("Invitation not found.")
        inv = _invitation_or_expire(inv)
        if inv.status not in ("pending", "expired"):
            raise WorkspaceError(f"Cannot resend a {inv.status} invitation.")
        raw = generate_token()
        inv.status = "pending"
        inv.token_hash = hash_token(raw)
        inv.expires_at = timezone.now() + INVITE_TTL
        inv.save(update_fields=["status", "token_hash", "expires_at", "updated_at"])
        send_invitation_email(workspace, inv.email, inv.role, raw)
        _emit(workspace.id, "workspace.invitation.resent",
              {"invitation_id": str(inv.id)}, actor_user.id)
        return inv, raw

    @staticmethod
    def cancel_invitation(*, workspace, actor_user, invitation_id) -> WorkspaceInvitation:
        WorkspaceService.require_admin(workspace, actor_user)
        inv = WorkspaceInvitation.objects.filter(
            workspace=workspace, id=invitation_id).first()
        if inv is None:
            raise WorkspaceError("Invitation not found.")
        if inv.status != "pending":
            raise WorkspaceError(f"Cannot cancel a {inv.status} invitation.")
        inv.status = "cancelled"
        inv.responded_at = timezone.now()
        inv.save(update_fields=["status", "responded_at", "updated_at"])
        _emit(workspace.id, "workspace.invitation.cancelled",
              {"invitation_id": str(inv.id)}, actor_user.id)
        return inv
