import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
  InstalledSolution,
  WizardOptions,
  WizardPreview,
  WizardSelection,
} from "@/lib/solution-templates/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

// Mutation/query stubs shared across tests (mutateAsync args are never-typed → cast at call sites).
const resolve = { mutateAsync: vi.fn(), isPending: false };
const preview = {
  mutateAsync: vi.fn(),
  isPending: false,
  isError: false,
  data: undefined as WizardPreview | undefined,
};
const create = {
  mutateAsync: vi.fn(),
  isPending: false,
  isError: false,
};
const tenant = { workspace: { role: "owner" } as { role: string } | null };
const optionsQ = {
  isLoading: false,
  isError: false,
  data: undefined as WizardOptions | undefined,
};

vi.mock("@/lib/tenant/context", () => ({ useTenant: () => tenant }));
vi.mock("@/lib/solution-templates/hooks", () => ({
  useWizardOptions: () => optionsQ,
  useResolveDependencies: () => resolve,
  usePreviewSolution: () => preview,
  useCreateSolution: () => create,
}));

import { CreateSolutionWizard, WizardFlow } from "./create-solution-wizard";

const OPTIONS: WizardOptions = {
  solution_types: [
    {
      key: "crm",
      label: "CRM",
      recommends: {
        business_objects: ["customer", "contact"],
        workflows: ["assignment"],
        roles: ["manager"],
        dashboards: ["operational"],
        reports: ["summary"],
      },
    },
    {
      key: "hr",
      label: "HR",
      recommends: { business_objects: ["employee"], workflows: [], roles: [], dashboards: [], reports: [] },
    },
  ],
  industries: [
    {
      key: "retail",
      label: "Retail",
      recommends: {
        business_objects: ["customer", "store"],
        workflows: ["approval"],
        roles: ["manager"],
        dashboards: ["executive"],
        reports: ["trend"],
      },
    },
  ],
  library: {
    business_objects: [
      { slug: "customer", name: "Customer", plural_name: "Customers" },
      { slug: "contact", name: "Contact", plural_name: "Contacts" },
      { slug: "store", name: "Store", plural_name: "Stores" },
      { slug: "employee", name: "Employee", plural_name: "Employees" },
    ],
    workflows: [
      { slug: "approval", name: "Approval" },
      { slug: "assignment", name: "Assignment" },
    ],
    roles: [
      { slug: "manager", name: "Manager" },
      { slug: "administrator", name: "Administrator" },
    ],
    dashboards: [
      { slug: "executive", name: "Executive" },
      { slug: "operational", name: "Operational" },
    ],
    reports: [],
  },
};

const previewResult = (valid: boolean): WizardPreview => ({
  valid,
  errors: valid ? [] : ["duplicate slug customer"],
  warnings: ["customer already exists — it will be reused"],
  resolved_objects: ["customer", "contact"],
  summary: {
    entities: 2,
    forms: 2,
    views: 2,
    workflows: 1,
    rules: 0,
    reports: 1,
    notification_templates: 0,
    roles: 1,
    dashboards: 1,
    applications: 1,
    navigations: 1,
    home_layouts: 1,
  },
  manifest: {},
});

beforeEach(() => {
  vi.clearAllMocks();
  tenant.workspace = { role: "owner" };
  optionsQ.isLoading = false;
  optionsQ.isError = false;
  optionsQ.data = OPTIONS;
  resolve.isPending = false;
  resolve.mutateAsync.mockResolvedValue({ resolved_objects: ["customer", "contact"] });
  preview.isPending = false;
  preview.isError = false;
  preview.data = undefined;
  preview.mutateAsync.mockImplementation(() => {
    preview.data = previewResult(true);
    return Promise.resolve(preview.data);
  });
  create.isPending = false;
  create.isError = false;
  create.mutateAsync.mockResolvedValue({
    id: "i1",
    solution_name: "Sales CRM",
    created_entity_ids: ["e1", "e2"],
  } as unknown as InstalledSolution);
});

/** Walk the wizard to the Configure step having chosen CRM. */
function advanceToConfigure() {
  fireEvent.click(screen.getByRole("button", { name: "Select CRM" }));
  fireEvent.click(screen.getByRole("button", { name: "Next" })); // → industry
  fireEvent.click(screen.getByRole("button", { name: "Skip industry preset" }));
  fireEvent.click(screen.getByRole("button", { name: "Next" })); // → blocks
  fireEvent.click(screen.getByRole("button", { name: "Next" })); // → configure
}

describe("CreateSolutionWizard gating", () => {
  it("blocks non-admins before they can reach create", () => {
    tenant.workspace = { role: "member" };
    render(<CreateSolutionWizard />);
    expect(screen.getByText(/Only owners and admins can create solutions/)).toBeInTheDocument();
  });

  it("renders the flow for admins", () => {
    render(<CreateSolutionWizard />);
    expect(screen.getByText("Choose a solution type")).toBeInTheDocument();
  });
});

describe("WizardFlow", () => {
  it("prefills recommended building blocks when a type is chosen", () => {
    render(<WizardFlow options={OPTIONS} />);
    fireEvent.click(screen.getByRole("button", { name: "Select CRM" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Skip industry preset" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" })); // → blocks

    // CRM recommends customer + contact business objects (checked).
    expect(screen.getByLabelText("Business objects: Customers")).toBeChecked();
    expect(screen.getByLabelText("Business objects: Contacts")).toBeChecked();
    expect(screen.getByLabelText("Business objects: Employees")).not.toBeChecked();
  });

  it("merges an industry preset over the type defaults", () => {
    render(<WizardFlow options={OPTIONS} />);
    fireEvent.click(screen.getByRole("button", { name: "Select CRM" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Select Retail" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" })); // → blocks

    // Retail recommends customer + store (overrides CRM's contact).
    expect(screen.getByLabelText("Business objects: Customers")).toBeChecked();
    expect(screen.getByLabelText("Business objects: Stores")).toBeChecked();
    expect(screen.getByLabelText("Business objects: Contacts")).not.toBeChecked();
  });

  it("resolves and surfaces auto-included dependencies for the selection", async () => {
    resolve.mutateAsync.mockResolvedValue({ resolved_objects: ["customer", "contact", "address"] });
    render(<WizardFlow options={OPTIONS} />);
    fireEvent.click(screen.getByRole("button", { name: "Select CRM" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Skip industry preset" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" })); // → blocks

    await waitFor(() =>
      expect(resolve.mutateAsync).toHaveBeenCalledWith(["customer", "contact"]),
    );
    // "address" is auto-included (not user-picked) and shown as a chip.
    await waitFor(() => expect(screen.getByText("address")).toBeInTheDocument());
  });

  it("composes the selection and posts it to preview after Configure", async () => {
    render(<WizardFlow options={OPTIONS} />);
    advanceToConfigure();

    fireEvent.change(screen.getByLabelText("Solution name"), { target: { value: "Sales CRM" } });
    fireEvent.click(screen.getByRole("button", { name: "Preview solution" }));

    await waitFor(() => expect(preview.mutateAsync).toHaveBeenCalled());
    const sent = preview.mutateAsync.mock.calls[0][0] as WizardSelection;
    expect(sent.solution_type).toBe("crm");
    expect(sent.business_objects).toEqual(["customer", "contact"]);
    expect(sent.workflows).toEqual(["assignment"]);
    expect(sent.config.solution_name).toBe("Sales CRM");
    expect(sent.config.application_name).toBe("Sales CRM"); // mirrored from solution name
  });

  it("disables Continue on an invalid preview", async () => {
    preview.mutateAsync.mockImplementation(() => {
      preview.data = previewResult(false);
      return Promise.resolve(preview.data);
    });
    render(<WizardFlow options={OPTIONS} />);
    advanceToConfigure();
    fireEvent.change(screen.getByLabelText("Solution name"), { target: { value: "Sales CRM" } });
    fireEvent.click(screen.getByRole("button", { name: "Preview solution" }));

    await waitFor(() => expect(screen.getByText(/duplicate slug customer/)).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();
    // warnings are surfaced regardless of validity
    expect(screen.getByText(/already exists — it will be reused/)).toBeInTheDocument();
  });

  it("creates the composed solution and routes to /solutions", async () => {
    render(<WizardFlow options={OPTIONS} />);
    advanceToConfigure();
    fireEvent.change(screen.getByLabelText("Solution name"), { target: { value: "Sales CRM" } });
    fireEvent.click(screen.getByRole("button", { name: "Preview solution" }));

    await waitFor(() => expect(screen.getByRole("button", { name: "Continue" })).not.toBeDisabled());
    fireEvent.click(screen.getByRole("button", { name: "Continue" })); // → create step
    fireEvent.click(screen.getByRole("button", { name: "Create solution" }));

    await waitFor(() => expect(create.mutateAsync).toHaveBeenCalled());
    const sent = create.mutateAsync.mock.calls[0][0] as WizardSelection;
    expect(sent.solution_type).toBe("crm");
    expect(sent.config.solution_name).toBe("Sales CRM");
    await waitFor(() => expect(push).toHaveBeenCalledWith("/solutions"));
  });
});
