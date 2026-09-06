import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));
const create = { mutateAsync: vi.fn(), isPending: false };
vi.mock("@/lib/workflows/hooks", () => ({ useCreateWorkflow: () => create }));

import { WorkflowCreateDialog } from "./workflow-create-dialog";

const onCreated = vi.fn();

beforeEach(() => {
  create.isPending = false;
  create.mutateAsync.mockReset().mockResolvedValue({ id: "w9", name: "Lead intake" });
  vi.clearAllMocks();
});

describe("WorkflowCreateDialog", () => {
  it("creates a workflow with a derived slug + default trigger, then reports the id", async () => {
    render(<WorkflowCreateDialog onCreated={onCreated} />);
    fireEvent.click(screen.getByRole("button", { name: "New workflow" }));
    expect(screen.getByRole("button", { name: "Create" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Lead intake" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() =>
      expect(create.mutateAsync).toHaveBeenCalledWith({
        name: "Lead intake",
        slug: "lead_intake",
        trigger_type: "record_created",
      }),
    );
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith("w9"));
    expect(toast.success).toHaveBeenCalled();
  });

  it("creates with a chosen trigger type", async () => {
    render(<WorkflowCreateDialog />);
    fireEvent.click(screen.getByRole("button", { name: "New workflow" }));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Nightly" } });
    fireEvent.click(screen.getByRole("combobox", { name: /Trigger/i }));
    fireEvent.click(await screen.findByRole("option", { name: "Schedule (cron)" }));
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() =>
      expect(create.mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({ trigger_type: "schedule" }),
      ),
    );
  });

  it("surfaces an error toast on failure", async () => {
    create.mutateAsync.mockRejectedValueOnce(new Error("dup"));
    render(<WorkflowCreateDialog />);
    fireEvent.click(screen.getByRole("button", { name: "New workflow" }));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "X" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
  });
});
