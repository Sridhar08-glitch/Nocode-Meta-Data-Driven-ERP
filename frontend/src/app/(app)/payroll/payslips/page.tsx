"use client";

import { PayrollNav } from "@/components/payroll/payroll-nav";
import { PayslipsPanel } from "@/components/payroll/payslips-panel";

export default function PayrollPayslipsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Payslips</h1>
        <p className="text-sm text-muted-foreground">Read-only payslips with a line-level breakdown. Immutable once posted.</p>
      </div>
      <PayrollNav />
      <PayslipsPanel />
    </div>
  );
}
