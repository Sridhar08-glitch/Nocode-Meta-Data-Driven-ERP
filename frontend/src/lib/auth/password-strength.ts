/**
 * Client-side password strength (Phase F1.3) — UX only; the backend's Django validators
 * (min 10, not common, not all-numeric) are authoritative on submit.
 */
export interface PasswordStrength {
  /** 0–4 */
  score: number;
  label: "Very weak" | "Weak" | "Fair" | "Good" | "Strong";
  /** Hard rule mirrored from the backend: at least 10 characters. */
  meetsMinLength: boolean;
  suggestions: string[];
}

const LABELS: PasswordStrength["label"][] = ["Very weak", "Weak", "Fair", "Good", "Strong"];

export function scorePassword(password: string): PasswordStrength {
  const suggestions: string[] = [];
  let score = 0;

  if (password.length >= 10) score++;
  else suggestions.push("Use at least 10 characters");
  if (password.length >= 14) score++;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
  else suggestions.push("Mix upper and lower case");
  if (/\d/.test(password)) score++;
  else suggestions.push("Add a number");
  if (/[^A-Za-z0-9]/.test(password)) score++;
  else suggestions.push("Add a symbol");

  if (/^\d+$/.test(password) && password.length > 0) {
    score = Math.min(score, 1);
    suggestions.push("Don't use only numbers");
  }

  const clamped = Math.max(0, Math.min(4, score));
  return {
    score: clamped,
    label: LABELS[clamped],
    meetsMinLength: password.length >= 10,
    suggestions,
  };
}
