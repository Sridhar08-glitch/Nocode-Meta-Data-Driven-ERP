import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ApprovalProcess } from "@/lib/approvals/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));
vi.mock("@/lib/metadata/hooks", () => ({ useEntities: () => ({ data: [{ id: "e1", name: "Deals", slug: "deals" }] }) }));

const procsQ = { isLoading: false, isError: false, data: { results: [] as ApprovalProcess[], count: 0 } };
const create = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const del = { mutateAsync: vi.fn(() => Promise.resolve(null)), isPending: false };
vi.mock("@/lib/approvals/hooks", () => ({ useApprovalProcesses: () => procsQ, useCreateProcess: () => create, useDeleteProcess: () => del }));

import { ApprovalBuilder } from "./approval-builder";

beforeEach(() => {
  procsQ.data = { results: [], count: 0 };
  create.mutateAsync.mockClear().mockResolvedValue({});
  del.mutateAsync.mockClear().mockResolvedValue(null);
  vi.clearAllMocks();
});

describe("ApprovalBuilder", () => {
  it("creates a process with a level + approver matrix", async () => {
    render(<ApprovalBuilder />);
    fireEvent.click(screen.getAllByRole("button", { name: "New process" })[0]);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Big deals" } });
    fireEvent.click(screen.getByRole("combobox", { name: "Entity" }));
    fireEvent.click(await screen.findByRole("option", { name: "Deals" }));
    fireEvent.change(screen.getByLabelText("Level 1 approver 1 value"), { target: { value: "manager" } });
    fireEvent.click(screen.getByRole("button", { name: "Create process" }));
    await waitFor(() => expect(create.mutateAsync).toHaveBeenCalled());
    expect(create.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "Big deals",
        slug: "big_deals",
        entity_id: "e1",
        levels: [
          expect.objectContaining({
            level: 1,
            approvers: [{ type: "role", value: "manager" }],
            quorum: "any",
            timeout_hours: 24,
            on_timeout: "auto_reject",
          }),
        ],
      }),
    );
  });

  it("adds a second level (renumbered)", async () => {
    render(<ApprovalBuilder />);
    fireEvent.click(screen.getAllByRole("button", { name: "New process" })[0]);
    fireEvent.click(screen.getByRole("button", { name: "Add level" }));
    expect(screen.getByLabelText("Level 2 approver 1 value")).toBeInTheDocument();
  });

  it("deletes a process", async () => {
    procsQ.data = { results: [{ id: "p1", name: "Old", levels: [], is_active: true } as unknown as ApprovalProcess], count: 1 };
    render(<ApprovalBuilder />);
    fireEvent.click(screen.getByRole("button", { name: "Remove process Old" }));
    await waitFor(() => expect(del.mutateAsync).toHaveBeenCalledWith("p1"));
  });
});
