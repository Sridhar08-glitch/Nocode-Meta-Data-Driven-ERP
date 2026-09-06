"use client";

import { useEffect, useState } from "react";

import { BrandMark } from "@/components/shell/brand-mark";
import { ThemeToggle } from "@/components/theme-toggle";
import { readBrandingSnapshot, type WorkspaceBranding } from "@/lib/branding/apply";

/**
 * Pre-auth branding chrome for the login / register / reset pages. There is no workspace/TenantContext
 * before sign-in, so it reads the last-known branding SNAPSHOT (written by applyBranding while a
 * workspace was active) — reusing the SAME WorkspaceBranding fields, no new endpoint, no new engine.
 * Shows the workspace logo/name, optional login headline + subtext, and an optional background image.
 */
export function AuthShell({ children }: { children: React.ReactNode }) {
  const [b, setB] = useState<WorkspaceBranding | null>(null);
  useEffect(() => setB(readBrandingSnapshot()), []);

  const bg = b?.login_background_url;
  return (
    <div
      className="flex min-h-screen flex-col bg-cover bg-center"
      style={bg ? { backgroundImage: `linear-gradient(hsl(var(--background)/0.85), hsl(var(--background)/0.85)), url(${bg})` } : undefined}
    >
      <header className="flex items-center justify-between p-4">
        <BrandMark logoUrl={b?.logo_url} appName={b?.app_name} size={26} />
        <ThemeToggle />
      </header>
      <main className="flex flex-1 flex-col items-center justify-center px-4 pb-16">
        {(b?.login_headline || b?.login_subtext) && (
          <div className="mb-6 max-w-sm text-center">
            {b?.login_headline && <h1 className="text-xl font-heading font-semibold">{b.login_headline}</h1>}
            {b?.login_subtext && <p className="mt-1 text-sm text-muted-foreground">{b.login_subtext}</p>}
          </div>
        )}
        <div className="w-full max-w-sm space-y-6 rounded-lg border border-border bg-card p-6 shadow-sm">
          {children}
        </div>
      </main>
    </div>
  );
}
