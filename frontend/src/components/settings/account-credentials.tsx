"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { authApi } from "@/lib/auth/api";

/** Authenticated change-password + change-email (P2.17). */
export function AccountCredentials() {
  return (
    <div className="space-y-6">
      <ChangePasswordForm />
      <ChangeEmailForm />
    </div>
  );
}

function ChangePasswordForm() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setMsg(null);
    setBusy(true);
    try {
      await authApi.changePassword({ current_password: current, password: next });
      setMsg("Password changed. Other sessions were signed out.");
      setCurrent("");
      setNext("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not change password.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3 rounded-lg border p-5">
      <h2 className="font-medium">Change password</h2>
      <div className="space-y-1.5">
        <Label htmlFor="cur-pw">Current password</Label>
        <Input id="cur-pw" type="password" value={current}
          onChange={(e) => setCurrent(e.target.value)} required autoComplete="current-password" />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="new-pw">New password</Label>
        <Input id="new-pw" type="password" value={next}
          onChange={(e) => setNext(e.target.value)} required autoComplete="new-password" />
      </div>
      {msg && <p className="text-sm text-emerald-600">{msg}</p>}
      {error && <p className="text-sm text-destructive">{error}</p>}
      <Button type="submit" disabled={busy || !current || !next}>
        {busy ? "Saving…" : "Change password"}
      </Button>
    </form>
  );
}

function ChangeEmailForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setMsg(null);
    setBusy(true);
    try {
      await authApi.changeEmail({ new_email: email, password });
      setMsg("Confirmation sent to the new address. The change applies once you confirm it.");
      setEmail("");
      setPassword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not change email.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3 rounded-lg border p-5">
      <h2 className="font-medium">Change email</h2>
      <div className="space-y-1.5">
        <Label htmlFor="new-email">New email address</Label>
        <Input id="new-email" type="email" value={email}
          onChange={(e) => setEmail(e.target.value)} required />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="confirm-pw">Confirm with password</Label>
        <Input id="confirm-pw" type="password" value={password}
          onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" />
      </div>
      {msg && <p className="text-sm text-emerald-600">{msg}</p>}
      {error && <p className="text-sm text-destructive">{error}</p>}
      <Button type="submit" disabled={busy || !email || !password}>
        {busy ? "Sending…" : "Send confirmation"}
      </Button>
    </form>
  );
}
