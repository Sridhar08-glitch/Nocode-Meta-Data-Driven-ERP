import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/errors";

const create = { mutateAsync: vi.fn(), isPending: false };
vi.mock("@/lib/metadata/builder-hooks", () => ({ useCreateEntity: () => create }));
const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

import { EntityCreateDialog } from "./entity-create-dialog";

function open() {
  render(<EntityCreateDialog onCreated={onCreated} />);
  fireEvent.click(screen.getByRole("button", { name: "New entity" }));
}
const onCreated = vi.fn();

beforeEach(() => {
  create.isPending = false;
  create.mutateAsync.mockReset().mockResolvedValue({ slug: "lead", name: "Lead" });
  vi.clearAllMocks();
});

describe("EntityCreateDialog", () => {
  it("auto-derives the slug from the name", () => {
    open();
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Lead Source" } });
    expect((screen.getByLabelText("Slug") as HTMLInputElement).value).toBe("lead_source");
  });

  it("flags an invalid slug and disables Create", () => {
    open();
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Lead" } });
    fireEvent.change(screen.getByLabelText("Slug"), { target: { value: "9bad" } });
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create" })).toBeDisabled();
  });

  it("submits a valid entity and reports the new slug", async () => {
    open();
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Lead" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() => expect(create.mutateAsync).toHaveBeenCalled());
    expect(create.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ slug: "lead", name: "Lead", plural_name: "Leads" }),
    );
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith("lead"));
    expect(toast.success).toHaveBeenCalled();
  });

  it("sends an explicit plural name and description, and closes on Cancel", async () => {
    open();
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Lead" } });
    fireEvent.change(screen.getByLabelText("Plural name"), { target: { value: "Leadz" } });
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "A sales lead" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() =>
      expect(create.mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({ plural_name: "Leadz", description: "A sales lead" }),
      ),
    );
  });

  it("closes without creating on Cancel", () => {
    open();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(create.mutateAsync).not.toHaveBeenCalled();
  });

  it("shows a pending label while creating", () => {
    create.isPending = true;
    open();
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Lead" } });
    expect(screen.getByRole("button", { name: "Creating…" })).toBeDisabled();
  });

  it("resets and closes when dismissed via Escape", () => {
    open();
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Lead" } });
    fireEvent.keyDown(document.activeElement ?? document.body, { key: "Escape", code: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("surfaces an error toast when creation fails", async () => {
    create.mutateAsync.mockRejectedValueOnce(new Error("boom"));
    open();
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Lead" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(onCreated).not.toHaveBeenCalled();
  });

  it("uses the ApiError message on a typed failure", async () => {
    create.mutateAsync.mockRejectedValueOnce(new ApiError({ status: 409, message: "slug taken" }));
    open();
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Lead" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("slug taken"));
  });
});
