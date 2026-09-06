"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { Switch } from "@/components/ui/switch";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import type { FormSubmission, PublicFormDef } from "@/lib/public-forms/admin-api";
import {
  useApproveSubmission,
  useFormSubmissions,
  usePublicForms,
  useRejectSubmission,
  useUpdatePublicForm,
} from "@/lib/public-forms/admin-hooks";

/** Public-forms admin (Phase P1.5): publish forms + triage submissions. */
export function PublicFormsAdmin() {
  const forms = usePublicForms();
  const update = useUpdatePublicForm();
  const [inboxFor, setInboxFor] = useState<PublicFormDef | null>(null);

  const rows = forms.data?.results ?? [];

  async function togglePublic(f: PublicFormDef) {
    try {
      await update.mutateAsync({ id: f.id, data: { is_public: !f.is_public } });
      toast.success(f.is_public ? "Form unpublished" : "Form published");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not update form");
    }
  }
  function copyUrl(id: string) {
    const url = `${window.location.origin}/f/${id}`;
    void navigator.clipboard?.writeText(url);
    toast.success("Public URL copied");
  }

  if (forms.isLoading) return <Skeleton className="h-64 w-full" />;
  if (forms.isError) return <ErrorState title="Couldn't load forms" />;
  if (rows.length === 0) {
    return <EmptyState title="No forms" description="Create a form in Studio, then publish it here for public submissions." />;
  }

  return (
    <div className="space-y-2">
      <ul className="space-y-2">
        {rows.map((f) => (
          <li key={f.id} className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm">
            <span className="flex min-w-0 flex-wrap items-center gap-2">
              <span className="font-medium">{f.name}</span>
              <Badge variant="outline">{f.entity_slug}</Badge>
              {f.is_public ? <Badge>public</Badge> : <Badge variant="secondary">private</Badge>}
            </span>
            <span className="flex shrink-0 items-center gap-2">
              <label className="flex items-center gap-1.5 text-xs">
                <Switch checked={f.is_public} onCheckedChange={() => togglePublic(f)} aria-label={`Publish ${f.name}`} disabled={update.isPending} />
                Public
              </label>
              {f.is_public && (
                <Button variant="ghost" size="sm" aria-label={`Copy public URL for ${f.name}`} onClick={() => copyUrl(f.id)}>
                  Copy URL
                </Button>
              )}
              <Button variant="ghost" size="sm" aria-label={`Submissions for ${f.name}`} onClick={() => setInboxFor(f)}>
                Submissions
              </Button>
            </span>
          </li>
        ))}
      </ul>

      {inboxFor && <SubmissionsDialog form={inboxFor} onClose={() => setInboxFor(null)} />}
    </div>
  );
}

const STATUSES = ["all", "pending", "accepted", "rejected"];

function SubmissionsDialog({ form, onClose }: { form: PublicFormDef; onClose: () => void }) {
  const [status, setStatus] = useState("all");
  const subs = useFormSubmissions(form.id, status === "all" ? undefined : status);
  const approve = useApproveSubmission();
  const reject = useRejectSubmission();
  const [rejecting, setRejecting] = useState<FormSubmission | null>(null);
  const [reason, setReason] = useState("");

  const rows = subs.data?.results ?? [];

  async function doApprove(s: FormSubmission) {
    try {
      await approve.mutateAsync({ formId: form.id, subId: s.id });
      toast.success("Submission approved");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not approve");
    }
  }
  async function doReject() {
    if (!rejecting) return;
    try {
      await reject.mutateAsync({ formId: form.id, subId: rejecting.id, reason: reason.trim() });
      toast.success("Submission rejected");
      setRejecting(null);
      setReason("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not reject");
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Submissions — {form.name}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger aria-label="Status filter" className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {STATUSES.map((s) => (
                <SelectItem key={s} value={s}>
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {subs.isLoading ? (
            <Skeleton className="h-40 w-full" />
          ) : rows.length === 0 ? (
            <p className="text-sm text-muted-foreground">No submissions.</p>
          ) : (
            <ul className="max-h-[50vh] space-y-2 overflow-y-auto">
              {rows.map((s) => (
                <li key={s.id} className="space-y-1.5 rounded-md border p-2 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={s.status === "accepted" ? "default" : s.status === "rejected" ? "destructive" : "secondary"}>{s.status}</Badge>
                    {s.submitter_name && <span className="font-medium">{s.submitter_name}</span>}
                    {s.submitter_email && <span className="text-xs text-muted-foreground">{s.submitter_email}</span>}
                    {s.spam_score > 0.5 && <Badge variant="destructive">spam {Math.round(s.spam_score * 100)}%</Badge>}
                    <span className="ml-auto text-xs text-muted-foreground">{s.created_at ? new Date(s.created_at).toLocaleString() : ""}</span>
                  </div>
                  <pre className="max-h-32 overflow-auto rounded bg-muted/40 p-2 text-xs">{JSON.stringify(s.data, null, 2)}</pre>
                  {s.rejection_reason && <p className="text-xs text-destructive">Rejected: {s.rejection_reason}</p>}
                  {s.status === "pending" && (
                    <div className="flex gap-1.5">
                      <Button variant="outline" size="sm" className="h-7" aria-label={`Approve submission ${s.id}`} onClick={() => doApprove(s)} disabled={approve.isPending}>
                        Approve
                      </Button>
                      <Button variant="outline" size="sm" className="h-7" aria-label={`Reject submission ${s.id}`} onClick={() => setRejecting(s)}>
                        Reject
                      </Button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>

        {rejecting && (
          <Dialog open onOpenChange={(o) => !o && setRejecting(null)}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Reject submission</DialogTitle>
              </DialogHeader>
              <Input aria-label="Rejection reason" placeholder="Reason (optional)" value={reason} onChange={(e) => setReason(e.target.value)} autoFocus />
              <DialogFooter>
                <Button variant="ghost" onClick={() => setRejecting(null)}>
                  Cancel
                </Button>
                <Button onClick={doReject} disabled={reject.isPending}>
                  {reject.isPending ? "Rejecting…" : "Reject"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        )}

        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
