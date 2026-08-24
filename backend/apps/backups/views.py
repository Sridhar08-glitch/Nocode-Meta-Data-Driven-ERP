"""
Backups REST API (PROJECT_HANDBOOK.md §33.5) at /api/v1/backups/.

Workspace-scoped and admin-gated. Backup artifacts and the restore confirmation
token are never returned by the read endpoints; the confirmation token is shown
exactly once, in the create-restore-job response.
"""
import uuid

from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import BackupJob, DataRetentionPolicy, RestoreJob
from .serializers import (
    BackupJobSerializer,
    DataRetentionPolicySerializer,
    RestoreJobSerializer,
)
from .services import BackupError, BackupService

_ADMIN_ROLES = {"owner", "admin"}


def _ws(request) -> uuid.UUID:
    ws = getattr(request, "workspace_id", None)
    if not ws:
        raise PermissionDenied("No active workspace. Send the X-Workspace-Slug header.")
    return ws if isinstance(ws, uuid.UUID) else uuid.UUID(str(ws))


def _member(request):
    m = getattr(request, "workspace_member", None)
    if m is None:
        raise PermissionDenied("No workspace membership for this request.")
    return m


def _require_admin(request):
    m = _member(request)
    if getattr(m, "role", "") not in _ADMIN_ROLES:
        raise PermissionDenied("Admin role required.")
    return m


# ── backup jobs ──────────────────────────────────────────────────────────────
class BackupJobListView(APIView):
    def get(self, request):
        _member(request)
        qs = BackupJob.objects.filter(workspace_id=_ws(request)).order_by("-created_at")[:200]
        return Response({"results": BackupJobSerializer(qs, many=True).data})

    def post(self, request):
        member = _require_admin(request)
        backup_type = request.data.get("backup_type", "full")
        if backup_type not in ("full", "incremental", "config_only"):
            raise ValidationError("Invalid backup_type.")
        job = BackupService.create_backup_job(
            workspace_id=_ws(request), backup_type=backup_type, initiated_by=member.user_id)
        return Response(BackupJobSerializer(job).data, status=201)


class BackupJobDetailView(APIView):
    def _get(self, request, pk) -> BackupJob:
        obj = BackupJob.objects.filter(id=pk, workspace_id=_ws(request)).first()
        if obj is None:
            raise NotFound("Backup job not found")
        return obj

    def get(self, request, pk):
        _member(request)
        return Response(BackupJobSerializer(self._get(request, pk)).data)

    def delete(self, request, pk):
        _require_admin(request)
        job = self._get(request, pk)
        if job.storage_key:
            import contextlib

            from apps.documents.storage import get_storage_backend
            with contextlib.suppress(Exception):
                get_storage_backend(job.workspace_id).delete(job.storage_key)
        job.status = "expired"
        job.storage_key = ""
        job.save(update_fields=["status", "storage_key"])
        return Response({"deleted": True})


# ── restore jobs ─────────────────────────────────────────────────────────────
class RestoreJobListCreateView(APIView):
    def post(self, request):
        member = _require_admin(request)
        ws = _ws(request)
        data = request.data
        restore_type = data.get("restore_type")
        if restore_type not in ("full_backup", "pitr"):
            raise ValidationError("Invalid restore_type.")
        target_ws_id = data.get("target_workspace_id")
        target_ws_slug = data.get("target_workspace_slug", "")
        if not target_ws_id:
            raise ValidationError("target_workspace_id is required.")
        try:
            job, token = BackupService.create_restore_job(
                workspace_id=ws, restore_type=restore_type,
                target_workspace_id=target_ws_id, target_workspace_slug=target_ws_slug,
                initiated_by=member.user_id, backup_job_id=data.get("backup_job_id"),
                pitr_target_sequence=data.get("pitr_target_sequence"))
        except BackupError as exc:
            raise ValidationError(str(exc)) from exc
        out = RestoreJobSerializer(job).data
        out["confirmation_token"] = token  # shown ONCE — only the hash is persisted
        return Response(out, status=201)


class RestoreJobDetailView(APIView):
    def get(self, request, pk):
        _member(request)
        obj = RestoreJob.objects.filter(id=pk, workspace_id=_ws(request)).first()
        if obj is None:
            raise NotFound("Restore job not found")
        return Response(RestoreJobSerializer(obj).data)


class RestoreJobConfirmView(APIView):
    def post(self, request, pk):
        _require_admin(request)
        obj = RestoreJob.objects.filter(id=pk, workspace_id=_ws(request)).first()
        if obj is None:
            raise NotFound("Restore job not found")
        try:
            job = BackupService.confirm_restore(
                obj.id, request.data.get("token", ""), getattr(_member(request), "user_id", None))
        except BackupError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(RestoreJobSerializer(job).data)


# ── retention policies ───────────────────────────────────────────────────────
class RetentionPolicyListView(APIView):
    def get(self, request):
        _member(request)
        qs = DataRetentionPolicy.objects.filter(workspace_id=_ws(request)).order_by("-created_at")
        return Response({"results": DataRetentionPolicySerializer(qs, many=True).data})

    def post(self, request):
        _require_admin(request)
        ser = DataRetentionPolicySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = ser.save(workspace_id=_ws(request))
        return Response(DataRetentionPolicySerializer(obj).data, status=201)


class RetentionPolicyDetailView(APIView):
    def _get(self, request, pk) -> DataRetentionPolicy:
        obj = DataRetentionPolicy.objects.filter(id=pk, workspace_id=_ws(request)).first()
        if obj is None:
            raise NotFound("Retention policy not found")
        return obj

    def get(self, request, pk):
        _member(request)
        return Response(DataRetentionPolicySerializer(self._get(request, pk)).data)

    def patch(self, request, pk):
        _require_admin(request)
        obj = self._get(request, pk)
        ser = DataRetentionPolicySerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(DataRetentionPolicySerializer(obj).data)

    def delete(self, request, pk):
        _require_admin(request)
        self._get(request, pk).delete()
        return Response(status=204)
