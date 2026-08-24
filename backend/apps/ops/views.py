"""
Operational probes (Phase P1.6) — unauthenticated, workspace-agnostic endpoints for
load balancers / process orchestrators. These are intentionally NOT under ``/api/v1/`` and
NOT tenant-scoped; they report process and dependency health only, never tenant data.

  * ``GET /healthz/`` — liveness: 200 as long as the process can serve a request.
  * ``GET /readyz/``  — readiness: 200 only when DB + cache + broker are all reachable,
                         otherwise 503 with a per-component breakdown.
"""
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .checks import run_readiness_checks


class LivenessView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"status": "ok"})


class ReadinessView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        all_ok, components = run_readiness_checks()
        return Response(
            {"status": "ready" if all_ok else "not_ready", "checks": components},
            status=200 if all_ok else 503,
        )
