"use client";

import { useRouter } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import { useDeleteForm, useForms } from "@/lib/metadata/builder-hooks";
import type { FormDefinition } from "@/lib/metadata/types";

export function FormsPanel({ entity }: { entity: string }) {
  const router = useRouter();
  const forms = useForms(entity);
  const del = useDeleteForm(entity);

  if (forms.isLoading) return <Skeleton className="h-48 w-full" />;
  if (forms.isError) return <ErrorState title="Couldn't load forms" />;

  const rows = forms.data ?? [];

  async function remove(f: FormDefinition) {
    try {
      await del.mutateAsync(f.id);
      toast.success("Form deleted");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not delete form");
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-muted-foreground">{rows.length} forms</h2>
        <Button size="sm" onClick={() => router.push(`/studio/${entity}/forms/new`)}>
          New form
        </Button>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="No custom forms"
          description="Records use an auto-generated form until you build one."
          action={{ label: "New form", onClick: () => router.push(`/studio/${entity}/forms/new`) }}
        />
      ) : (
        <ul className="space-y-2">
          {rows.map((f) => (
            <li
              key={f.id}
              className="flex items-center justify-between rounded-md border p-3 text-sm"
            >
              <div className="flex items-center gap-2">
                <span className="font-medium">{f.name}</span>
                {f.is_default && <Badge>default</Badge>}
                {f.is_public && <Badge variant="secondary">public</Badge>}
                <span className="text-xs text-muted-foreground">{f.layout.length} sections</span>
              </div>
              <span className="space-x-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => router.push(`/studio/${entity}/forms/${f.id}`)}
                >
                  Edit
                </Button>
                <Button variant="ghost" size="sm" onClick={() => remove(f)} disabled={del.isPending}>
                  Delete
                </Button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
