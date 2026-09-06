import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { FeatureFlag, FeatureFlagOverride } from "@/lib/feature-flags/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const flagsQ = { isLoading: false, isError: false, data: [] as FeatureFlag[] };
const overridesQ = { isLoading: false, data: [] as FeatureFlagOverride[] };
const create = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const update = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const del = { mutateAsync: vi.fn(() => Promise.resolve(null)), isPending: false };
const createOv = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const delOv = { mutateAsync: vi.fn(() => Promise.resolve(null)), isPending: false };
vi.mock("@/lib/feature-flags/hooks", () => ({
  useFeatureFlags: () => flagsQ,
  useCreateFlag: () => create,
  useUpdateFlag: () => update,
  useDeleteFlag: () => del,
  useFlagOverrides: () => overridesQ,
  useCreateOverride: () => createOv,
  useDeleteOverride: () => delOv,
}));

import { FeatureFlagManager } from "./feature-flag-manager";

const flag = (over: Partial<FeatureFlag> = {}): FeatureFlag => ({
  id: "f1", key: "new_dash", name: "New dashboard", description: "", enabled: false,
  rollout_percent: 100, scope: "workspace", config: {}, is_active: true, created_by: null,
  created_at: "", updated_at: "", ...over,
});

beforeEach(() => {
  flagsQ.data = [];
  overridesQ.data = [];
  for (const m of [create, update, del, createOv, delOv]) m.mutateAsync.mockClear();
  vi.clearAllMocks();
});

describe("FeatureFlagManager", () => {
  it("toggles a flag's master switch", async () => {
    flagsQ.data = [flag()];
    render(<FeatureFlagManager />);
    fireEvent.click(screen.getByRole("switch", { name: "Toggle new_dash" }));
    await waitFor(() => expect(update.mutateAsync).toHaveBeenCalledWith({ id: "f1", data: { enabled: true } }));
  });

  it("creates a flag with key + rollout", async () => {
    render(<FeatureFlagManager />);
    fireEvent.click(screen.getAllByRole("button", { name: "New flag" })[0]);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Beta search" } });
    fireEvent.change(screen.getByLabelText("Rollout %"), { target: { value: "25" } });
    fireEvent.click(screen.getByRole("button", { name: "Create flag" }));
    await waitFor(() => expect(create.mutateAsync).toHaveBeenCalled());
    expect(create.mutateAsync).toHaveBeenCalledWith(expect.objectContaining({ key: "beta_search", rollout_percent: 25, scope: "workspace" }));
  });

  it("adds a workspace override from the overrides dialog", async () => {
    flagsQ.data = [flag()];
    render(<FeatureFlagManager />);
    fireEvent.click(screen.getByRole("button", { name: "Overrides for new_dash" }));
    fireEvent.click(screen.getByRole("button", { name: "Add override" }));
    await waitFor(() => expect(createOv.mutateAsync).toHaveBeenCalled());
    expect(createOv.mutateAsync).toHaveBeenCalledWith({ flagId: "f1", data: { target_type: "workspace", target_id: null, enabled: true } });
  });

  it("deletes a flag", async () => {
    flagsQ.data = [flag()];
    render(<FeatureFlagManager />);
    fireEvent.click(screen.getByRole("button", { name: "Remove flag new_dash" }));
    await waitFor(() => expect(del.mutateAsync).toHaveBeenCalledWith("f1"));
  });
});
