import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Comment } from "@/lib/comments/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));
vi.mock("@/lib/auth/session", () => ({ useAuthStore: (sel: (s: { user: { id: string } }) => unknown) => sel({ user: { id: "u1" } }) }));

const commentsQ = { isLoading: false, isError: false, data: { results: [] as Comment[], count: 0 } };
const create = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const del = { mutateAsync: vi.fn(() => Promise.resolve(null)), isPending: false };
const pin = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
vi.mock("@/lib/comments/hooks", () => ({
  useComments: () => commentsQ,
  useCreateComment: () => create,
  useDeleteComment: () => del,
  useTogglePin: () => pin,
  useEditComment: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

import { CommentThread } from "./comment-thread";

function c(over: Partial<Comment> = {}): Comment {
  return {
    id: "c1",
    entity_id: "e1",
    record_id: "r1",
    author_id: "u1",
    author_type: "member",
    parent_id: null,
    body: "hello",
    body_format: "markdown",
    mentions: [],
    is_edited: false,
    is_deleted: false,
    is_pinned: false,
    created_at: "",
    updated_at: "",
    ...over,
  };
}

beforeEach(() => {
  commentsQ.data = { results: [], count: 0 };
  create.mutateAsync.mockClear().mockResolvedValue({});
  del.mutateAsync.mockClear().mockResolvedValue(null);
  pin.mutateAsync.mockClear().mockResolvedValue({});
  vi.clearAllMocks();
});

describe("CommentThread", () => {
  it("posts a top-level comment (with an @[uuid] mention) firing create", async () => {
    render(<CommentThread entitySlug="deals" recordId="r1" />);
    fireEvent.change(screen.getByLabelText("New comment"), { target: { value: "ping @[3f2504e0-4f89-41d3-9a0c-0305e82c3301]" } });
    fireEvent.click(screen.getByRole("button", { name: "Comment" }));
    await waitFor(() =>
      expect(create.mutateAsync).toHaveBeenCalledWith({ body: "ping @[3f2504e0-4f89-41d3-9a0c-0305e82c3301]", parent_id: null }),
    );
  });

  it("renders a mention token as a badge", () => {
    commentsQ.data = { results: [c({ body: "hi @[3f2504e0-4f89-41d3-9a0c-0305e82c3301]" })], count: 1 };
    render(<CommentThread entitySlug="deals" recordId="r1" />);
    expect(screen.getByText("@3f2504e0")).toBeInTheDocument();
  });

  it("threads a reply under its parent via parent_id", async () => {
    commentsQ.data = { results: [c()], count: 1 };
    render(<CommentThread entitySlug="deals" recordId="r1" />);
    fireEvent.click(screen.getByRole("button", { name: "Reply" }));
    fireEvent.change(screen.getByLabelText("Reply to c1"), { target: { value: "agreed" } });
    fireEvent.click(within(screen.getByLabelText("Reply to c1").closest("div")!).getByRole("button", { name: "Reply" }));
    await waitFor(() => expect(create.mutateAsync).toHaveBeenCalledWith({ body: "agreed", parent_id: "c1" }));
  });

  it("pins a comment and lets the author delete it", async () => {
    commentsQ.data = { results: [c({ is_pinned: false })], count: 1 };
    render(<CommentThread entitySlug="deals" recordId="r1" />);
    fireEvent.click(screen.getByRole("button", { name: "Pin" }));
    await waitFor(() => expect(pin.mutateAsync).toHaveBeenCalledWith({ id: "c1", pinned: false }));
    fireEvent.click(screen.getByRole("button", { name: /Delete comment/ }));
    await waitFor(() => expect(del.mutateAsync).toHaveBeenCalledWith("c1"));
  });

  it("hides Delete for comments by other authors", () => {
    commentsQ.data = { results: [c({ author_id: "someone-else" })], count: 1 };
    render(<CommentThread entitySlug="deals" recordId="r1" />);
    expect(screen.queryByRole("button", { name: /Delete comment/ })).not.toBeInTheDocument();
  });
});
