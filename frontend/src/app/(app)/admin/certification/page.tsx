"use client";

import { CertificationConsole } from "@/components/certification/certification-console";

/**
 * Enterprise Certification (Phase P2.16) — the cross-module integration dashboard:
 * certification report + module health + executive readiness + architecture validation +
 * integration registry + business simulations. Read-only; all results come from the
 * backend `apps/certification` orchestrator (which reads existing engines, never a new one).
 */
export default function AdminCertificationPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Enterprise certification</h1>
        <p className="text-sm text-muted-foreground">
          End-to-end cross-module integration health, architecture validation, and live business
          simulations.
        </p>
      </div>
      <CertificationConsole />
    </div>
  );
}
