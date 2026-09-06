/**
 * Integrations client (Phase F3.5 Developer Portal) — outbound webhooks, inbound webhooks, HTTP
 * connectors, and OAuth apps over `/api/v1/integrations/` (backend Phase 1.21). Admin writes.
 * Secrets are stored by reference only (`*_ref`); inbound tokens are returned ONCE on create/rotate.
 */
import { apiGet, apiSend } from "@/lib/api/request";

export interface WebhookSubscription {
  id: string;
  name: string;
  target_url: string;
  signing_secret_ref: string;
  event_types: string[];
  entity_id: string | null;
  status: string;
  http_method: string;
  headers: Record<string, string>;
  timeout_seconds: number;
  max_retries: number;
  success_count: number;
  failure_count: number;
  consecutive_failures: number;
  last_fired_at: string | null;
}
export interface SubscriptionWrite {
  name: string;
  target_url: string;
  event_types: string[];
  signing_secret_ref?: string;
  http_method?: string;
  timeout_seconds?: number;
  max_retries?: number;
}
export interface WebhookDelivery {
  id: string;
  event_type: string;
  status: string;
  attempt_number: number;
  response_status: number | null;
  duration_ms: number;
  delivered_at: string | null;
  error_message: string;
}

export interface InboundWebhook {
  id: string;
  name: string;
  slug: string;
  workflow_id: string | null;
  is_active: boolean;
  allowed_ips: string[];
  expected_content_type: string;
  call_count: number;
  last_called_at: string | null;
}
export interface InboundWrite {
  name: string;
  slug: string;
  workflow_id?: string | null;
  allowed_ips?: string[];
}
export interface InboundCreated extends InboundWebhook {
  token: string;
  url: string;
}

export interface HTTPConnector {
  id: string;
  name: string;
  slug: string;
  base_url: string;
  auth_type: string;
  auth_config: Record<string, unknown>;
  timeout_seconds: number;
  is_active: boolean;
}
export interface ConnectorWrite {
  name: string;
  slug: string;
  base_url: string;
  auth_type?: string;
  auth_config?: Record<string, unknown>;
}

export interface OAuthApp {
  id: string;
  name: string;
  provider: string;
  client_id: string;
  client_secret_ref: string;
  scopes: string[];
  redirect_uri: string;
  is_active: boolean;
}
export interface OAuthAppWrite {
  name: string;
  provider: string;
  client_id: string;
  client_secret_ref?: string;
  scopes?: string[];
  redirect_uri?: string;
}

export const CONNECTOR_AUTH_TYPES = ["none", "bearer", "basic", "api_key_header", "api_key_query"] as const;

const I = "/api/v1/integrations";

export const integrationsApi = {
  // outbound webhooks
  listSubs: () => apiGet<{ results: WebhookSubscription[]; count: number }>(`${I}/webhooks/subscriptions/`),
  createSub: (data: SubscriptionWrite) => apiSend<WebhookSubscription>(`${I}/webhooks/subscriptions/`, "POST", data),
  updateSub: (id: string, data: Partial<SubscriptionWrite>) => apiSend<WebhookSubscription>(`${I}/webhooks/subscriptions/${id}/`, "PATCH", data),
  deleteSub: (id: string) => apiSend<null>(`${I}/webhooks/subscriptions/${id}/`, "DELETE"),
  testSub: (id: string) => apiSend<{ delivered: boolean; delivery: WebhookDelivery | null }>(`${I}/webhooks/subscriptions/${id}/test/`, "POST"),
  deliveries: (id: string) => apiGet<{ results: WebhookDelivery[]; count: number }>(`${I}/webhooks/subscriptions/${id}/deliveries/`),
  enableSub: (id: string) => apiSend<WebhookSubscription>(`${I}/webhooks/subscriptions/${id}/enable/`, "POST"),
  disableSub: (id: string) => apiSend<WebhookSubscription>(`${I}/webhooks/subscriptions/${id}/disable/`, "POST"),

  // inbound webhooks
  listInbound: () => apiGet<{ results: InboundWebhook[]; count: number }>(`${I}/inbound-webhooks/`),
  createInbound: (data: InboundWrite) => apiSend<InboundCreated>(`${I}/inbound-webhooks/`, "POST", data),
  deleteInbound: (id: string) => apiSend<null>(`${I}/inbound-webhooks/${id}/`, "DELETE"),
  rotateInbound: (id: string) => apiSend<{ token: string; url: string }>(`${I}/inbound-webhooks/${id}/rotate-token/`, "POST"),

  // connectors
  listConnectors: () => apiGet<{ results: HTTPConnector[]; count: number }>(`${I}/connectors/`),
  createConnector: (data: ConnectorWrite) => apiSend<HTTPConnector>(`${I}/connectors/`, "POST", data),
  deleteConnector: (id: string) => apiSend<null>(`${I}/connectors/${id}/`, "DELETE"),
  testConnector: (id: string) => apiSend<{ status: number | null }>(`${I}/connectors/${id}/test/`, "POST"),

  // oauth apps
  listOAuth: () => apiGet<{ results: OAuthApp[]; count: number }>(`${I}/oauth-apps/`),
  createOAuth: (data: OAuthAppWrite) => apiSend<OAuthApp>(`${I}/oauth-apps/`, "POST", data),
  deleteOAuth: (id: string) => apiSend<null>(`${I}/oauth-apps/${id}/`, "DELETE"),
};
