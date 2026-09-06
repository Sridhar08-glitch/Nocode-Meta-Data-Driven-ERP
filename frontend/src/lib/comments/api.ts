/**
 * Comments client (Phase F2.5) — per-record threaded comments over
 * `/api/v1/data/{slug}/{id}/comments/`. @mentions use the backend's literal `@[uuid]` format
 * (the server extracts them and sends a `comment_mention` notification). Author is server-set.
 */
import { apiGet, apiSend } from "@/lib/api/request";

export interface Mention {
  type: "member";
  id: string;
}
export interface Comment {
  id: string;
  entity_id: string;
  record_id: string;
  author_id: string;
  author_type: "member" | "portal_user";
  parent_id: string | null;
  body: string;
  body_format: "markdown" | "plain";
  mentions: Mention[];
  is_edited: boolean;
  is_deleted: boolean;
  is_pinned: boolean;
  created_at: string;
  updated_at: string;
}
export interface CommentCreate {
  body: string;
  parent_id?: string | null;
  body_format?: "markdown" | "plain";
}
export interface Paged<T> {
  results: T[];
  count: number;
}

/** Mention token the backend recognizes. */
export function mentionToken(memberId: string): string {
  return `@[${memberId}]`;
}

const base = (slug: string, recordId: string) => `/api/v1/data/${slug}/${recordId}/comments`;

export const commentsApi = {
  list: (slug: string, recordId: string) => apiGet<Paged<Comment>>(`${base(slug, recordId)}/`),
  create: (slug: string, recordId: string, data: CommentCreate) =>
    apiSend<Comment>(`${base(slug, recordId)}/`, "POST", data),
  edit: (slug: string, recordId: string, id: string, body: string) =>
    apiSend<Comment>(`${base(slug, recordId)}/${id}/`, "PATCH", { body }),
  remove: (slug: string, recordId: string, id: string) =>
    apiSend<null>(`${base(slug, recordId)}/${id}/`, "DELETE"),
  pin: (slug: string, recordId: string, id: string) =>
    apiSend<Comment>(`${base(slug, recordId)}/${id}/pin/`, "POST"),
  unpin: (slug: string, recordId: string, id: string) =>
    apiSend<Comment>(`${base(slug, recordId)}/${id}/unpin/`, "POST"),
};
