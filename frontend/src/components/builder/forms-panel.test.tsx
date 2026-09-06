import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/errors";
import type { FormDefinition } from "@/lib/metadata/types";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));
const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const formsQ = { isLoading: false, isError: false, data: [] as FormDefinition[] };
const del = { mutateAsync: vi.fn(), isPending: false };
vi.mock("@/lib/metadata/builder-hooks", () => ({
  useForms: () => formsQ,
  useDeleteForm: () => del,
}));

import { FormsPanel } from "./forms-panel";

function form(over: Partial<FormDefinition> = {}): FormDefinition {
  return {
    id: "f1",
    entity: "e1",
    entity_slug: "lead",
    name: "Intake",
    is_default: true,
    is_public: true,
    layout: [{ key: "main", title: "Details", columns: 1, fields: [], condition: null }],
    settings: {},
    ...over,
  };
}

beforeEach(() => {
  formsQ.isLoading = false;
  formsQ.isError = false;
  formsQ.data = [];
  del.isPending = false;
  del.mutateAsync.mockReset().mockResolvedValue(null);
  vi.clearAllMocks();
});

describe("FormsPanel", () => {
  it("renders a loading skeleton", () => {
    formsQ.isLoading = true;
    const { container } = render(<FormsPanel entity="lead" />);
    expect(container.querySelector(".h-48")).toBeTruthy();
  });

  it("renders an error state", () => {
    formsQ.isError = true;
    render(<FormsPanel entity="lead" />);
    expect(screen.getByText("Couldn't load forms")).toBeInTheDocument();
  });

  it("treats undefined data as empty", () => {
    formsQ.data = undefined as unknown as FormDefinition[];
    render(<FormsPanel entity="lead" />);
    expect(screen.getByText("No custom forms")).toBeInTheDocument();
  });

  it("empty state navigates to the new-form route", () => {
    render(<FormsPanel entity="lead" />);
    expect(screen.getByText("No custom forms")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "New form" })[0]);
    expect(push).toHaveBeenCalledWith("/studio/lead/forms/new");
  });

  it("navigates from the empty-state action", () => {
    render(<FormsPanel entity="lead" />);
    const actions = screen.getAllByRole("button", { name: "New form" });
    fireEvent.click(actions[actions.length - 1]); // EmptyState action button
    expect(push).toHaveBeenCalledWith("/studio/lead/forms/new");
  });

  it("lists forms with default/public badges and edits one", () => {
    formsQ.data = [form()];
    render(<FormsPanel entity="lead" />);
    expect(screen.getByText("Intake")).toBeInTheDocument();
    expect(screen.getByText("default")).toBeInTheDocument();
    expect(screen.getByText("public")).toBeInTheDocument();
    expect(screen.getByText("1 sections")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    expect(push).toHaveBeenCalledWith("/studio/lead/forms/f1");
  });

  it("deletes a form", async () => {
    formsQ.data = [form({ is_default: false, is_public: false })];
    render(<FormsPanel entity="lead" />);
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(del.mutateAsync).toHaveBeenCalledWith("f1"));
    expect(toast.success).toHaveBeenCalled();
  });

  it("surfaces a delete error", async () => {
    del.mutateAsync.mockRejectedValueOnce(new Error("x"));
    formsQ.data = [form()];
    render(<FormsPanel entity="lead" />);
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
  });

  it("uses the ApiError message on a typed delete failure", async () => {
    del.mutateAsync.mockRejectedValueOnce(new ApiError({ status: 409, message: "form locked" }));
    formsQ.data = [form()];
    render(<FormsPanel entity="lead" />);
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("form locked"));
  });
});
