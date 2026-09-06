"use client";

import { useRouter } from "next/navigation";

import { FormBuilder } from "@/components/builder/form-builder";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/states";
import { useFields, useForm } from "@/lib/metadata/builder-hooks";
import { useEntityMeta } from "@/lib/metadata/hooks";

export default function FormBuilderPage({
  params,
}: {
  params: { entity: string; formId: string };
}) {
  const slug = params.entity;
  const isNew = params.formId === "new";
  const router = useRouter();
  const { entity } = useEntityMeta(slug);
  const fields = useFields(slug);
  const form = useForm(slug, isNew ? "" : params.formId);

  const loading = fields.isLoading || (!isNew && form.isLoading);
  if (loading) return <Skeleton className="h-96 w-full" />;
  if (fields.isError || (!isNew && form.isError)) return <ErrorState title="Couldn't load the form" />;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="sm" onClick={() => router.push(`/studio/${slug}`)}>
          ← Back
        </Button>
        <h1 className="text-xl font-semibold">
          {isNew ? "New form" : "Edit form"} · {entity?.name ?? slug}
        </h1>
      </div>
      <FormBuilder
        entity={slug}
        entityName={entity?.name ?? slug}
        fields={fields.data ?? []}
        form={isNew ? undefined : form.data}
        onSaved={() => router.push(`/studio/${slug}`)}
      />
    </div>
  );
}
