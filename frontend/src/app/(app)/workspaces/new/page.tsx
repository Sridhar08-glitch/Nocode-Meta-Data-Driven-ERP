"use client";

import { useRouter } from "next/navigation";

import { CreateWorkspace } from "@/components/tenant/create-workspace";

export default function NewWorkspacePage() {
  const router = useRouter();
  return (
    <div className="flex justify-center py-10">
      <CreateWorkspace onCreated={() => router.push("/home")} />
    </div>
  );
}
