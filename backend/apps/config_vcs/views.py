"""Config VCS API (admin/owner only) — /api/v1/config-vcs/."""
import uuid

from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services


def _ctx(request):
    ws = getattr(request, "workspace_id", None)
    member = getattr(request, "workspace_member", None)
    if not ws or member is None:
        raise PermissionDenied("No active workspace.")
    if member.role not in ("owner", "admin"):
        raise PermissionDenied("Config VCS requires owner/admin.")
    ws = ws if isinstance(ws, uuid.UUID) else uuid.UUID(str(ws))
    return ws, getattr(request.user, "id", None)


def _serialize(c):
    return {"sha": c.sha, "parent_sha": c.parent_sha, "message": c.message,
            "branch": c.branch, "author_id": str(c.author_id) if c.author_id else None,
            "created_at": c.created_at.isoformat(), "diff": c.diff}


def _serialize_branch(b):
    return {"name": b.name, "head_sha": b.head_sha, "base_sha": b.base_sha,
            "is_default": b.is_default, "is_protected": b.is_protected,
            "created_by": str(b.created_by) if b.created_by else None,
            "created_at": b.created_at.isoformat()}


def _serialize_mr(mr):
    return {"id": str(mr.id), "title": mr.title, "description": mr.description,
            "source_branch": mr.source_branch, "target_branch": mr.target_branch,
            "status": mr.status, "conflict_details": mr.conflict_details,
            "resolution": mr.resolution,
            "opened_by": str(mr.opened_by) if mr.opened_by else None,
            "merged_by": str(mr.merged_by) if mr.merged_by else None,
            "merged_at": mr.merged_at.isoformat() if mr.merged_at else None,
            "merge_commit_sha": mr.merge_commit_sha,
            "created_at": mr.created_at.isoformat()}


class CommitView(APIView):
    def post(self, request):
        ws, author = _ctx(request)
        try:
            c = services.commit(workspace_id=ws, message=request.data.get("message", ""),
                                author_id=author, branch=request.data.get("branch", "main"))
        except services.ConfigVCSError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(_serialize(c), status=status.HTTP_201_CREATED)


class CommitListView(APIView):
    def get(self, request):
        ws, _ = _ctx(request)
        branch = request.query_params.get("branch", "main")
        commits = services.list_commits(workspace_id=ws, branch=branch)
        return Response({"results": [_serialize(c) for c in commits], "count": len(commits)})


class DiffView(APIView):
    def get(self, request):
        ws, _ = _ctx(request)
        a, b = request.query_params.get("a"), request.query_params.get("b")
        if not a or not b:
            raise ValidationError("Provide ?a=<sha>&b=<sha>")
        try:
            return Response(services.diff_commits(workspace_id=ws, sha_a=a, sha_b=b))
        except services.ConfigVCSError as exc:
            raise NotFound(str(exc)) from exc


class RollbackView(APIView):
    def post(self, request):
        ws, author = _ctx(request)
        sha = request.data.get("sha")
        if not sha:
            raise ValidationError("sha is required")
        try:
            c = services.rollback(workspace_id=ws, sha=sha, author_id=author)
        except services.ConfigVCSError as exc:
            raise NotFound(str(exc)) from exc
        return Response(_serialize(c), status=status.HTTP_201_CREATED)


# ── Branches (Phase 1.28) ─────────────────────────────────────────────────────
class BranchListCreateView(APIView):
    def get(self, request):
        ws, _ = _ctx(request)
        branches = services.list_branches(workspace_id=ws)
        return Response({"results": [_serialize_branch(b) for b in branches],
                         "count": len(branches)})

    def post(self, request):
        ws, author = _ctx(request)
        try:
            b = services.create_branch(
                workspace_id=ws, name=request.data.get("name", ""),
                from_branch=request.data.get("from_branch", "main"),
                from_sha=request.data.get("from_sha"), created_by=author)
        except services.ConfigVCSError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(_serialize_branch(b), status=status.HTTP_201_CREATED)


# ── Merge requests (Phase 1.28) ───────────────────────────────────────────────
class MergeRequestListCreateView(APIView):
    def get(self, request):
        ws, _ = _ctx(request)
        mrs = services.list_merge_requests(
            workspace_id=ws, status=request.query_params.get("status"))
        return Response({"results": [_serialize_mr(m) for m in mrs], "count": len(mrs)})

    def post(self, request):
        ws, author = _ctx(request)
        try:
            mr = services.open_merge_request(
                workspace_id=ws, source_branch=request.data.get("source_branch", ""),
                target_branch=request.data.get("target_branch", ""),
                title=request.data.get("title", ""),
                description=request.data.get("description", ""), opened_by=author)
        except services.ConfigVCSError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(_serialize_mr(mr), status=status.HTTP_201_CREATED)


class MergeRequestDetailView(APIView):
    def get(self, request, mr_id):
        ws, _ = _ctx(request)
        try:
            mr = services.get_merge_request(ws, mr_id)
        except services.ConfigVCSError as exc:
            raise NotFound(str(exc)) from exc
        return Response(_serialize_mr(mr))


class MergeRequestMergeView(APIView):
    def post(self, request, mr_id):
        ws, author = _ctx(request)
        try:
            mr, conflicts = services.merge(workspace_id=ws, mr_id=mr_id, merged_by=author)
        except services.ConfigVCSError as exc:
            raise ValidationError(str(exc)) from exc
        if conflicts:
            return Response({**_serialize_mr(mr), "conflicts": conflicts},
                            status=status.HTTP_409_CONFLICT)
        return Response(_serialize_mr(mr), status=status.HTTP_200_OK)


class MergeRequestResolveView(APIView):
    def post(self, request, mr_id):
        ws, author = _ctx(request)
        try:
            mr, conflicts = services.resolve_merge_request(
                workspace_id=ws, mr_id=mr_id,
                resolutions=request.data.get("resolutions"), merged_by=author)
        except services.ConfigVCSError as exc:
            raise ValidationError(str(exc)) from exc
        if conflicts:
            return Response({**_serialize_mr(mr), "conflicts": conflicts},
                            status=status.HTTP_409_CONFLICT)
        return Response(_serialize_mr(mr), status=status.HTTP_200_OK)
