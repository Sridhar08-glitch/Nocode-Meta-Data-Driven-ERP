"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import { type Comment } from "@/lib/comments/api";
import {
  useComments,
  useCreateComment,
  useDeleteComment,
  useTogglePin,
} from "@/lib/comments/hooks";
import { useAuthStore } from "@/lib/auth/session";
import { cn } from "@/lib/utils";

/** Renders comment body, turning `@[uuid]` mention tokens into badges. */
function renderBody(body: string) {
  const parts = body.split(/(@\[[0-9a-fA-F-]{36}\])/);
  return parts.map((p, i) => {
    const m = p.match(/^@\[([0-9a-fA-F-]{36})\]$/);
    if (m) return <Badge key={i} variant="secondary" className="mx-0.5">@{m[1].slice(0, 8)}</Badge>;
    return <span key={i}>{p}</span>;
  });
}

/** Per-record threaded comments with @mentions (Phase F2.5). */
export function CommentThread({ entitySlug, recordId }: { entitySlug: string; recordId: string }) {
  const comments = useComments(entitySlug, recordId);
  const create = useCreateComment(entitySlug, recordId);
  const [body, setBody] = useState("");

  if (comments.isLoading) return <Skeleton className="h-40 w-full" />;
  if (comments.isError) return <ErrorState title="Couldn't load comments" />;
  const all = comments.data?.results ?? [];
  const roots = all.filter((c) => !c.parent_id);
  const repliesOf = (id: string) => all.filter((c) => c.parent_id === id);

  async function submit(parentId: string | null, text: string, reset: () => void) {
    if (!text.trim()) return;
    try {
      await create.mutateAsync({ body: text.trim(), parent_id: parentId });
      reset();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not post comment");
    }
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Textarea
          aria-label="New comment"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Comment… mention with @[member-id]"
          rows={2}
        />
        <Button size="sm" disabled={!body.trim() || create.isPending} onClick={() => submit(null, body, () => setBody(""))}>
          {create.isPending ? "Posting…" : "Comment"}
        </Button>
      </div>

      {roots.length === 0 ? (
        <EmptyState title="No comments yet" />
      ) : (
        <ul className="space-y-3">
          {roots.map((c) => (
            <li key={c.id} className="space-y-2">
              <CommentItem comment={c} entitySlug={entitySlug} recordId={recordId} />
              {repliesOf(c.id).length > 0 && (
                <ul className="ml-6 space-y-2 border-l pl-3">
                  {repliesOf(c.id).map((r) => (
                    <li key={r.id}>
                      <CommentItem comment={r} entitySlug={entitySlug} recordId={recordId} />
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function CommentItem({ comment, entitySlug, recordId }: { comment: Comment; entitySlug: string; recordId: string }) {
  const user = useAuthStore((s) => s.user);
  const del = useDeleteComment(entitySlug, recordId);
  const pin = useTogglePin(entitySlug, recordId);
  const create = useCreateComment(entitySlug, recordId);
  const [replying, setReplying] = useState(false);
  const [reply, setReply] = useState("");
  const isAuthor = !!user?.id && user.id === comment.author_id;

  async function run(p: Promise<unknown>, ok: string) {
    try {
      await p;
      toast.success(ok);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Action failed");
    }
  }

  return (
    <div className={cn("rounded-md border p-3 text-sm", comment.is_pinned && "border-primary/40 bg-primary/5")}>
      <div className="mb-1 flex items-center gap-2 text-xs text-muted-foreground">
        <span className="font-mono">{comment.author_id.slice(0, 8)}</span>
        {comment.is_pinned && <Badge>pinned</Badge>}
        {comment.is_edited && <span>(edited)</span>}
      </div>
      <div className="whitespace-pre-wrap">{comment.is_deleted ? <em className="text-muted-foreground">deleted</em> : renderBody(comment.body)}</div>
      {!comment.is_deleted && (
        <div className="mt-2 flex gap-2">
          <Button variant="ghost" size="sm" onClick={() => setReplying((r) => !r)}>
            Reply
          </Button>
          <Button variant="ghost" size="sm" onClick={() => run(pin.mutateAsync({ id: comment.id, pinned: comment.is_pinned }), comment.is_pinned ? "Unpinned" : "Pinned")} disabled={pin.isPending}>
            {comment.is_pinned ? "Unpin" : "Pin"}
          </Button>
          {isAuthor && (
            <Button variant="ghost" size="sm" aria-label={`Delete comment ${comment.id.slice(0, 8)}`} onClick={() => run(del.mutateAsync(comment.id), "Comment deleted")} disabled={del.isPending}>
              Delete
            </Button>
          )}
        </div>
      )}
      {replying && (
        <div className="mt-2 space-y-1">
          <Textarea aria-label={`Reply to ${comment.id.slice(0, 8)}`} value={reply} onChange={(e) => setReply(e.target.value)} rows={2} />
          <Button
            size="sm"
            disabled={!reply.trim() || create.isPending}
            onClick={async () => {
              await run(create.mutateAsync({ body: reply.trim(), parent_id: comment.id }), "Reply posted");
              setReply("");
              setReplying(false);
            }}
          >
            Reply
          </Button>
        </div>
      )}
    </div>
  );
}
