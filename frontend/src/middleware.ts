import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { AUTH_COOKIE } from "@/lib/auth/constants";

/**
 * Route protection (Phase F1.3).
 *
 * Gates the authenticated app using a non-sensitive presence cookie (`nexus_auth`) set on
 * login/verify/OAuth. Tokens never live in cookies — real validation is the API
 * 401→refresh→logout path; this only keeps unauthenticated users out of app shells and
 * authenticated users off the auth pages.
 */
const PUBLIC_PREFIXES = [
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
  "/oauth",
  "/f", // public forms (F3.8)
  "/portal", // external portal realm (F3.7)
];

const AUTH_PAGES = new Set([
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
]);

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const authed = req.cookies.get(AUTH_COOKIE)?.value === "1";

  if (pathname === "/") {
    return NextResponse.redirect(new URL(authed ? "/home" : "/login", req.url));
  }

  const isPublic = PUBLIC_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`));

  if (isPublic) {
    // Keep signed-in users out of the auth pages.
    if (authed && AUTH_PAGES.has(pathname)) {
      return NextResponse.redirect(new URL("/home", req.url));
    }
    return NextResponse.next();
  }

  // Protected route — require the presence cookie.
  if (!authed) {
    const url = new URL("/login", req.url);
    if (pathname !== "/home") url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  // Run on everything except Next internals, static assets, and API proxy paths.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.\\w+$).*)"],
};
