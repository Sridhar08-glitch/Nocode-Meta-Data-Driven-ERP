"use client";

import { useEffect } from "react";

import { logout } from "@/lib/auth/session";
import { registerAuthFailureHandler } from "@/lib/auth/token-store";

/** Wires the interceptor's auth-failure (reuse-detection / expired refresh) to a clean
 *  client logout + redirect. Mounted once in the root providers. */
export function AuthInit() {
  useEffect(() => {
    registerAuthFailureHandler(() => logout());
    return () => registerAuthFailureHandler(null);
  }, []);
  return null;
}
