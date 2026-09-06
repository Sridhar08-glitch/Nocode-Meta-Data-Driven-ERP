"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
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
import { EmptyState, ErrorState } from "@/components/ui/states";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import { authApi } from "@/lib/auth/api";
import { useAuthStore } from "@/lib/auth/session";
import { isPasskeySupported, registerPasskey } from "@/lib/webauthn/client";

/** Security settings (Phase F3/P1.1): self-service TOTP + passkey enrollment + account recovery. */
export function SecuritySettings() {
  return (
    <div className="space-y-8">
      <TotpSection />
      <PasskeySection />
    </div>
  );
}

// ── TOTP ────────────────────────────────────────────────────────────────────
function TotpSection() {
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const [setupOpen, setSetupOpen] = useState(false);
  const [disableOpen, setDisableOpen] = useState(false);

  const enabled = !!user?.mfa_enabled;

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-medium">Two-factor authentication (TOTP)</h2>
          <p className="text-xs text-muted-foreground">An authenticator-app code at sign-in.</p>
        </div>
        {enabled ? (
          <span className="flex items-center gap-2">
            <Badge>Enabled</Badge>
            <Button variant="outline" size="sm" onClick={() => setDisableOpen(true)}>
              Disable
            </Button>
          </span>
        ) : (
          <Button size="sm" onClick={() => setSetupOpen(true)}>
            Set up
          </Button>
        )}
      </div>

      {setupOpen && (
        <TotpSetupDialog
          onClose={() => setSetupOpen(false)}
          onEnabled={() => user && setUser({ ...user, mfa_enabled: true })}
        />
      )}
      {disableOpen && (
        <TotpDisableDialog
          onClose={() => setDisableOpen(false)}
          onDisabled={() => user && setUser({ ...user, mfa_enabled: false })}
        />
      )}
    </section>
  );
}

function TotpSetupDialog({ onClose, onEnabled }: { onClose: () => void; onEnabled: () => void }) {
  const [phase, setPhase] = useState<"loading" | "config" | "backup">("loading");
  const [secret, setSecret] = useState("");
  const [uri, setUri] = useState("");
  const [code, setCode] = useState("");
  const [backupCodes, setBackupCodes] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const started = useRef(false);

  // Kick off setup once when the dialog mounts (guarded against StrictMode double-invoke).
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    authApi
      .mfaSetupInitiate()
      .then((r) => {
        setSecret(r.secret);
        setUri(r.qr_uri);
        setPhase("config");
      })
      .catch((err) => {
        toast.error(err instanceof ApiError ? err.message : "Could not start setup");
        onClose();
      });
  }, [onClose]);

  async function confirm() {
    if (code.trim().length < 6) return;
    setBusy(true);
    try {
      const r = await authApi.mfaSetupConfirm(code.trim());
      setBackupCodes(r.backup_codes);
      setPhase("backup");
      onEnabled();
      toast.success("Two-factor enabled");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Invalid code");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Set up two-factor authentication</DialogTitle>
        </DialogHeader>
        {phase === "loading" && <Skeleton className="h-32 w-full" />}
        {phase === "config" && (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Add this secret to your authenticator app (or paste the setup URI), then enter the 6-digit code.
            </p>
            <div className="space-y-1.5">
              <Label>Secret</Label>
              <code aria-label="TOTP secret" className="block break-all rounded bg-muted px-2 py-1 font-mono text-sm">{secret}</code>
            </div>
            <details className="text-xs text-muted-foreground">
              <summary className="cursor-pointer">Setup URI (otpauth)</summary>
              <code className="mt-1 block break-all">{uri}</code>
            </details>
            <div className="space-y-1.5">
              <Label htmlFor="totp-code">6-digit code</Label>
              <Input id="totp-code" inputMode="numeric" value={code} onChange={(e) => setCode(e.target.value)} maxLength={6} autoFocus />
            </div>
            <DialogFooter>
              <Button variant="ghost" onClick={onClose}>Cancel</Button>
              <Button onClick={confirm} disabled={code.trim().length < 6 || busy}>
                {busy ? "Verifying…" : "Verify & enable"}
              </Button>
            </DialogFooter>
          </div>
        )}
        {phase === "backup" && (
          <div className="space-y-3">
            <p className="text-sm">Save these backup codes somewhere safe — they&apos;re shown only once.</p>
            <ul aria-label="Backup codes" className="grid grid-cols-2 gap-1 rounded-md border p-3 font-mono text-sm">
              {backupCodes.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
            <DialogFooter>
              <Button onClick={onClose}>Done</Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function TotpDisableDialog({ onClose, onDisabled }: { onClose: () => void; onDisabled: () => void }) {
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!password) return;
    setBusy(true);
    try {
      await authApi.mfaDisable(password);
      onDisabled();
      toast.success("Two-factor disabled");
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not disable (wrong password?)");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Disable two-factor?</DialogTitle>
        </DialogHeader>
        <div className="space-y-1.5">
          <Label htmlFor="dis-pass">Confirm your password</Label>
          <Input id="dis-pass" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoFocus />
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={submit} disabled={!password || busy}>
            {busy ? "Disabling…" : "Disable"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ── Passkeys ──────────────────────────────────────────────────────────────────
function PasskeySection() {
  const qc = useQueryClient();
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const supported = isPasskeySupported();
  const passkeys = useQuery({ queryKey: ["passkeys"], queryFn: () => authApi.listPasskeys() });
  const [addOpen, setAddOpen] = useState(false);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);

  const rows = passkeys.data ?? [];

  async function add() {
    setBusy(true);
    try {
      const begin = await authApi.passkeyRegisterBegin();
      const credential = await registerPasskey(begin.publicKey);
      await authApi.passkeyRegisterComplete({ credential, name: name.trim() || "Passkey" });
      await qc.invalidateQueries({ queryKey: ["passkeys"] });
      if (user) setUser({ ...user, mfa_enabled: true });
      toast.success("Passkey added");
      setAddOpen(false);
      setName("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : err instanceof Error ? err.message : "Could not add passkey");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    try {
      await authApi.deletePasskey(id);
      await qc.invalidateQueries({ queryKey: ["passkeys"] });
      toast.success("Passkey removed");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not remove passkey");
    }
  }

  return (
    <section className="space-y-3 border-t pt-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-medium">Passkeys</h2>
          <p className="text-xs text-muted-foreground">Sign in with a device biometric or security key.</p>
        </div>
        <Button size="sm" onClick={() => setAddOpen(true)} disabled={!supported}>
          Add passkey
        </Button>
      </div>
      {!supported && <p className="text-xs text-muted-foreground">This browser doesn&apos;t support passkeys.</p>}

      {passkeys.isLoading ? (
        <Skeleton className="h-20 w-full" />
      ) : passkeys.isError ? (
        <ErrorState title="Couldn't load passkeys" />
      ) : rows.length === 0 ? (
        <EmptyState title="No passkeys" description="Add a passkey for passwordless second-factor sign-in." className="border-0 p-0 text-left" />
      ) : (
        <ul className="space-y-2">
          {rows.map((p) => (
            <li key={p.id} className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm">
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{p.name || "Passkey"}</span>
                {p.created_at && <span className="text-xs text-muted-foreground">added {new Date(p.created_at).toLocaleDateString()}</span>}
              </span>
              <Button variant="ghost" size="sm" aria-label={`Remove passkey ${p.name || p.id}`} onClick={() => remove(p.id)}>
                Delete
              </Button>
            </li>
          ))}
        </ul>
      )}

      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add a passkey</DialogTitle>
          </DialogHeader>
          <div className="space-y-1.5">
            <Label htmlFor="pk-name">Name (optional)</Label>
            <Input id="pk-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. MacBook Touch ID" autoFocus />
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setAddOpen(false)}>Cancel</Button>
            <Button onClick={add} disabled={busy}>
              {busy ? "Waiting for device…" : "Register passkey"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
