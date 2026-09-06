import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/errors";
import type { EntityMeta } from "@/lib/metadata/types";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));
const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

// Impact dialog (opens before archive) fetches references — return none by default.
const entityImpact = vi.hoisted(() => vi.fn(() => Promise.resolve({ dependents: [], count: 0 })));
vi.mock("@/lib/metadata/builder-api", () => ({ builderApi: { entityImpact } }));

function render2(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

/** Open the archive impact dialog, wait for the impact check, then confirm. */
async function archiveConfirm() {
  fireEvent.click(screen.getByRole("button", { name: "Archive entity" }));
  await screen.findByText(/No known references/);
  fireEvent.click(screen.getByRole("button", { name: "Archive" }));
}

const update = { mutateAsync: vi.fn(), isPending: false };
const archive = { mutateAsync: vi.fn(), isPending: false };
vi.mock("@/lib/metadata/builder-hooks", () => ({
  useUpdateEntity: () => update,
  useDeleteEntity: () => archive,
}));

import { EntitySettings } from "./entity-settings";

const entity: EntityMeta = {
  id: "e1",
  slug: "lead",
  name: "Lead",
  plural_name: "Leads",
  description: "Sales leads",
  icon: "box",
  color: "#2563eb",
  module: null,
  is_active: true,
  title_field_slug: "name",
  current_schema_version: 1,
  fields: [],
};

beforeEach(() => {
  update.isPending = false;
  archive.isPending = false;
  update.mutateAsync.mockReset().mockResolvedValue({});
  archive.mutateAsync.mockReset().mockResolvedValue(null);
  vi.clearAllMocks();
});

describe("EntitySettings", () => {
  it("disables Save until a field changes", () => {
    render(<EntitySettings entity={entity} />);
    expect(screen.getByRole("button", { name: "Save settings" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Prospect" } });
    expect(screen.getByRole("button", { name: "Save settings" })).toBeEnabled();
  });

  it("saves edits", async () => {
    render(<EntitySettings entity={entity} />);
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "Updated" } });
    fireEvent.click(screen.getByRole("button", { name: "Save settings" }));
    await waitFor(() => expect(update.mutateAsync).toHaveBeenCalled());
    expect(update.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ name: "Lead", description: "Updated" }),
    );
    expect(toast.success).toHaveBeenCalled();
  });

  it("surfaces a save error", async () => {
    update.mutateAsync.mockRejectedValueOnce(new Error("x"));
    render(<EntitySettings entity={entity} />);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Prospect" } });
    fireEvent.click(screen.getByRole("button", { name: "Save settings" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
  });

  it("archives after the impact check and navigates home", async () => {
    render2(<EntitySettings entity={entity} />);
    await archiveConfirm();
    await waitFor(() => expect(archive.mutateAsync).toHaveBeenCalledWith("lead"));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/studio"));
  });

  it("edits plural, icon and color", async () => {
    render(<EntitySettings entity={entity} />);
    fireEvent.change(screen.getByLabelText("Plural"), { target: { value: "Prospects" } });
    fireEvent.change(screen.getByLabelText("Icon"), { target: { value: "users" } });
    fireEvent.change(screen.getByLabelText("Color"), { target: { value: "#111111" } });
    fireEvent.click(screen.getByRole("button", { name: "Save settings" }));
    await waitFor(() => expect(update.mutateAsync).toHaveBeenCalled());
    expect(update.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ plural_name: "Prospects", icon: "users", color: "#111111" }),
    );
  });

  it("shows pending labels while saving and archiving", () => {
    update.isPending = true;
    archive.isPending = true;
    render2(<EntitySettings entity={entity} />);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Prospect" } });
    expect(screen.getByRole("button", { name: "Saving…" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Archive entity" }));
    expect(screen.getByRole("button", { name: "Archiving…" })).toBeDisabled();
  });

  it("closes the archive dialog on Cancel", () => {
    render2(<EntitySettings entity={entity} />);
    fireEvent.click(screen.getByRole("button", { name: "Archive entity" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(archive.mutateAsync).not.toHaveBeenCalled();
  });

  it("surfaces an archive error", async () => {
    archive.mutateAsync.mockRejectedValueOnce(new Error("x"));
    render2(<EntitySettings entity={entity} />);
    await archiveConfirm();
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(push).not.toHaveBeenCalled();
  });

  it("uses the ApiError message on typed save and archive failures", async () => {
    update.mutateAsync.mockRejectedValueOnce(new ApiError({ status: 400, message: "bad name" }));
    archive.mutateAsync.mockRejectedValueOnce(new ApiError({ status: 409, message: "has records" }));
    render2(<EntitySettings entity={entity} />);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Prospect" } });
    fireEvent.click(screen.getByRole("button", { name: "Save settings" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("bad name"));
    await archiveConfirm();
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("has records"));
  });
});
