"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/states";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import type { BrandingSettings as TBranding } from "@/lib/branding/api";
import { useBranding, useSaveSmtp, useSmtpConfig, useTestSmtp, useUpdateBranding } from "@/lib/branding/hooks";
import { isHexColor, validateBrandingForm } from "@/lib/branding/validation";

type ColorKey =
  | "color_primary"
  | "color_secondary"
  | "color_accent"
  | "color_background"
  | "color_surface"
  | "color_text_primary";

const COLOR_FIELDS: { key: ColorKey; label: string }[] = [
  { key: "color_primary", label: "Primary" },
  { key: "color_secondary", label: "Secondary" },
  { key: "color_accent", label: "Accent" },
  { key: "color_background", label: "Background" },
  { key: "color_surface", label: "Surface" },
  { key: "color_text_primary", label: "Text" },
];

/** Backend model defaults (apps/branding/models.py) — used by "Restore defaults". */
const DEFAULT_BRANDING: TBranding = {
  app_name: "",
  logo_url: "",
  color_primary: "#6366f1",
  color_secondary: "#8b5cf6",
  color_accent: "#06b6d4",
  color_background: "#ffffff",
  color_surface: "#f8fafc",
  color_text_primary: "#0f172a",
  custom_css: "",
};

/** Branding settings (Phase F3.1 + polish): validated form, live preview, impact warning, restore. */
export function BrandingSettings() {
  const branding = useBranding();
  const update = useUpdateBranding();
  const [form, setForm] = useState<TBranding>({});
  const [confirmReset, setConfirmReset] = useState(false);

  useEffect(() => {
    if (branding.data) setForm(branding.data);
  }, [branding.data]);

  if (branding.isLoading) return <Skeleton className="h-64 w-full" />;
  if (branding.isError) return <ErrorState title="Couldn't load branding" />;

  const set = (k: keyof TBranding & string, v: string) => setForm((f) => ({ ...f, [k]: v }));
  const validation = validateBrandingForm(form);

  async function save() {
    if (validation.hasErrors) return;
    try {
      await update.mutateAsync({
        app_name: form.app_name,
        logo_url: form.logo_url,
        favicon_url: form.favicon_url,
        font_family_heading: form.font_family_heading,
        font_family_body: form.font_family_body,
        default_theme: form.default_theme,
        allow_theme_toggle: form.allow_theme_toggle,
        ui_density: form.ui_density,
        border_radius: form.border_radius,
        login_headline: form.login_headline,
        login_subtext: form.login_subtext,
        login_background_url: form.login_background_url,
        custom_css: form.custom_css,
        ...Object.fromEntries(COLOR_FIELDS.map((c) => [c.key, form[c.key]])),
      });
      toast.success("Branding saved");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not save branding");
    }
  }

  return (
    <div className="space-y-8">
      <div className="grid gap-6 lg:grid-cols-2">
        <section className="space-y-4">
          <div className="flex flex-wrap gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="b-app">App name</Label>
              <Input id="b-app" value={form.app_name ?? ""} onChange={(e) => set("app_name", e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="b-logo">Logo URL</Label>
              <Input id="b-logo" value={form.logo_url ?? ""} onChange={(e) => set("logo_url", e.target.value)} className="w-72" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="b-favicon">Favicon URL</Label>
              <Input id="b-favicon" value={form.favicon_url ?? ""} onChange={(e) => set("favicon_url", e.target.value)} className="w-72" />
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="b-font-h">Heading font</Label>
              <Input id="b-font-h" value={form.font_family_heading ?? ""} onChange={(e) => set("font_family_heading", e.target.value)} placeholder="Inter" className="w-48" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="b-font-b">Body font</Label>
              <Input id="b-font-b" value={form.font_family_body ?? ""} onChange={(e) => set("font_family_body", e.target.value)} placeholder="Inter" className="w-48" />
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="b-theme">Default theme</Label>
              <select id="b-theme" value={form.default_theme ?? "system"} onChange={(e) => set("default_theme", e.target.value)} className="h-9 rounded-md border border-input bg-background px-2 text-sm">
                <option value="system">System</option>
                <option value="light">Light</option>
                <option value="dark">Dark</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="b-density">Density</Label>
              <select id="b-density" value={form.ui_density ?? "comfortable"} onChange={(e) => set("ui_density", e.target.value)} className="h-9 rounded-md border border-input bg-background px-2 text-sm">
                <option value="comfortable">Comfortable</option>
                <option value="compact">Compact</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="b-radius">Corner radius</Label>
              <select id="b-radius" value={form.border_radius ?? "md"} onChange={(e) => set("border_radius", e.target.value)} className="h-9 rounded-md border border-input bg-background px-2 text-sm">
                <option value="none">None</option>
                <option value="sm">Small</option>
                <option value="md">Medium</option>
                <option value="lg">Large</option>
                <option value="xl">Extra large</option>
              </select>
            </div>
            <div className="flex items-end gap-2 pb-1.5">
              <input id="b-toggle" type="checkbox" checked={form.allow_theme_toggle ?? true} onChange={(e) => setForm((f) => ({ ...f, allow_theme_toggle: e.target.checked }))} className="size-4" />
              <Label htmlFor="b-toggle">Allow users to toggle theme</Label>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Colors</Label>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {COLOR_FIELDS.map((c) => (
                <div key={c.key} className="space-y-1">
                  <div className="flex items-center gap-2">
                    <input
                      type="color"
                      aria-label={`${c.label} color`}
                      value={isHexColor(form[c.key] ?? "") ? (form[c.key] as string) : "#000000"}
                      onChange={(e) => set(c.key, e.target.value)}
                      className="size-8 rounded border"
                    />
                    <Input aria-label={`${c.label} hex`} value={form[c.key] ?? ""} onChange={(e) => set(c.key, e.target.value)} className="h-8" />
                  </div>
                  {validation.colors[c.key] && (
                    <p role="alert" className="text-xs text-destructive">
                      {validation.colors[c.key]}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="b-css">Custom CSS (sanitized server-side)</Label>
            <Textarea id="b-css" rows={4} value={form.custom_css ?? ""} onChange={(e) => set("custom_css", e.target.value)} className="font-mono text-xs" />
            {validation.cssError && (
              <p role="alert" className="text-xs text-destructive">
                {validation.cssError}
              </p>
            )}
          </div>

          <div className="space-y-3 border-t pt-3">
            <Label className="text-muted-foreground">Login page</Label>
            <div className="space-y-1.5">
              <Label htmlFor="b-login-h">Headline</Label>
              <Input id="b-login-h" value={form.login_headline ?? ""} onChange={(e) => set("login_headline", e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="b-login-s">Subtext</Label>
              <Input id="b-login-s" value={form.login_subtext ?? ""} onChange={(e) => set("login_subtext", e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="b-login-bg">Background image URL</Label>
              <Input id="b-login-bg" value={form.login_background_url ?? ""} onChange={(e) => set("login_background_url", e.target.value)} />
            </div>
          </div>
        </section>

        <section className="space-y-2">
          <Label>Preview</Label>
          <BrandingPreview form={form} />
        </section>
      </div>

      <div className="space-y-3 border-t pt-4">
        <p className="rounded-md bg-muted/50 px-3 py-2 text-xs text-muted-foreground" role="note">
          Branding changes affect all users in this workspace.
        </p>
        <div className="flex gap-2">
          <Button onClick={save} disabled={validation.hasErrors || update.isPending}>
            {update.isPending ? "Saving…" : "Save branding"}
          </Button>
          <Button variant="outline" onClick={() => setConfirmReset(true)}>
            Restore defaults
          </Button>
        </div>
      </div>

      <SmtpSettings />

      <Dialog open={confirmReset} onOpenChange={setConfirmReset}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Restore branding defaults?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            This resets the app name, logo, theme colors, and custom CSS to the platform defaults in
            the form. Nothing is saved until you click <strong>Save branding</strong>.
          </p>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setConfirmReset(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => {
                setForm((f) => ({ ...f, ...DEFAULT_BRANDING }));
                setConfirmReset(false);
                toast.info("Defaults restored — click Save to apply");
              }}
            >
              Restore defaults
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/** Pure client-side preview of representative UI using the in-progress form (no mutation). */
function BrandingPreview({ form }: { form: TBranding }) {
  const safe = (v: string | undefined, fallback: string) => (v && isHexColor(v) ? v : fallback);
  const bg = safe(form.color_background, "#ffffff");
  const surface = safe(form.color_surface, "#f8fafc");
  const primary = safe(form.color_primary, "#6366f1");
  const text = safe(form.color_text_primary, "#0f172a");

  return (
    <div aria-label="Branding preview" className="overflow-hidden rounded-lg border" style={{ background: bg, color: text }}>
      <div className="flex">
        <div className="w-24 shrink-0 p-2 text-xs" style={{ background: surface }} aria-label="Preview sidebar">
          <div className="mb-2 truncate font-semibold">{form.app_name || "Sridhar ERP"}</div>
          <div className="space-y-1">
            <div className="rounded px-1.5 py-1" style={{ background: primary, color: "#fff" }}>
              Home
            </div>
            <div className="px-1.5 py-1">Records</div>
          </div>
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 border-b px-3 py-2" aria-label="Preview header">
            {form.logo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={form.logo_url} alt="" className="size-5 rounded object-contain" />
            ) : (
              <span className="size-5 rounded" style={{ background: primary }} />
            )}
            <span className="text-sm font-medium">{form.app_name || "Sridhar ERP"}</span>
          </div>
          <div className="p-3">
            <div className="rounded-md border p-3 text-xs" style={{ background: surface }} aria-label="Preview card">
              <p className="mb-2 font-medium">Sample card</p>
              <button type="button" className="rounded-md px-3 py-1.5 text-xs font-medium text-white" style={{ background: primary }}>
                Primary button
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function SmtpSettings() {
  const smtp = useSmtpConfig();
  const save = useSaveSmtp();
  const test = useTestSmtp();
  const [host, setHost] = useState("");
  const [port, setPort] = useState(587);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [fromEmail, setFromEmail] = useState("");
  const [lastTest, setLastTest] = useState<{ ok: boolean; message: string; at: string } | null>(null);

  useEffect(() => {
    const d = smtp.data;
    if (d && "host" in d) {
      setHost(d.host ?? "");
      setPort(d.port ?? 587);
      setUsername(d.username ?? "");
      setFromEmail(d.from_email ?? "");
    }
  }, [smtp.data]);

  const valid = !!host.trim() && !!fromEmail.trim();

  async function persist() {
    if (!valid) return;
    try {
      await save.mutateAsync({ host: host.trim(), port, username: username.trim(), password: password || undefined, from_email: fromEmail.trim() });
      setPassword("");
      toast.success("SMTP saved");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not save SMTP");
    }
  }
  async function runTest() {
    const at = new Date().toLocaleString();
    try {
      const res = await test.mutateAsync();
      if (res.success) {
        setLastTest({ ok: true, message: "Success", at });
        toast.success("SMTP test passed");
      } else {
        setLastTest({ ok: false, message: res.error || "Test failed", at });
        toast.error(res.error || "SMTP test failed");
      }
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Test failed";
      setLastTest({ ok: false, message, at });
      toast.error(message);
    }
  }

  return (
    <section className="space-y-4 border-t pt-6">
      <h2 className="text-sm font-medium text-muted-foreground">Outgoing email (SMTP)</h2>
      <div className="flex flex-wrap gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="s-host">Host</Label>
          <Input id="s-host" value={host} onChange={(e) => setHost(e.target.value)} className="w-56" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="s-port">Port</Label>
          <Input id="s-port" type="number" value={port} onChange={(e) => setPort(Number(e.target.value))} className="w-24" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="s-user">Username</Label>
          <Input id="s-user" value={username} onChange={(e) => setUsername(e.target.value)} className="w-56" />
        </div>
      </div>
      <div className="flex flex-wrap gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="s-pass">Password (write-only)</Label>
          <Input id="s-pass" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••" className="w-56" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="s-from">From email</Label>
          <Input id="s-from" type="email" value={fromEmail} onChange={(e) => setFromEmail(e.target.value)} className="w-64" />
        </div>
      </div>
      <div className="flex items-center gap-3">
        <Button onClick={persist} disabled={!valid || save.isPending}>
          {save.isPending ? "Saving…" : "Save SMTP"}
        </Button>
        <Button variant="outline" onClick={runTest} disabled={test.isPending}>
          {test.isPending ? "Testing…" : "Send test"}
        </Button>
        {lastTest && (
          <div className="text-xs" role="status" aria-label="Last SMTP test">
            <span className={lastTest.ok ? "text-emerald-600" : "text-destructive"}>
              {lastTest.ok ? "✓ " : "✗ "}
              {lastTest.message}
            </span>
            <span className="ml-2 text-muted-foreground">{lastTest.at}</span>
          </div>
        )}
      </div>
    </section>
  );
}
