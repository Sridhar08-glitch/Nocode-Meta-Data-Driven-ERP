"""
Request-ID correlation middleware (Phase P1.6).

Assigns every request a stable id (honouring an inbound ``X-Request-ID`` from an upstream
proxy when present, else minting one) and echoes it on the response. The id is also attached
to the request so views/logging can correlate a single request across log lines, and — when
Sentry is active — tagged on the active scope so an error links back to its access log entry.
"""
import uuid

from django.utils.deprecation import MiddlewareMixin

REQUEST_ID_HEADER = "HTTP_X_REQUEST_ID"
RESPONSE_HEADER = "X-Request-ID"


class RequestIDMiddleware(MiddlewareMixin):
    def process_request(self, request):
        rid = request.META.get(REQUEST_ID_HEADER, "").strip() or uuid.uuid4().hex
        # Bound the length so a malicious upstream can't inject an unbounded header value.
        request.request_id = rid[:64]
        try:
            import sentry_sdk

            sentry_sdk.set_tag("request_id", request.request_id)
        except ImportError:
            pass
        return None

    def process_response(self, request, response):
        rid = getattr(request, "request_id", None)
        if rid:
            response[RESPONSE_HEADER] = rid
        return response
