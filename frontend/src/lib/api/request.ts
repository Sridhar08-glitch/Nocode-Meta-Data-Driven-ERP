/**
 * Thin typed GET/JSON helpers over the auth-interceptor fetch (Phase F1.4).
 * For endpoints whose generated types are imprecise (dynamic/APIView), callers pass an
 * explicit `T`. Errors normalise to `ApiError`.
 */
import { authFetch } from "./client";
import { API_BASE_URL } from "./config";
import { toApiError } from "./errors";

async function parse<T>(res: Response): Promise<T> {
  const text = await res.text();
  const body = text ? JSON.parse(text) : null;
  if (!res.ok) throw toApiError(res, body);
  return body as T;
}

export function apiGet<T>(path: string): Promise<T> {
  return authFetch(`${API_BASE_URL}${path}`).then((r) => parse<T>(r));
}

export function apiSend<T>(path: string, method: string, body?: unknown): Promise<T> {
  return authFetch(`${API_BASE_URL}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  }).then((r) => parse<T>(r));
}

/** POST multipart/form-data (file uploads). Lets the browser set the boundary Content-Type. */
export function apiUpload<T>(path: string, form: FormData): Promise<T> {
  return authFetch(`${API_BASE_URL}${path}`, { method: "POST", body: form }).then((r) => parse<T>(r));
}

/** Fetch a binary export (CSV/XLSX/PDF) as a Blob; throws `ApiError` on non-ok. */
export async function apiBlob(path: string): Promise<Blob> {
  const res = await authFetch(`${API_BASE_URL}${path}`);
  if (!res.ok) throw toApiError(res, null);
  return res.blob();
}

/** Trigger a browser download of a fetched export blob. */
export async function downloadFile(path: string, filename: string): Promise<void> {
  const blob = await apiBlob(path);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
