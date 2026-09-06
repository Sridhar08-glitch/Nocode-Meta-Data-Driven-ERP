"use client";

import { InputsPanel } from "@/components/payroll/inputs-panel";
import { PayrollNav } from "@/components/payroll/payroll-nav";

export default function PayrollLoansPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Loans & inputs</h1>
        <p className="text-sm text-muted-foreground">Loans, advances, overtime and one-time adjustments feed the next payroll calculation.</p>
      </div>
      <PayrollNav />
      <InputsPanel />
    </div>
  );
}
