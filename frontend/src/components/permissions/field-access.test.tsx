import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { FieldPermission, MaskingRule } from "@/lib/permissions/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const entitiesQ = { data: [{ id: "e1", slug: "deals", name: "Deals" }] };
vi.mock("@/lib/metadata/hooks", () => ({ useEntities: () => entitiesQ }));
const fieldsQ = { data: [{ id: "f1", name: "Amount" }] };
vi.mock("@/lib/metadata/builder-hooks", () => ({ useFields: () => fieldsQ }));

const fpsQ = { data: [] as FieldPermission[] };
const masksQ = { data: [] as MaskingRule[] };
const createFp = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const delFp = { mutateAsync: vi.fn(() => Promise.resolve(null)), isPending: false };
const createMask = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const delMask = { mutateAsync: vi.fn(() => Promise.resolve(null)), isPending: false };
vi.mock("@/lib/permissions/hooks", () => ({
  useFieldPermissions: () => fpsQ,
  useMaskingRules: () => masksQ,
  useCreateFieldPermission: () => createFp,
  useDeleteFieldPermission: () => delFp,
  useCreateMaskingRule: () => createMask,
  useDeleteMaskingRule: () => delMask,
}));

import { FieldAccess } from "./field-access";

beforeEach(() => {
  fpsQ.data = [];
  masksQ.data = [];
  vi.clearAllMocks();
  createFp.mutateAsync.mockResolvedValue({});
  createMask.mutateAsync.mockResolvedValue({});
});

async function pickField() {
  fireEvent.click(screen.getByRole("combobox", { name: "Entity" }));
  fireEvent.click(await screen.findByRole("option", { name: "Deals" }));
  fireEvent.click(screen.getByRole("combobox", { name: "Field" }));
  fireEvent.click(await screen.findByRole("option", { name: "Amount" }));
}

describe("FieldAccess", () => {
  it("hides a field (read & write false) after picking entity + field", async () => {
    render(<FieldAccess roleId="r1" />);
    await pickField();
    fireEvent.click(screen.getByRole("button", { name: "Hide field" }));
    await waitFor(() =>
      expect(createFp.mutateAsync).toHaveBeenCalledWith({
        field_id: "f1",
        role_id: "r1",
        can_read: false,
        can_write: false,
      }),
    );
  });

  it("makes a field read-only", async () => {
    render(<FieldAccess roleId="r1" />);
    await pickField();
    fireEvent.click(screen.getByRole("button", { name: "Read-only" }));
    await waitFor(() =>
      expect(createFp.mutateAsync).toHaveBeenCalledWith({
        field_id: "f1",
        role_id: "r1",
        can_read: true,
        can_write: false,
      }),
    );
  });

  it("adds a masking rule", async () => {
    render(<FieldAccess roleId="r1" />);
    await pickField();
    fireEvent.click(screen.getByRole("button", { name: "Mask field" }));
    await waitFor(() =>
      expect(createMask.mutateAsync).toHaveBeenCalledWith({
        field_id: "f1",
        role_id: "r1",
        mask_type: "full",
      }),
    );
  });

  it("lists and removes existing field restrictions and masks", async () => {
    fpsQ.data = [{ id: "fp1", field_id: "f1", role_id: "r1", can_read: false, can_write: false }];
    masksQ.data = [{ id: "m1", field_id: "f1", role_id: "r1", mask_type: "full", mask_pattern: "" }];
    render(<FieldAccess roleId="r1" />);
    expect(screen.getByText("Amount")).toBeInTheDocument(); // mask resolves field name
    fireEvent.click(screen.getByRole("button", { name: "Remove field rule f1" }));
    await waitFor(() => expect(delFp.mutateAsync).toHaveBeenCalledWith("fp1"));
    fireEvent.click(screen.getByRole("button", { name: "Remove mask f1" }));
    await waitFor(() => expect(delMask.mutateAsync).toHaveBeenCalledWith("m1"));
  });

  it("surfaces an error when saving a rule fails", async () => {
    createFp.mutateAsync.mockRejectedValueOnce(new Error("x"));
    render(<FieldAccess roleId="r1" />);
    await pickField();
    fireEvent.click(screen.getByRole("button", { name: "Hide field" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
  });
});
