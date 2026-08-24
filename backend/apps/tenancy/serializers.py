"""Serializers for the tenancy/workspaces API."""
from rest_framework import serializers

from .models import Workspace, WorkspaceInvitation, WorkspaceMember


class MyWorkspaceSerializer(serializers.Serializer):
    """A workspace the authenticated user belongs to, with their role + plan limits.

    Serialises a ``WorkspaceMember`` row (so the caller's role travels with each workspace).
    """

    id = serializers.UUIDField(source="workspace.id")
    slug = serializers.CharField(source="workspace.slug")
    name = serializers.CharField(source="workspace.name")
    plan = serializers.CharField(source="workspace.plan")
    logo_url = serializers.CharField(source="workspace.logo_url")
    role = serializers.CharField()
    limits = serializers.SerializerMethodField()

    def get_limits(self, member: WorkspaceMember) -> dict:
        w = member.workspace
        return {
            "max_members": w.max_members,
            "max_entities": w.max_entities,
            "max_records": w.max_records,
            "max_storage_bytes": w.max_storage_bytes,
        }


class WorkspaceSerializer(serializers.ModelSerializer):
    """Full workspace detail (for owners/admins managing the tenant)."""

    class Meta:
        model = Workspace
        fields = [
            "id", "name", "slug", "plan", "logo_url", "owner",
            "max_members", "max_entities", "max_records", "max_storage_bytes",
            "settings", "is_active", "created_at",
        ]
        read_only_fields = ["id", "slug", "owner", "is_active", "created_at"]


class WorkspaceMemberSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    user_id = serializers.UUIDField()
    email = serializers.CharField(source="user.email")
    full_name = serializers.CharField(source="user.full_name")
    role = serializers.CharField()
    status = serializers.CharField()
    custom_role_id = serializers.UUIDField(allow_null=True)
    joined_at = serializers.DateTimeField(allow_null=True)
    is_owner = serializers.SerializerMethodField()

    def get_is_owner(self, member: WorkspaceMember) -> bool:
        return member.role == "owner"


# ── input serializers ────────────────────────────────────────────────────────
class CreateWorkspaceSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    slug = serializers.SlugField(max_length=63, required=False, allow_blank=True)
    plan = serializers.ChoiceField(
        choices=["free", "starter", "pro", "enterprise"], required=False, default="free")


class UpdateWorkspaceSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    logo_url = serializers.URLField(required=False, allow_blank=True)
    plan = serializers.ChoiceField(
        choices=["free", "starter", "pro", "enterprise"], required=False)
    settings = serializers.DictField(required=False)
    max_members = serializers.IntegerField(required=False, min_value=1)
    max_entities = serializers.IntegerField(required=False, min_value=1)
    max_records = serializers.IntegerField(required=False, min_value=1)
    max_storage_bytes = serializers.IntegerField(required=False, min_value=1)


class AddMemberSerializer(serializers.Serializer):
    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    role = serializers.ChoiceField(choices=["admin", "member", "viewer"], default="member")


class AssignRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=["admin", "member", "viewer"], required=False)
    custom_role_id = serializers.UUIDField(required=False, allow_null=True)


class InviteMemberSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=["admin", "member", "viewer"], default="member")


class InvitationTokenSerializer(serializers.Serializer):
    token = serializers.CharField()


class WorkspaceInvitationSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkspaceInvitation
        fields = ["id", "email", "role", "status", "invited_by",
                  "expires_at", "responded_at", "created_at"]
        read_only_fields = fields
