import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/errors";

const commits = { data: { results: [{ sha: "abcdef123456", message: "Add Lead" }] } };
const publish = { mutateAsync: vi.fn(), isPending: false };
const rollback = { mutateAsync: vi.fn(), isPending: false };
vi.mock("@/lib/config-vcs/hooks", () => ({
  useCommits: () => commits,
  usePublish: () => publish,
  useRollback: () => rollback,
}));
const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

import { PublishBar } from "./publish-bar";

beforeEach(() => {
  publish.isPending = false;
  rollback.isPending = false;
  publish.mutateAsync.mockReset().mockResolvedValue({ sha: "abcdef123456" });
  rollback.mutateAsync.mockReset().mockResolvedValue({});
  vi.clearAllMocks();
});

describe("PublishBar", () => {
  it("publishes with a commit message", async () => {
    render(<PublishBar />);
    fireEvent.click(screen.getByRole("button", { name: "Publish changes" }));
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Add Lead entity" } });
    fireEvent.click(screen.getByRole("button", { name: "Publish" }));
    await waitFor(() => expect(publish.mutateAsync).toHaveBeenCalledWith({ message: "Add Lead entity" }));
    expect(toast.success).toHaveBeenCalled();
  });

  it("treats a 400 as 'nothing to publish'", async () => {
    publish.mutateAsync.mockRejectedValueOnce(new ApiError({ status: 400, message: "no changes" }));
    render(<PublishBar />);
    fireEvent.click(screen.getByRole("button", { name: "Publish changes" }));
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "noop" } });
    fireEvent.click(screen.getByRole("button", { name: "Publish" }));
    await waitFor(() => expect(toast.info).toHaveBeenCalled());
    expect(toast.error).not.toHaveBeenCalled();
  });

  it("shows an error toast on a non-400 publish failure", async () => {
    publish.mutateAsync.mockRejectedValueOnce(new ApiError({ status: 500, message: "server" }));
    render(<PublishBar />);
    fireEvent.click(screen.getByRole("button", { name: "Publish changes" }));
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: "Publish" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(toast.info).not.toHaveBeenCalled();
  });

  it("closes the publish dialog on Cancel", () => {
    render(<PublishBar />);
    fireEvent.click(screen.getByRole("button", { name: "Publish changes" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(publish.mutateAsync).not.toHaveBeenCalled();
  });

  it("rolls back a prior commit from history", async () => {
    render(<PublishBar />);
    fireEvent.click(screen.getByRole("button", { name: "Restore" }));
    await waitFor(() => expect(rollback.mutateAsync).toHaveBeenCalledWith("abcdef123456"));
    expect(toast.success).toHaveBeenCalled();
  });

  it("shows an error toast when rollback fails", async () => {
    rollback.mutateAsync.mockRejectedValueOnce(new Error("nope"));
    render(<PublishBar />);
    fireEvent.click(screen.getByRole("button", { name: "Restore" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
  });

  it("uses the ApiError message when rollback fails with a typed error", async () => {
    rollback.mutateAsync.mockRejectedValueOnce(new ApiError({ status: 409, message: "locked" }));
    render(<PublishBar />);
    fireEvent.click(screen.getByRole("button", { name: "Restore" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("locked"));
  });

  it("hides history when there are no commits", () => {
    commits.data = undefined as unknown as typeof commits.data;
    render(<PublishBar />);
    expect(screen.queryByText(/History/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Restore" })).not.toBeInTheDocument();
    commits.data = { results: [{ sha: "abcdef123456", message: "Add Lead" }] };
  });

  it("shows a pending label while publishing", () => {
    publish.isPending = true;
    render(<PublishBar />);
    fireEvent.click(screen.getByRole("button", { name: "Publish changes" }));
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "x" } });
    expect(screen.getByRole("button", { name: "Publishing…" })).toBeDisabled();
  });
});
