"use client";

import { useParams } from "next/navigation";

import { PublicFormRuntime } from "@/components/public-forms/public-form-runtime";

/** Public, unauthenticated form page at /f/[formId]. Outside the member shell + portal realm. */
export default function PublicFormPage() {
  const params = useParams<{ formId: string }>();
  return (
    <div className="mx-auto max-w-xl p-6">
      <PublicFormRuntime formId={params.formId} />
    </div>
  );
}
