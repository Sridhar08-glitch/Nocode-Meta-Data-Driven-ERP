/** Base URL for the backend (kept separate to avoid import cycles client↔refresh). */
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
