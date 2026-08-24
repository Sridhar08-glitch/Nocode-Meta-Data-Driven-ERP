"""
Numbering Engine REST API (Phase P2.1) at /api/v1/numbering/.

Sequence definitions are owner/admin-managed; any member may read, peek, and allocate
(issuing a number is a normal operational act). Other engines call ``NumberingService``
directly rather than this API.
"""
import uuid

from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import NumberAllocation, NumberSequence
from .serializers import NumberAllocationSerializer, NumberSequenceSerializer
from .services import NumberingError, NumberingService

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
    if getattr(_member(request), "role", "") not in _ADMIN_ROLES:
        raise PermissionDenied("Number sequence management requires an admin or owner role.")


def _uid(request):
    return getattr(request.user, "id", None)


def _get_seq(ws, seq_id) -> NumberSequence:
    seq = NumberSequence.objects.filter(workspace_id=ws, id=seq_id).first()
    if seq is None:
        raise NotFound("Number sequence not found.")
    return seq


class SequenceListCreateView(APIView):
    def get(self, request):
        _member(request)
        qs = NumberSequence.objects.filter(workspace_id=_ws(request)).order_by("key")
        return Response(NumberSequenceSerializer(qs, many=True).data)

    def post(self, request):
        _require_admin(request)
        ws = _ws(request)
        ser = NumberSequenceSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        key = ser.validated_data["key"]
        if NumberSequence.objects.filter(workspace_id=ws, key=key).exists():
            raise ValidationError(f"Sequence {key!r} already exists.")
        obj = ser.save(workspace_id=ws, created_by=_uid(request))
        return Response(NumberSequenceSerializer(obj).data, status=201)


class SequenceDetailView(APIView):
    def get(self, request, seq_id):
        _member(request)
        return Response(NumberSequenceSerializer(_get_seq(_ws(request), seq_id)).data)

    def patch(self, request, seq_id):
        _require_admin(request)
        seq = _get_seq(_ws(request), seq_id)
        ser = NumberSequenceSerializer(seq, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(NumberSequenceSerializer(seq).data)

    def delete(self, request, seq_id):
        _require_admin(request)
        seq = _get_seq(_ws(request), seq_id)
        if seq.is_system:
            raise ValidationError("System sequences cannot be deleted.")
        seq.delete()
        return Response(status=204)


class SequencePeekView(APIView):
    def get(self, request, seq_id):
        _member(request)
        seq = _get_seq(_ws(request), seq_id)
        try:
            nxt = NumberingService.peek(_ws(request), seq.key)
        except NumberingError as exc:
            raise ValidationError(str(exc)) from exc
        return Response({"next": nxt})


class SequenceAllocateView(APIView):
    def post(self, request, seq_id):
        _member(request)
        seq = _get_seq(_ws(request), seq_id)
        context = request.data.get("context") if isinstance(request.data, dict) else None
        try:
            formatted = NumberingService.allocate(
                _ws(request), seq.key, actor_id=_uid(request),
                context=context if isinstance(context, dict) else None)
        except NumberingError as exc:
            raise ValidationError(str(exc)) from exc
        return Response({"formatted": formatted}, status=201)


class SequenceResetView(APIView):
    def post(self, request, seq_id):
        _require_admin(request)
        seq = _get_seq(_ws(request), seq_id)
        to_value = request.data.get("to_value") if isinstance(request.data, dict) else None
        seq = NumberingService.reset(_ws(request), seq.key, to_value=to_value, actor_id=_uid(request))
        return Response(NumberSequenceSerializer(seq).data)


class SequenceAllocationsView(APIView):
    def get(self, request, seq_id):
        _member(request)
        ws = _ws(request)
        _get_seq(ws, seq_id)
        qs = NumberAllocation.objects.filter(
            workspace_id=ws, sequence_id=seq_id).order_by("-created_at")[:200]
        return Response({"results": NumberAllocationSerializer(qs, many=True).data})
