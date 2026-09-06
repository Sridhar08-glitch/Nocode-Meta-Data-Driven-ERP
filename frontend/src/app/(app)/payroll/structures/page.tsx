"use client";

import { PayrollNav } from "@/components/payroll/payroll-nav";
import { StructuresPanel } from "@/components/payroll/structures-panel";

export default function PayrollStructuresPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Salary structures</h1>
        <p className="text-sm text-muted-foreground">Group the earning and deduction components used to compute payslips.</p>
      </div>
      <PayrollNav />
      <StructuresPanel />
    </div>
  );
}
