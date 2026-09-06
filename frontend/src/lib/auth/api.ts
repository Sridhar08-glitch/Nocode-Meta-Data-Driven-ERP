/**
 * Auth API (Phase F1.3) — typed calls to `/api/v1/auth/`.
 *
 * Public endpoints (login/register/verify/reset/mfa-challenge) use plain `fetch` — a 401
 * there means bad credentials, NOT an expired access token, so it must never run the
 * refresh/logout interceptor. Authenticated endpoints (sessions, passkey register) use the
 * interceptor `authFetch`.
 */
import { authFetch } from "@/lib/api/client";
import { API_BASE_URL } from "@/lib/api/config";
import { toApiError } from "@/lib/api/errors";
import type { PublicKeyCredentialCreationOptionsJSON } from "@/lib/webauthn/client";

export interface Passkey {
  id: string;
  name: string;
  created_at: string | null;
  last_used_at: string | null;
}

export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  mfa_enabled: boolean;
}
export interface TokenResponse {
  access: string;
  refresh: string;
  user: AuthUser;
}
export interface MfaChallenge {
  mfa_required: true;
  mfa_token: string;
}
export interface Session {
  id: string;
  user_agent: string;
  ip_address: string | null;
  created_at: string;
  last_seen: string;
  expires_at: string;
}

async function handle<T>(res: Response): Promise<T> {
  const text = await res.text();
  const body = text ? JSON.parse(text) : null;
  if (!res.ok) throw toApiError(res, body);
  return body as T;
}

function publicPost<T>(path: string, body: unknown): Promise<T> {
  return fetch(`${API_BASE_URL}/api/v1/auth${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then((r) => handle<T>(r));
}

function authed(path: string, init: RequestInit): Promise<Response> {
  return authFetch(`${API_BASE_URL}/api/v1/auth${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
  });
}

export const authApi = {
  register: (data: { email: string; password: string; full_name: string }) =>
    publicPost<{ detail: string }>("/register/", data),

  verifyEmail: (token: string) => publicPost<TokenResponse>("/verify-email/", { token }),

  login: (data: { email: string; password: string }) =>
    publicPost<TokenResponse | MfaChallenge>("/login/", data),

  loginMfa: (data: { mfa_token: string; code: string }) =>
    publicPost<TokenResponse>("/login/mfa/", data),

  passwordResetRequest: (email: string) =>
    publicPost<{ detail: string }>("/password-reset/request/", { email }),

  passwordResetConfirm: (data: { token: string; password: string }) =>
    publicPost<{ detail: string }>("/password-reset/confirm/", data),

  resendVerification: (email: string) =>
    publicPost<{ detail: string }>("/resend-verification/", { email }),

  // Account self-service (authenticated).
  changePassword: (data: { current_password: string; password: string; refresh?: string }) =>
    authed("/change-password/", { method: "POST", body: JSON.stringify(data) }).then(
      (r) => handle<{ detail: string }>(r),
    ),
  changeEmail: (data: { new_email: string; password: string }) =>
    authed("/change-email/", { method: "POST", body: JSON.stringify(data) }).then(
      (r) => handle<{ detail: string }>(r),
    ),

  // Passkey as a second factor at login (begin/complete keyed by the mfa challenge token).
  passkeyAuthBegin: (mfa_token: string) =>
    publicPost<{ publicKey: PublicKeyCredentialRequestOptionsJSON }>(
      "/mfa/passkey/authenticate/begin/",
      { mfa_token },
    ),
  passkeyAuthComplete: (data: { mfa_token: string; credential: unknown }) =>
    publicPost<TokenResponse>("/mfa/passkey/authenticate/complete/", data),

  // MFA (TOTP) enrollment (authenticated).
  mfaSetupInitiate: () =>
    authed("/mfa/setup/initiate/", { method: "POST" }).then((r) => handle<{ secret: string; qr_uri: string }>(r)),
  mfaSetupConfirm: (code: string) =>
    authed("/mfa/setup/confirm/", { method: "POST", body: JSON.stringify({ code }) }).then(
      (r) => handle<{ detail: string; backup_codes: string[] }>(r),
    ),
  mfaDisable: (password: string) =>
    authed("/mfa/disable/", { method: "POST", body: JSON.stringify({ password }) }).then(
      (r) => handle<{ detail: string }>(r),
    ),

  // Passkey enrollment (authenticated).
  passkeyRegisterBegin: () =>
    authed("/mfa/passkey/register/begin/", { method: "POST" }).then(
      (r) => handle<{ publicKey: PublicKeyCredentialCreationOptionsJSON }>(r),
    ),
  passkeyRegisterComplete: (data: { credential: unknown; name?: string }) =>
    authed("/mfa/passkey/register/complete/", { method: "POST", body: JSON.stringify(data) }).then(
      (r) => handle<{ detail: string }>(r),
    ),
  listPasskeys: () => authed("/mfa/passkey/", { method: "GET" }).then((r) => handle<Passkey[]>(r)),
  deletePasskey: (credentialId: string) =>
    authed(`/mfa/passkey/${encodeURIComponent(credentialId)}/`, { method: "DELETE" }).then((r) => {
      if (!r.ok && r.status !== 204) throw toApiError(r, null);
    }),

  // Session management (authenticated).
  listSessions: () => authed("/sessions/", { method: "GET" }).then((r) => handle<Session[]>(r)),
  revokeSession: (id: string) =>
    authed(`/sessions/${id}/`, { method: "DELETE" }).then((r) => {
      if (!r.ok && r.status !== 204) throw toApiError(r, null);
    }),
  revokeAllSessions: (refresh?: string) =>
    authed("/sessions/revoke-all/", { method: "POST", body: JSON.stringify({ refresh }) }).then(
      (r) => handle<{ revoked: number }>(r),
    ),
};

/** Backend OAuth authorize URLs (full-page redirect → callback posts tokens to /oauth/callback). */
export const oauthAuthorizeUrl = {
  google: `${API_BASE_URL}/api/v1/auth/google/authorize/`,
  microsoft: `${API_BASE_URL}/api/v1/auth/microsoft/authorize/`,
};

// Minimal structural type for the begin response (the browser maps it to a real request).
export interface PublicKeyCredentialRequestOptionsJSON {
  challenge: string;
  rpId?: string;
  timeout?: number;
  userVerification?: UserVerificationRequirement;
  allowCredentials?: { id: string; type: "public-key"; transports?: string[] }[];
}
