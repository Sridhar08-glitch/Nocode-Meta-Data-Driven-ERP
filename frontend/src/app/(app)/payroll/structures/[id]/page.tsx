"use client";

import { useParams } from "next/navigation";

import { PayrollNav } from "@/components/payroll/payroll-nav";
import { StructureDetail } from "@/components/payroll/structure-detail";

export default function PayrollStructureDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id;
  return (
    <div className="space-y-6">
      <PayrollNav />
      {id ? <StructureDetail structureId={id} /> : null}
    </div>
  );
}
