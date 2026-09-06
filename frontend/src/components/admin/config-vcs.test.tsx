import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ConfigCommit, ConfigDiff } from "@/lib/config-vcs/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const commitsQ = { isLoading: false, isError: false, data: { results: [] as ConfigCommit[], count: 0 } };
const diffQ = { isLoading: false, isError: false, data: undefined as ConfigDiff | undefined };
const publish = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const rollback = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
vi.mock("@/lib/config-vcs/hooks", () => ({
  useCommits: () => commitsQ,
  usePublish: () => publish,
  useRollback: () => rollback,
  useDiff: () => diffQ,
}));

import { ConfigVcsPanel } from "./config-vcs";

const commit = (sha: string, message: string): ConfigCommit => ({
  sha, parent_sha: null, message, branch: "main", author_id: null, created_at: "2026-06-23T09:00:00Z", diff: {},
});

beforeEach(() => {
  commitsQ.data = { results: [], count: 0 };
  diffQ.data = undefined;
  publish.mutateAsync.mockClear();
  rollback.mutateAsync.mockClear();
  vi.clearAllMocks();
});

describe("ConfigVcsPanel", () => {
  it("commits the live config with a message", async () => {
    render(<ConfigVcsPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Commit live config" }));
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "snapshot v1" } });
    fireEvent.click(screen.getByRole("button", { name: "Commit" }));
    await waitFor(() => expect(publish.mutateAsync).toHaveBeenCalledWith({ message: "snapshot v1" }));
  });

  it("rolls back after confirmation", async () => {
    commitsQ.data = { results: [commit("abcdef1234", "first")], count: 1 };
    render(<ConfigVcsPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Rollback to abcdef12" }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Roll back" }));
    await waitFor(() => expect(rollback.mutateAsync).toHaveBeenCalledWith("abcdef1234"));
  });

  it("renders a structural diff", () => {
    commitsQ.data = { results: [commit("aaa11111", "a"), commit("bbb22222", "b")], count: 2 };
    diffQ.data = {
      entities: { added: [{ slug: "leads" }], removed: [], modified: [] },
      fields: { added: [], removed: [], modified: [{ before: { slug: "amount" }, after: { slug: "amount" } }] },
      rules: { added: [], removed: [], modified: [] },
      roles: { added: [], removed: [], modified: [] },
      permissions: { added: [], removed: [], modified: [] },
    };
    render(<ConfigVcsPanel />);
    expect(screen.getByLabelText("diff-entities")).toBeInTheDocument();
    expect(screen.getByText("+ leads")).toBeInTheDocument();
    expect(screen.getByText("~ amount")).toBeInTheDocument();
  });
});
