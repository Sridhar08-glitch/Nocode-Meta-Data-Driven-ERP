"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { WorkspaceInvitation } from "@/lib/tenant/admin-api";
import {
  useCancelInvitation,
  useInvitations,
  useInvite,
  useResendInvitation,
} from "@/lib/tenant/admin-hooks";

const ROLES = ["admin", "member", "viewer"] as const;

/** Invite teammates by email + manage pending invitations (P2.17 invitation lifecycle). */
export function InvitationsPanel() {
  const invitations = useInvitations();
  const invite = useInvite();
  const resend = useResendInvitation();
  const cancel = useCancelInvitation();

  const [email, setEmail] = useState("");
  const [role, setRole] = useState<(typeof ROLES)[number]>("member");
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function flash(setter: (v: string | null) => void, value: string) {
    setter(value);
    window.setTimeout(() => setter(null), 4000);
  }

  async function onInvite(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await invite.mutateAsync({ email: email.trim(), role });
      setEmail("");
      flash(setMsg, "Invitation sent.");
    } catch (err) {
      flash(setError, err instanceof Error ? err.message : "Could not send the invitation.");
    }
  }

  const pending = (invitations.data ?? []).filter((i) => i.status === "pending");

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold">Invitations</h2>
        <p className="text-sm text-muted-foreground">
          Invite teammates by email — they accept and set up their account themselves.
        </p>
      </div>

      <form onSubmit={onInvite} className="flex flex-wrap items-end gap-3 rounded-lg border p-4">
        <div className="flex-1 min-w-[220px] space-y-1.5">
          <label className="text-xs font-medium" htmlFor="inv-email">Email</label>
          <Input id="inv-email" type="email" required value={email}
            onChange={(e) => setEmail(e.target.value)} placeholder="teammate@company.com" />
        </div>
        <div className="space-y-1.5">
          <label className="text-xs font-medium">Role</label>
          <Select value={role} onValueChange={(v) => setRole(v as (typeof ROLES)[number])}>
            <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
            <SelectContent>
              {ROLES.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <Button type="submit" disabled={!email.trim() || invite.isPending}>
          {invite.isPending ? "Sending…" : "Send invite"}
        </Button>
      </form>

      {msg && <p className="text-sm text-emerald-600">{msg}</p>}
      {error && <p className="text-sm text-destructive">{error}</p>}

      {pending.length > 0 && (
        <ul className="divide-y rounded-lg border">
          {pending.map((inv: WorkspaceInvitation) => (
            <li key={inv.id} className="flex items-center justify-between gap-3 p-3">
              <div>
                <div className="font-medium">{inv.email}</div>
                <div className="text-xs text-muted-foreground">
                  <Badge variant="secondary">{inv.role}</Badge> · expires{" "}
                  {new Date(inv.expires_at).toLocaleDateString()}
                </div>
              </div>
              <div className="space-x-1">
                <Button size="sm" variant="ghost"
                  onClick={() => resend.mutateAsync(inv.id).then(() => flash(setMsg, "Invitation resent."))}>
                  Resend
                </Button>
                <Button size="sm" variant="ghost" className="text-destructive"
                  onClick={() => cancel.mutateAsync(inv.id)}>
                  Cancel
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
