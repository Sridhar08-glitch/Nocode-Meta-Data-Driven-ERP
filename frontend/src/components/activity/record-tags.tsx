"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import { useAttachTag, useDetachTag, useRecordTags, useTags } from "@/lib/tagging/hooks";

/** Universal tagging on a record (Phase F2.5): attach existing tags + detach. */
export function RecordTags({ entitySlug, recordId }: { entitySlug: string; recordId: string }) {
  const recordTags = useRecordTags(recordId);
  const allTags = useTags();
  const attach = useAttachTag(entitySlug, recordId);
  const detach = useDetachTag(recordId);
  const [picking, setPicking] = useState(false);

  const current = recordTags.data?.results ?? [];
  const currentIds = new Set(current.map((t) => t.id));
  const available = (allTags.data?.results ?? []).filter((t) => !currentIds.has(t.id));

  async function run(p: Promise<unknown>, ok: string) {
    try {
      await p;
      toast.success(ok);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Action failed");
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2" aria-label="Tags">
      {current.map((t) => (
        <span key={t.id} className="inline-flex items-center gap-1 rounded-full border py-0.5 pl-2 pr-1 text-xs" style={{ borderColor: t.color }}>
          <span aria-hidden className="size-2 rounded-full" style={{ backgroundColor: t.color }} />
          {t.name}
          <button aria-label={`Remove tag ${t.name}`} className="rounded px-1 text-muted-foreground hover:bg-muted" onClick={() => run(detach.mutateAsync(t.id), "Tag removed")}>
            ✕
          </button>
        </span>
      ))}
      {picking ? (
        <Select
          value=""
          onValueChange={(id) => {
            run(attach.mutateAsync(id), "Tag added");
            setPicking(false);
          }}
        >
          <SelectTrigger aria-label="Add tag" className="h-7 w-40">
            <SelectValue placeholder="Pick a tag…" />
          </SelectTrigger>
          <SelectContent>
            {available.map((t) => (
              <SelectItem key={t.id} value={t.id}>
                {t.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      ) : (
        <Button variant="outline" size="sm" className="h-7" onClick={() => setPicking(true)} disabled={attach.isPending}>
          + Tag
        </Button>
      )}
    </div>
  );
}
