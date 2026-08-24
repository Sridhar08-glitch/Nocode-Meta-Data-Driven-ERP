"""
NQL query endpoint (workspace-scoped via TenantMiddleware).

POST /api/v1/nql/query/
  Body is either the NQL JSON AST (master spec §12, with an "entity" key) or
  ``{"text": "SELECT ... FROM ... WHERE ..."}`` for the SQL-like surface.
"""
import uuid

from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .exceptions import NQLError, UnknownEntityError
from .services import execute_nql


def _ws(request) -> uuid.UUID:
    ws = getattr(request, "workspace_id", None)
    if not ws:
        raise PermissionDenied("No active workspace. Send the X-Workspace-Slug header.")
    return ws if isinstance(ws, uuid.UUID) else uuid.UUID(str(ws))


class NQLQueryView(APIView):
    def post(self, request):
        body = request.data
        source = body.get("text") if isinstance(body, dict) and "text" in body else body
        try:
            rows = execute_nql(
                workspace_id=_ws(request),
                source=source,
                user_id=getattr(request.user, "id", None),
            )
        except UnknownEntityError as exc:
            raise NotFound(str(exc)) from exc
        except NQLError as exc:
            raise ValidationError(str(exc)) from exc
        return Response({"rows": rows, "count": len(rows)}, status=status.HTTP_200_OK)
