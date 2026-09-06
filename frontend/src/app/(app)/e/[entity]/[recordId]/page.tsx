"use client";

import { useQuery } from "@tanstack/react-query";
import { Pencil, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CommentThread } from "@/components/activity/comment-thread";
import { RecordPlayback } from "@/components/activity/record-playback";
import { RecordTags } from "@/components/activity/record-tags";
import { RecordSla } from "@/components/sla/record-sla";
import { toast } from "@/components/ui/toast";
import { useTenant } from "@/lib/tenant/context";
import { getFieldType } from "@/lib/metadata/field-types";
import { useEntityMeta } from "@/lib/metadata/hooks";
import { recordTitle } from "@/lib/records/columns";
import { recordsApi } from "@/lib/records/api";
import { useDeleteRecord, useRecord } from "@/lib/records/hooks";

export default function RecordDetailPage({
  params,
}: {
  params: { entity: string; recordId: string };
}) {
  const { entity: slug, recordId } = params;
  const router = useRouter();
  const { workspace } = useTenant();
  const ws = workspace?.slug ?? null;
  const { entity } = useEntityMeta(slug);
  const record = useRecord(slug, recordId);
  const del = useDeleteRecord(slug);
  const [confirmOpen, setConfirmOpen] = useState(false);

  if (record.isLoading) return <Skeleton className="h-96 w-full max-w-3xl" />;
  if (record.isError || !record.data || !entity) {
    return <ErrorState title="Record not found" action={{ label: "Back", onClick: () => router.push(`/e/${slug}`) }} />;
  }

  const rec = record.data;
  const fields = entity.fields.filter((f) => !f.is_hidden);

  async function handleDelete() {
    try {
      await del.mutateAsync(recordId);
      toast.success("Record moved to recycle bin");
      router.push(`/e/${slug}`);
    } catch {
      toast.error("Could not delete record");
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => router.push(`/e/${slug}`)}>
            ← {entity.plural_name}
          </Button>
          <h1 className="text-2xl font-bold tracking-tight">{recordTitle(rec, entity)}</h1>
        </div>
        <div className="flex items-center gap-2">
          {entity.can_create !== false && (
            <Button variant="outline" size="sm" onClick={() => router.push(`/e/${slug}/${recordId}/edit`)}>
              <Pencil className="size-4" /> Edit
            </Button>
          )}
          <Button variant="ghost" size="sm" onClick={() => setConfirmOpen(true)}>
            <Trash2 className="size-4" /> Delete
          </Button>
        </div>
      </div>

      <RecordTags entitySlug={slug} recordId={recordId} />
      <RecordSla entitySlug={slug} recordId={recordId} />

      <Tabs defaultValue="fields">
        <TabsList>
          <TabsTrigger value="fields">Fields</TabsTrigger>
          <TabsTrigger value="comments">Comments</TabsTrigger>
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
          <TabsTrigger value="activity">Activity</TabsTrigger>
          <TabsTrigger value="playback">Playback</TabsTrigger>
          <TabsTrigger value="related">Related</TabsTrigger>
        </TabsList>

        <TabsContent value="fields">
          <dl className="divide-y divide-border rounded-lg border border-border">
            {fields.map((f) => (
              <div key={f.slug} className="grid grid-cols-3 gap-4 px-4 py-3 text-sm">
                <dt className="text-muted-foreground">{f.name}</dt>
                <dd className="col-span-2">
                  {getFieldType(f.field_type).format(rec[f.slug], f as never) || (
                    <span className="text-muted-foreground">—</span>
                  )}
                </dd>
              </div>
            ))}
          </dl>
        </TabsContent>

        <TabsContent value="comments">
          <CommentThread entitySlug={slug} recordId={recordId} />
        </TabsContent>
        <TabsContent value="playback">
          <RecordPlayback entitySlug={slug} recordId={recordId} />
        </TabsContent>

        <TabsContent value="timeline">
          <FeedTab queryKey={["data", ws, slug, "timeline", recordId]} loader={() => recordsApi.timeline(slug, recordId)} emptyLabel="No timeline events" />
        </TabsContent>
        <TabsContent value="activity">
          <FeedTab queryKey={["data", ws, slug, "activity", recordId]} loader={() => recordsApi.activity(slug, recordId)} emptyLabel="No activity yet" />
        </TabsContent>
        <TabsContent value="related">
          <EmptyState title="Related records" description="Relationship views arrive in a later phase." />
        </TabsContent>
      </Tabs>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete this record?</DialogTitle>
            <DialogDescription>
              It will be moved to the recycle bin and can be restored later.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={del.isPending}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function FeedTab({
  queryKey,
  loader,
  emptyLabel,
}: {
  queryKey: unknown[];
  loader: () => Promise<{ results: unknown[] }>;
  emptyLabel: string;
}) {
  const feed = useQuery({ queryKey, queryFn: loader });
  if (feed.isLoading) return <Skeleton className="h-32 w-full" />;
  if (feed.isError) return <ErrorState title="Couldn't load" />;
  const items = feed.data?.results ?? [];
  if (!items.length) return <EmptyState title={emptyLabel} />;
  return (
    <ul className="space-y-2">
      {items.map((item, i) => (
        <li key={i} className="rounded-md border border-border px-3 py-2 text-sm">
          <pre className="overflow-x-auto whitespace-pre-wrap text-xs text-muted-foreground">
            {JSON.stringify(item, null, 2)}
          </pre>
        </li>
      ))}
    </ul>
  );
}
