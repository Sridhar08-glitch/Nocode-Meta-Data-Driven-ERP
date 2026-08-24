"""
Integrations services (PROJECT_HANDBOOK.md §30.1).

Outbound webhooks (HMAC-signed, retried) and reusable HTTP connectors. **No raw
secrets are ever stored or logged** — signing keys and connector credentials are
loaded from the environment by reference (``*_ref`` → ``os.environ[ref]``).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os

from django.utils import timezone

from .models import HTTPConnector, WebhookSubscription

SIGNATURE_HEADER = "X-Nexus-Signature"


def resolve_secret(ref: str) -> str:
    """Resolve a secret *reference* to its value from the environment (never the DB)."""
    if not ref:
        return ""
    return os.environ.get(ref, "")


# ── outbound HTTP seam (monkeypatched in tests) ──────────────────────────────
def _http_request(method, url, *, headers=None, params=None, data=None, timeout=10):
    import requests
    resp = requests.request(method, url, headers=headers, params=params, data=data,
                            timeout=timeout)
    body = None
    try:
        body = resp.json()
    except Exception:  # noqa: BLE001
        body = resp.text
    return {"status": resp.status_code, "body": body, "headers": dict(resp.headers)}


class WebhookService:
    @staticmethod
    def deliver_event(event_type, payload, workspace_id, event_id=None) -> int:
        """Dispatch an outbound delivery for every active subscription matching *event_type*."""
        from .tasks import deliver_webhook
        subs = WebhookSubscription.objects.filter(workspace_id=workspace_id, status="active")
        fired = 0
        for sub in subs:
            if sub.event_types and event_type not in sub.event_types:
                continue
            deliver_webhook.delay(str(sub.id), event_type, payload, str(event_id) if event_id else None)
            fired += 1
        return fired

    @staticmethod
    def build_payload(event_type, payload, subscription) -> tuple[str, dict]:
        body = json.dumps({
            "event": event_type, "data": payload,
            "workspace_id": str(subscription.workspace_id),
            "sent_at": timezone.now().isoformat(),
        }, default=str)
        headers = {"Content-Type": "application/json", **(subscription.headers or {})}
        secret = resolve_secret(subscription.signing_secret_ref)
        if secret:
            sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
            headers[SIGNATURE_HEADER] = f"sha256={sig}"
        return body, headers


class HTTPConnectorService:
    @staticmethod
    def request(connector: HTTPConnector, method, path, body=None, timeout=None) -> dict:
        url = connector.base_url.rstrip("/") + "/" + str(path or "").lstrip("/")
        headers = {"Content-Type": "application/json", **(connector.default_headers or {})}
        params = {}
        cfg = connector.auth_config or {}
        auth = connector.auth_type
        if auth == "bearer_token":
            token = resolve_secret(cfg.get("token_ref", ""))
            if token:
                headers["Authorization"] = f"Bearer {token}"
        elif auth == "basic_auth":
            import base64
            user = cfg.get("username", "")
            pw = resolve_secret(cfg.get("password_ref", ""))
            token = base64.b64encode(f"{user}:{pw}".encode()).decode()
            headers["Authorization"] = f"Basic {token}"
        elif auth == "api_key_header":
            key = resolve_secret(cfg.get("key_ref", ""))
            headers[cfg.get("header_name", "X-API-Key")] = key
        elif auth == "api_key_query":
            params[cfg.get("param_name", "api_key")] = resolve_secret(cfg.get("key_ref", ""))
        data = json.dumps(body, default=str) if body is not None else None
        return _http_request(method.upper(), url, headers=headers, params=params,
                             data=data, timeout=timeout or connector.timeout_seconds)
