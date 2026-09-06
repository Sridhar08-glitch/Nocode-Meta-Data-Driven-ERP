"use client";

import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/states";
import { toast } from "@/components/ui/toast";
import { FormRenderer } from "@/features/form-renderer";
import { ApiError } from "@/lib/api/errors";
import { useEntityMeta, useFormSchema } from "@/lib/metadata/hooks";
import { useCreateRecord } from "@/lib/records/hooks";

export default function NewRecordPage({ params }: { params: { entity: string } }) {
  const slug = params.entity;
  const router = useRouter();
  const { entity } = useEntityMeta(slug);
  const schema = useFormSchema(slug);
  const create = useCreateRecord(slug);

  if (schema.isLoading) return <Skeleton className="h-96 w-full max-w-2xl" />;
  if (schema.isError || !schema.data) return <ErrorState title="Couldn't load the form" />;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="sm" onClick={() => router.push(`/e/${slug}`)}>
          ← Back
        </Button>
        <h1 className="text-xl font-semibold">New {entity?.name ?? schema.data.entity_name}</h1>
      </div>
      <FormRenderer
        schema={schema.data}
        submitLabel="Create"
        onSubmit={async (values) => {
          try {
            const created = await create.mutateAsync(values);
            toast.success("Record created");
            router.push(`/e/${slug}/${created.id}`);
          } catch (err) {
            toast.error(err instanceof ApiError ? err.message : "Could not create record");
          }
        }}
      />
    </div>
  );
}
