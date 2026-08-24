"""
Portal scoped-data API (Phase 1.34) — /api/v1/portal/data/{entity}/.

Authenticated in the portal realm (``PortalJWTAuthentication`` → ``request.user`` is a
PortalUser). Every read/write is scoped to records linked to the caller via
:class:`~apps.portal.data_services.PortalDataService`. The workspace is taken from the
portal token, never from the client.
"""
from rest_framework import status
from rest_framework.exceptions import NotFound, ParseError, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.nql.exceptions import NQLError
from apps.records.services import EntityNotQueryable, RecordNotFound
from apps.rules.services import RuleBlocked

from .authentication import PortalJWTAuthentication
from .data_services import PortalAccessError, PortalDataService, PortalNotFound


def _run(fn):
    try:
        return fn()
    except PortalAccessError as exc:
        raise PermissionDenied(str(exc)) from exc
    except (PortalNotFound, RecordNotFound) as exc:
        raise NotFound(str(exc)) from exc
    except EntityNotQueryable as exc:
        raise NotFound(str(exc)) from exc
    except (NQLError, RuleBlocked) as exc:
        raise ValidationError(str(exc)) from exc


class PortalRecordListCreateView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, entity_slug):
        extra = None
        if "filter" in request.query_params:
            import json
            try:
                extra = json.loads(request.query_params["filter"])
            except (TypeError, ValueError) as exc:
                raise ParseError("filter must be valid JSON") from exc
        rows = _run(lambda: PortalDataService.list_records(
            request.user, entity_slug, extra_filter=extra))
        return Response({"results": rows, "count": len(rows)})

    def post(self, request, entity_slug):
        rec = _run(lambda: PortalDataService.create_record(
            request.user, entity_slug, request.data))
        return Response(rec, status=status.HTTP_201_CREATED)


class PortalRecordDetailView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, entity_slug, record_id):
        rec = _run(lambda: PortalDataService.retrieve_record(
            request.user, entity_slug, record_id))
        return Response(rec)
