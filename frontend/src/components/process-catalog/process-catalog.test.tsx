import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { BlueprintPreview, ProcessBlueprint } from "@/lib/process-catalog/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const listQ = { isLoading: false, isError: false, data: { results: [] as ProcessBlueprint[], count: 0 } };
const previewQ = { isLoading: false, isError: false, data: undefined as BlueprintPreview | undefined };
const install = { mutateAsync: vi.fn(() => Promise.resolve({ blueprint: "onboarding", entity_ids: ["e1"], workflow_ids: ["w1"], rule_ids: [], report_ids: [] })), isPending: false };
vi.mock("@/lib/process-catalog/hooks", () => ({
  useBlueprints: () => listQ,
  useBlueprintPreview: () => previewQ,
  useInstallBlueprint: () => install,
}));

import { ProcessCatalog } from "./process-catalog";

const bp = (over: Partial<ProcessBlueprint> = {}): ProcessBlueprint => ({
  id: "b1", name: "Employee Onboarding", slug: "onboarding", category: "hr", description: "Hire to desk",
  publisher: "Nexus", manifest: {}, is_published: true, install_count: 3, created_at: "", updated_at: "", ...over,
});
const preview = (valid: boolean): BlueprintPreview => ({
  id: "b1", slug: "onboarding", name: "Employee Onboarding", valid, errors: valid ? [] : ["bad field_type"],
  summary: { entities: 2, workflows: 1, rules: 0, reports: 1, notification_templates: 1 }, manifest: {},
});

beforeEach(() => {
  listQ.data = { results: [], count: 0 };
  previewQ.data = undefined;
  install.mutateAsync.mockClear();
  vi.clearAllMocks();
});

describe("ProcessCatalog", () => {
  it("lists published blueprints", () => {
    listQ.data = { results: [bp()], count: 1 };
    render(<ProcessCatalog />);
    expect(screen.getByText("Employee Onboarding")).toBeInTheDocument();
    expect(screen.getByText("3 install(s)")).toBeInTheDocument();
  });

  it("previews and installs after consent", async () => {
    listQ.data = { results: [bp()], count: 1 };
    previewQ.data = preview(true);
    render(<ProcessCatalog />);
    fireEvent.click(screen.getByRole("button", { name: "Preview Employee Onboarding" }));
    // summary surfaced
    expect(screen.getByLabelText("Entities")).toHaveTextContent("2");
    // install gated on consent
    expect(screen.getByRole("button", { name: "Install process" })).toBeDisabled();
    fireEvent.click(screen.getByLabelText("Consent to install"));
    fireEvent.click(screen.getByRole("button", { name: "Install process" }));
    await waitFor(() => expect(install.mutateAsync).toHaveBeenCalledWith("b1"));
  });

  it("blocks install on an invalid manifest", () => {
    listQ.data = { results: [bp()], count: 1 };
    previewQ.data = preview(false);
    render(<ProcessCatalog />);
    fireEvent.click(screen.getByRole("button", { name: "Preview Employee Onboarding" }));
    expect(screen.getByText(/bad field_type/)).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Consent to install"));
    expect(screen.getByRole("button", { name: "Install process" })).toBeDisabled();
  });
});
