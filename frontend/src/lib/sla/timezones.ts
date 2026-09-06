/**
 * IANA timezone list for the Business Calendar timezone picker (Phase F2.7 hardening).
 * Sourced from the runtime via `Intl.supportedValuesOf("timeZone")` when available, with a
 * small static fallback for environments that don't expose it. The stored value is the raw
 * IANA id (unchanged backend contract).
 */
const FALLBACK_TIMEZONES = [
  "UTC",
  "Europe/London",
  "Europe/Paris",
  "Europe/Berlin",
  "Europe/Madrid",
  "Africa/Cairo",
  "Asia/Qatar",
  "Asia/Dubai",
  "Asia/Riyadh",
  "Asia/Kolkata",
  "Asia/Singapore",
  "Asia/Tokyo",
  "Australia/Sydney",
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "America/Sao_Paulo",
];

function loadTimezones(): string[] {
  try {
    const supported = (Intl as unknown as { supportedValuesOf?: (k: string) => string[] }).supportedValuesOf;
    if (typeof supported === "function") {
      const list = supported("timeZone");
      if (Array.isArray(list) && list.length > 0) {
        return ["UTC", ...list.filter((t) => t !== "UTC")];
      }
    }
  } catch {
    // fall through to the static list
  }
  return FALLBACK_TIMEZONES;
}

export const IANA_TIMEZONES: string[] = loadTimezones();
