"""
Tenancy API — /api/v1/workspaces/.

Workspace & Identity Administration (P2.17): self-service tenant provisioning, a
member roster, role assignment, suspend/remove, ownership transfer and admin
password reset — the lifecycle a real customer needs to run Sridhar ERP without a
developer. ``GET /`` (membership list) and ``POST /`` (create) need no workspace
context; everything else resolves the workspace from the URL slug and is gated on
the caller's role inside ``WorkspaceService``.
"""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Workspace, WorkspaceMember
from .serializers import (
    AddMemberSerializer,
    AssignRoleSerializer,
    CreateWorkspaceSerializer,
    InvitationTokenSerializer,
    InviteMemberSerializer,
    MyWorkspaceSerializer,
    UpdateWorkspaceSerializer,
    WorkspaceInvitationSerializer,
    WorkspaceMemberSerializer,
    WorkspaceSerializer,
)
from .services import WorkspaceError, WorkspacePermissionError, WorkspaceService


def _err(exc) -> Response:
    code = (status.HTTP_403_FORBIDDEN if isinstance(exc, WorkspacePermissionError)
            else status.HTTP_400_BAD_REQUEST)
    return Response({"detail": str(exc)}, status=code)


def _get_workspace(slug) -> Workspace | None:
    return Workspace.objects.filter(
        slug=slug, is_active=True, deleted_at__isnull=True).first()


def _get_workspace_any(slug) -> Workspace | None:
    """Resolve a workspace regardless of archived/soft-deleted state (for restore /
    permanent-delete). Hard-purged workspaces are gone and return None."""
    return Workspace.objects.filter(slug=slug).first()


class _WorkspaceOwnerActionView(APIView):
    """For lifecycle actions on a workspace that may be archived/soft-deleted —
    resolves it in any state; the service enforces owner-only."""
    permission_classes = [IsAuthenticated]

    def _resolve(self, slug):
        ws = _get_workspace_any(slug)
        if ws is None:
            return None, Response({"detail": "Workspace not found."},
                                  status=status.HTTP_404_NOT_FOUND)
        if WorkspaceService.get_role(ws, self.request.user) is None:
            return None, Response({"detail": "You are not a member of this workspace."},
                                  status=status.HTTP_403_FORBIDDEN)
        return ws, None


class _WorkspaceScopedView(APIView):
    """Resolves the workspace from the URL slug and 404s if absent. Role checks are
    performed inside the service (so an admin of another workspace can't act here)."""
    permission_classes = [IsAuthenticated]

    def get_workspace_or_404(self, slug):
        ws = _get_workspace(slug)
        if ws is None:
            return None, Response({"detail": "Workspace not found."},
                                  status=status.HTTP_404_NOT_FOUND)
        # The caller must at least be an active member to see/act on the workspace.
        if WorkspaceService.get_role(ws, self.request.user) is None:
            return None, Response({"detail": "You are not a member of this workspace."},
                                  status=status.HTTP_403_FORBIDDEN)
        return ws, None


class MyWorkspacesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # ?archived=true → workspaces the caller owns that are archived/soft-deleted
        if request.query_params.get("archived") in ("1", "true", "yes"):
            archived = WorkspaceService.list_archived(user=request.user)
            return Response([WorkspaceSerializer(w).data for w in archived])
        members = (
            WorkspaceMember.objects.filter(user=request.user, status="active")
            .select_related("workspace")
            .filter(workspace__is_active=True, workspace__deleted_at__isnull=True)
            .order_by("workspace__name")
        )
        return Response(MyWorkspaceSerializer(members, many=True).data)

    def post(self, request):
        """Self-service tenant provisioning — the caller becomes the owner."""
        s = CreateWorkspaceSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            ws = WorkspaceService.create_workspace(
                user=request.user, name=s.validated_data["name"],
                slug=s.validated_data.get("slug") or None,
                plan=s.validated_data.get("plan", "free"))
        except WorkspaceError as exc:
            return _err(exc)
        data = WorkspaceSerializer(ws).data
        data["role"] = "owner"
        return Response(data, status=status.HTTP_201_CREATED)


class WorkspaceDetailView(_WorkspaceScopedView):
    def get(self, request, slug):
        ws, err = self.get_workspace_or_404(slug)
        if err:
            return err
        data = WorkspaceSerializer(ws).data
        data["role"] = WorkspaceService.get_role(ws, request.user)
        return Response(data)

    def patch(self, request, slug):
        ws, err = self.get_workspace_or_404(slug)
        if err:
            return err
        s = UpdateWorkspaceSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            ws = WorkspaceService.update_workspace(
                workspace=ws, actor_user=request.user, data=s.validated_data)
        except WorkspaceError as exc:
            return _err(exc)
        return Response(WorkspaceSerializer(ws).data)

    def delete(self, request, slug):
        """Soft-delete the workspace (owner-only, recoverable until retention purge)."""
        ws, err = self.get_workspace_or_404(slug)
        if err:
            return err
        try:
            WorkspaceService.soft_delete_workspace(workspace=ws, actor_user=request.user)
        except WorkspaceError as exc:
            return _err(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkspaceArchiveView(_WorkspaceScopedView):
    def post(self, request, slug):
        ws, err = self.get_workspace_or_404(slug)
        if err:
            return err
        try:
            ws = WorkspaceService.archive_workspace(workspace=ws, actor_user=request.user)
        except WorkspaceError as exc:
            return _err(exc)
        return Response(WorkspaceSerializer(ws).data)


class WorkspaceRestoreView(_WorkspaceOwnerActionView):
    def post(self, request, slug):
        ws, err = self._resolve(slug)
        if err:
            return err
        try:
            ws = WorkspaceService.restore_workspace(workspace=ws, actor_user=request.user)
        except WorkspaceError as exc:
            return _err(exc)
        return Response(WorkspaceSerializer(ws).data)


class WorkspaceHardDeleteRequestView(_WorkspaceOwnerActionView):
    def post(self, request, slug):
        ws, err = self._resolve(slug)
        if err:
            return err
        try:
            token = WorkspaceService.request_hard_delete(workspace=ws, actor_user=request.user)
        except WorkspaceError as exc:
            return _err(exc)
        return Response({"confirmation_token": token,
                         "detail": "Confirm within 30 minutes to permanently delete this workspace."})


class WorkspaceHardDeleteConfirmView(_WorkspaceOwnerActionView):
    def post(self, request, slug):
        ws, err = self._resolve(slug)
        if err:
            return err
        token = request.data.get("token")
        if not token:
            return Response({"detail": "token is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            WorkspaceService.confirm_hard_delete(
                workspace=ws, actor_user=request.user, token=token)
        except WorkspaceError as exc:
            return _err(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkspaceTransferOwnershipView(_WorkspaceScopedView):
    def post(self, request, slug):
        ws, err = self.get_workspace_or_404(slug)
        if err:
            return err
        member_id = request.data.get("member_id")
        if not member_id:
            return Response({"detail": "member_id is required."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            member = WorkspaceService.transfer_ownership(
                workspace=ws, actor_user=request.user, member_id=member_id)
        except WorkspaceError as exc:
            return _err(exc)
        return Response(WorkspaceMemberSerializer(member).data)


class MemberListView(_WorkspaceScopedView):
    def get(self, request, slug):
        ws, err = self.get_workspace_or_404(slug)
        if err:
            return err
        members = WorkspaceService.list_members(workspace=ws)
        return Response(WorkspaceMemberSerializer(members, many=True).data)

    def post(self, request, slug):
        ws, err = self.get_workspace_or_404(slug)
        if err:
            return err
        s = AddMemberSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            member, created_user = WorkspaceService.add_member(
                workspace=ws, actor_user=request.user,
                email=s.validated_data["email"],
                full_name=s.validated_data.get("full_name", ""),
                role=s.validated_data.get("role", "member"))
        except WorkspaceError as exc:
            return _err(exc)
        data = WorkspaceMemberSerializer(member).data
        data["created_user"] = created_user
        return Response(data, status=status.HTTP_201_CREATED)


class MemberDetailView(_WorkspaceScopedView):
    def patch(self, request, slug, member_id):
        ws, err = self.get_workspace_or_404(slug)
        if err:
            return err
        s = AssignRoleSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        kwargs = {}
        if "role" in s.validated_data:
            kwargs["role"] = s.validated_data["role"]
        if "custom_role_id" in s.validated_data:
            kwargs["custom_role_id"] = s.validated_data["custom_role_id"]
        try:
            member = WorkspaceService.assign_role(
                workspace=ws, actor_user=request.user, member_id=member_id, **kwargs)
        except WorkspaceError as exc:
            return _err(exc)
        return Response(WorkspaceMemberSerializer(member).data)

    def delete(self, request, slug, member_id):
        ws, err = self.get_workspace_or_404(slug)
        if err:
            return err
        try:
            WorkspaceService.remove_member(
                workspace=ws, actor_user=request.user, member_id=member_id)
        except WorkspaceError as exc:
            return _err(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MemberSuspendView(_WorkspaceScopedView):
    def post(self, request, slug, member_id):
        ws, err = self.get_workspace_or_404(slug)
        if err:
            return err
        try:
            member = WorkspaceService.suspend_member(
                workspace=ws, actor_user=request.user, member_id=member_id)
        except WorkspaceError as exc:
            return _err(exc)
        return Response(WorkspaceMemberSerializer(member).data)


class MemberReactivateView(_WorkspaceScopedView):
    def post(self, request, slug, member_id):
        ws, err = self.get_workspace_or_404(slug)
        if err:
            return err
        try:
            member = WorkspaceService.reactivate_member(
                workspace=ws, actor_user=request.user, member_id=member_id)
        except WorkspaceError as exc:
            return _err(exc)
        return Response(WorkspaceMemberSerializer(member).data)


class MemberResetPasswordView(_WorkspaceScopedView):
    def post(self, request, slug, member_id):
        ws, err = self.get_workspace_or_404(slug)
        if err:
            return err
        try:
            WorkspaceService.admin_reset_password(
                workspace=ws, actor_user=request.user, member_id=member_id)
        except WorkspaceError as exc:
            return _err(exc)
        return Response({"detail": "Password reset email sent."})


# ── invitation lifecycle ─────────────────────────────────────────────────────
class InvitationListCreateView(_WorkspaceScopedView):
    def get(self, request, slug):
        ws, err = self.get_workspace_or_404(slug)
        if err:
            return err
        invites = WorkspaceService.list_invitations(
            workspace=ws, status=request.query_params.get("status"))
        return Response(WorkspaceInvitationSerializer(invites, many=True).data)

    def post(self, request, slug):
        ws, err = self.get_workspace_or_404(slug)
        if err:
            return err
        s = InviteMemberSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            inv, _ = WorkspaceService.invite_member(
                workspace=ws, actor_user=request.user,
                email=s.validated_data["email"], role=s.validated_data.get("role", "member"))
        except WorkspaceError as exc:
            return _err(exc)
        return Response(WorkspaceInvitationSerializer(inv).data, status=status.HTTP_201_CREATED)


class InvitationResendView(_WorkspaceScopedView):
    def post(self, request, slug, invitation_id):
        ws, err = self.get_workspace_or_404(slug)
        if err:
            return err
        try:
            inv, _ = WorkspaceService.resend_invitation(
                workspace=ws, actor_user=request.user, invitation_id=invitation_id)
        except WorkspaceError as exc:
            return _err(exc)
        return Response(WorkspaceInvitationSerializer(inv).data)


class InvitationCancelView(_WorkspaceScopedView):
    def post(self, request, slug, invitation_id):
        ws, err = self.get_workspace_or_404(slug)
        if err:
            return err
        try:
            inv = WorkspaceService.cancel_invitation(
                workspace=ws, actor_user=request.user, invitation_id=invitation_id)
        except WorkspaceError as exc:
            return _err(exc)
        return Response(WorkspaceInvitationSerializer(inv).data)


class InvitationAcceptView(APIView):
    """The authenticated invitee accepts a tokenised invitation. No workspace
    context required — the token + the caller's email are the gate."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = InvitationTokenSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            member = WorkspaceService.accept_invitation(
                user=request.user, raw_token=s.validated_data["token"])
        except WorkspaceError as exc:
            return _err(exc)
        return Response(WorkspaceMemberSerializer(member).data, status=status.HTTP_200_OK)


class InvitationRejectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = InvitationTokenSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            WorkspaceService.reject_invitation(
                user=request.user, raw_token=s.validated_data["token"])
        except WorkspaceError as exc:
            return _err(exc)
        return Response({"detail": "Invitation declined."})
