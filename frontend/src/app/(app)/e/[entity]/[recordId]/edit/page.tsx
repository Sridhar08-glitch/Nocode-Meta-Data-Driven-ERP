"use client";

import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/states";
import { toast } from "@/components/ui/toast";
import { FormRenderer } from "@/features/form-renderer";
import { ApiError } from "@/lib/api/errors";
import { useFormSchema } from "@/lib/metadata/hooks";
import { useRecord, useUpdateRecord } from "@/lib/records/hooks";

export default function EditRecordPage({
  params,
}: {
  params: { entity: string; recordId: string };
}) {
  const { entity: slug, recordId } = params;
  const router = useRouter();
  const schema = useFormSchema(slug);
  const record = useRecord(slug, recordId);
  const update = useUpdateRecord(slug);

  if (schema.isLoading || record.isLoading) return <Skeleton className="h-96 w-full max-w-2xl" />;
  if (schema.isError || !schema.data || record.isError || !record.data) {
    return <ErrorState title="Couldn't load the form" />;
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="sm" onClick={() => router.push(`/e/${slug}/${recordId}`)}>
          ← Back
        </Button>
        <h1 className="text-xl font-semibold">Edit {schema.data.entity_name}</h1>
      </div>
      <FormRenderer
        schema={schema.data}
        initialValues={record.data}
        submitLabel="Save changes"
        onSubmit={async (values) => {
          try {
            await update.mutateAsync({ id: recordId, data: values });
            toast.success("Saved");
            router.push(`/e/${slug}/${recordId}`);
          } catch (err) {
            toast.error(err instanceof ApiError ? err.message : "Could not save");
          }
        }}
      />
    </div>
  );
}
