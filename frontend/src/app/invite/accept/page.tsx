"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { workspaceAdminApi } from "@/lib/tenant/admin-api";

type State =
  | { kind: "loading" }
  | { kind: "need-token" }
  | { kind: "accepted"; role: string }
  | { kind: "error"; message: string };

/**
 * Invitation acceptance (P2.17). Lives outside the app shell so a freshly-invited
 * user (who may belong to no workspace yet) can accept. The auth middleware still
 * requires sign-in first; a brand-new invitee registers with the invited email,
 * then returns here.
 */
export default function AcceptInvitePage() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("token");
    if (!token) {
      setState({ kind: "need-token" });
      return;
    }
    workspaceAdminApi
      .acceptInvitation(token)
      .then((m) => setState({ kind: "accepted", role: m.role }))
      .catch((err) =>
        setState({ kind: "error", message: err instanceof Error ? err.message : "Could not accept the invitation." }));
  }, []);

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-md space-y-4 rounded-lg border p-6 text-center">
        <h1 className="text-lg font-semibold">Workspace invitation</h1>
        {state.kind === "loading" && <Spinner />}
        {state.kind === "need-token" && (
          <p className="text-sm text-destructive">This invitation link is missing its token.</p>
        )}
        {state.kind === "error" && (
          <>
            <p className="text-sm text-destructive">{state.message}</p>
            <p className="text-xs text-muted-foreground">
              If you were invited under a different email, sign in with that account first.
            </p>
          </>
        )}
        {state.kind === "accepted" && (
          <>
            <p className="text-sm text-emerald-600">
              Invitation accepted — you joined as {state.role}.
            </p>
            <Button asChild className="w-full">
              <Link href="/home">Go to workspace</Link>
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
