"""Unified exception handler for Sridhar ERP."""
import logging

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger("nexus")


class NexusError(Exception):
    """Base for all Sridhar ERP domain errors."""
    status_code = 400
    code = "nexus_error"

    def __init__(self, message, code=None, detail=None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.detail = detail or {}


class NotFoundError(NexusError):
    status_code = 404
    code = "not_found"


class PermissionError(NexusError):
    status_code = 403
    code = "permission_denied"


class ConflictError(NexusError):
    status_code = 409
    code = "conflict"


class SchemaError(NexusError):
    status_code = 422
    code = "schema_error"


class NQLError(NexusError):
    status_code = 400
    code = "nql_error"


class TenantError(NexusError):
    status_code = 403
    code = "tenant_error"


def nexus_exception_handler(exc, context):
    """Convert all exceptions to consistent JSON error envelopes."""
    if isinstance(exc, NexusError):
        return Response(
            {"error": {"code": exc.code, "message": exc.message, "detail": exc.detail}},
            status=exc.status_code,
        )

    if isinstance(exc, PermissionDenied):
        return Response(
            {"error": {"code": "permission_denied", "message": "You do not have permission to perform this action."}},
            status=status.HTTP_403_FORBIDDEN,
        )

    if isinstance(exc, ObjectDoesNotExist):
        return Response(
            {"error": {"code": "not_found", "message": str(exc)}},
            status=status.HTTP_404_NOT_FOUND,
        )

    if isinstance(exc, ValidationError):
        return Response(
            {"error": {"code": "validation_error", "message": "Validation failed.", "detail": exc.message_dict if hasattr(exc, "message_dict") else str(exc)}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Fall back to DRF default handler
    response = exception_handler(exc, context)
    if response is not None:
        # Wrap DRF errors in our envelope
        response.data = {
            "error": {
                "code": "validation_error" if response.status_code == 400 else "error",
                "message": "Request failed.",
                "detail": response.data,
            }
        }
    else:
        logger.exception("Unhandled exception in view", exc_info=exc)
        response = Response(
            {"error": {"code": "internal_error", "message": "An internal error occurred."}},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return response
