import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { InstalledSolution, SolutionTemplate, TemplatePreview } from "@/lib/solution-templates/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const listQ = { isLoading: false, isError: false, data: { results: [] as SolutionTemplate[], count: 0 } };
const previewQ = { isLoading: false, isError: false, data: undefined as TemplatePreview | undefined };
const installedQ = { isLoading: false, isError: false, data: { results: [] as InstalledSolution[], count: 0 } };
const install = {
  mutateAsync: vi.fn(() => Promise.resolve({ id: "i1", solution_name: "CRM", created_entity_ids: ["e1", "e2"], created_application_ids: ["a1"] } as unknown as InstalledSolution)),
  isPending: false,
};
const uninstall = { mutateAsync: vi.fn(() => Promise.resolve({} as InstalledSolution)), isPending: false };

vi.mock("@/lib/solution-templates/hooks", () => ({
  useTemplates: () => listQ,
  useTemplatePreview: () => previewQ,
  useInstalledSolutions: () => installedQ,
  useInstallTemplate: () => install,
  useUninstallSolution: () => uninstall,
}));

import { Browse, InstalledSolutions } from "./solution-catalog";

const tpl = (over: Partial<SolutionTemplate> = {}): SolutionTemplate => ({
  id: "t1", name: "CRM Suite", slug: "crm_suite", category: "sales", description: "Leads to deals",
  publisher: "Nexus", icon: "📇", color: "#3366ff", version: "1.0.0", is_system: true, is_published: true,
  install_count: 7,
  summary: { entities: 4, forms: 3, views: 5, workflows: 2, rules: 1, reports: 2, roles: 2, dashboards: 1, applications: 1 },
  created_at: "", ...over,
});
const preview = (valid: boolean): TemplatePreview => ({
  id: "t1", slug: "crm_suite", name: "CRM Suite", category: "sales", version: "1.0.0", valid,
  errors: valid ? [] : ["bad field_type in entity lead"],
  summary: { entities: 4, forms: 3, views: 5, workflows: 2, rules: 1, reports: 2, notification_templates: 1, roles: 2, dashboards: 1, applications: 1, navigations: 1, home_layouts: 1 },
  manifest: {},
});
const installed = (over: Partial<InstalledSolution> = {}): InstalledSolution => ({
  id: "i1", solution_template_id: "t1", solution_slug: "crm_suite", solution_name: "CRM Suite",
  installed_version: "1.0.0", status: "active",
  summary: { entities: 4, forms: 3, views: 5, workflows: 2, rules: 1, reports: 2, roles: 2, dashboards: 1, applications: 1 },
  created_entity_ids: ["e1", "e2"], created_application_ids: ["a1"], created_at: "", ...over,
});

beforeEach(() => {
  listQ.data = { results: [], count: 0 };
  previewQ.data = undefined;
  installedQ.data = { results: [], count: 0 };
  install.mutateAsync.mockClear();
  uninstall.mutateAsync.mockClear();
  vi.clearAllMocks();
});

describe("Browse", () => {
  it("lists published solution templates with summary badges", () => {
    listQ.data = { results: [tpl()], count: 1 };
    render(<Browse canManage />);
    expect(screen.getByText("CRM Suite")).toBeInTheDocument();
    expect(screen.getByText("4 entities")).toBeInTheDocument();
    expect(screen.getByText("v1.0.0 · 7 install(s)")).toBeInTheDocument();
  });

  it("renders preview summary counts and installs after consent (admin)", async () => {
    listQ.data = { results: [tpl()], count: 1 };
    previewQ.data = preview(true);
    render(<Browse canManage />);
    fireEvent.click(screen.getByRole("button", { name: "Preview CRM Suite" }));
    // preview summary surfaced
    expect(screen.getByLabelText("Entities")).toHaveTextContent("4");
    expect(screen.getByLabelText("Workflows")).toHaveTextContent("2");
    // install gated on consent
    expect(screen.getByRole("button", { name: "Install solution" })).toBeDisabled();
    fireEvent.click(screen.getByLabelText("Consent to install"));
    fireEvent.click(screen.getByRole("button", { name: "Install solution" }));
    await waitFor(() => expect(install.mutateAsync).toHaveBeenCalledWith("t1"));
  });

  it("blocks install on an invalid manifest", () => {
    listQ.data = { results: [tpl()], count: 1 };
    previewQ.data = preview(false);
    render(<Browse canManage />);
    fireEvent.click(screen.getByRole("button", { name: "Preview CRM Suite" }));
    expect(screen.getByText(/bad field_type/)).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Consent to install"));
    expect(screen.getByRole("button", { name: "Install solution" })).toBeDisabled();
  });

  it("hides install for non-admins", () => {
    listQ.data = { results: [tpl()], count: 1 };
    previewQ.data = preview(true);
    render(<Browse canManage={false} />);
    fireEvent.click(screen.getByRole("button", { name: "Preview CRM Suite" }));
    expect(screen.queryByRole("button", { name: "Install solution" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Consent to install")).not.toBeInTheDocument();
    expect(screen.getByText(/Only workspace owners and admins/)).toBeInTheDocument();
  });
});

describe("InstalledSolutions", () => {
  it("lists installed solutions and soft-uninstalls with {hard:false}", async () => {
    installedQ.data = { results: [installed()], count: 1 };
    render(<InstalledSolutions canManage />);
    expect(screen.getByText("CRM Suite")).toBeInTheDocument();
    expect(screen.getByText("2 entities · 1 apps")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Uninstall CRM Suite" }));
    fireEvent.click(screen.getByRole("button", { name: "Soft uninstall" }));
    await waitFor(() => expect(uninstall.mutateAsync).toHaveBeenCalledWith({ id: "i1", hard: false }));
  });

  it("hard-uninstalls with {hard:true}", async () => {
    installedQ.data = { results: [installed()], count: 1 };
    render(<InstalledSolutions canManage />);
    fireEvent.click(screen.getByRole("button", { name: "Uninstall CRM Suite" }));
    fireEvent.click(screen.getByRole("button", { name: "Hard uninstall" }));
    await waitFor(() => expect(uninstall.mutateAsync).toHaveBeenCalledWith({ id: "i1", hard: true }));
  });

  it("hides uninstall controls for non-admins", () => {
    installedQ.data = { results: [installed()], count: 1 };
    render(<InstalledSolutions canManage={false} />);
    expect(screen.getByText("CRM Suite")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Uninstall CRM Suite" })).not.toBeInTheDocument();
  });

  it("shows an empty state when nothing is installed", () => {
    render(<InstalledSolutions canManage />);
    expect(screen.getByText("No solutions installed")).toBeInTheDocument();
  });
});
