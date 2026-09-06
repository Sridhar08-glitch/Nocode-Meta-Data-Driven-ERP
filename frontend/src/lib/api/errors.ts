/**
 * Normalised API error (Phase F1.2).
 *
 * Maps DRF responses to a typed shape: top-level `message`, per-field `fieldErrors`
 * ({field: [msgs]}), and rate-limit info (`retryAfter` seconds + raw `X-RateLimit-*`).
 */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;
  readonly fieldErrors: Record<string, string[]>;
  readonly retryAfter: number | null;
  readonly rateLimit: Record<string, string>;

  constructor(args: {
    status: number;
    detail?: unknown;
    message?: string;
    fieldErrors?: Record<string, string[]>;
    retryAfter?: number | null;
    rateLimit?: Record<string, string>;
  }) {
    super(args.message ?? `API error ${args.status}`);
    this.name = "ApiError";
    this.status = args.status;
    this.detail = args.detail ?? null;
    this.fieldErrors = args.fieldErrors ?? {};
    this.retryAfter = args.retryAfter ?? null;
    this.rateLimit = args.rateLimit ?? {};
  }

  get isRateLimited(): boolean {
    return this.status === 429;
  }
}

function parseRetryAfter(headers: Headers): number | null {
  const raw = headers.get("Retry-After");
  if (!raw) return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

function collectRateLimit(headers: Headers): Record<string, string> {
  const out: Record<string, string> = {};
  headers.forEach((value, key) => {
    if (key.toLowerCase().startsWith("x-ratelimit")) out[key.toLowerCase()] = value;
  });
  return out;
}

/** Build an `ApiError` from a non-2xx response and its already-parsed JSON body. */
export function toApiError(response: { status: number; headers: Headers }, body: unknown): ApiError {
  const fieldErrors: Record<string, string[]> = {};
  let message: string | undefined;

  if (body && typeof body === "object") {
    const b = body as Record<string, unknown>;
    if (typeof b.detail === "string") {
      message = b.detail;
    }
    for (const [key, value] of Object.entries(b)) {
      if (key === "detail") continue;
      if (Array.isArray(value) && value.every((v) => typeof v === "string")) {
        fieldErrors[key] = value as string[];
      } else if (typeof value === "string") {
        fieldErrors[key] = [value];
      }
    }
    if (!message) {
      const firstField = Object.values(fieldErrors)[0];
      if (firstField?.[0]) message = firstField[0];
    }
  } else if (typeof body === "string" && body) {
    message = body;
  }

  return new ApiError({
    status: response.status,
    detail: body,
    message,
    fieldErrors,
    retryAfter: parseRetryAfter(response.headers),
    rateLimit: collectRateLimit(response.headers),
  });
}
