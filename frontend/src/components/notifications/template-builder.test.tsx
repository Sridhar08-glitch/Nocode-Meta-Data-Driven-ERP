import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { NotificationTemplate } from "@/lib/notifications/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const templatesQ = { isLoading: false, isError: false, data: [] as NotificationTemplate[] };
const create = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const update = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const del = { mutateAsync: vi.fn(() => Promise.resolve(null)), isPending: false };
const test = { mutateAsync: vi.fn(() => Promise.resolve({ sent: 1, notifications: [] })), isPending: false };
vi.mock("@/lib/notifications/hooks", () => ({
  useTemplates: () => templatesQ,
  useCreateTemplate: () => create,
  useUpdateTemplate: () => update,
  useDeleteTemplate: () => del,
  useTestTemplate: () => test,
}));

import { TemplateBuilder } from "./template-builder";

const tpl = (over: Partial<NotificationTemplate> = {}): NotificationTemplate => ({
  id: "t1",
  slug: "welcome",
  name: "Welcome",
  channel: "email",
  subject_template: "Hi ${actor_name}",
  body_template: "Welcome to ${workspace_name}",
  is_system: false,
  created_at: "",
  updated_at: "",
  ...over,
});

beforeEach(() => {
  templatesQ.data = [];
  for (const m of [create, update, del, test]) m.mutateAsync.mockClear();
  vi.clearAllMocks();
});

describe("TemplateBuilder", () => {
  it("lists templates with channel + slug", () => {
    templatesQ.data = [tpl()];
    render(<TemplateBuilder />);
    expect(screen.getByText("Welcome")).toBeInTheDocument();
    expect(screen.getByText("Email")).toBeInTheDocument();
    expect(screen.getByText("welcome")).toBeInTheDocument();
  });

  it("creates a template with auto-slug + body", async () => {
    render(<TemplateBuilder />);
    fireEvent.click(screen.getAllByRole("button", { name: "New template" })[0]);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Order Shipped" } });
    fireEvent.change(screen.getByLabelText("Body"), { target: { value: "Hi ${actor_name}" } });
    fireEvent.click(screen.getByRole("button", { name: "Create template" }));
    await waitFor(() => expect(create.mutateAsync).toHaveBeenCalled());
    expect(create.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ slug: "order_shipped", name: "Order Shipped", channel: "in_app", body_template: "Hi ${actor_name}" }),
    );
  });

  it("inserts a variable token into the body", () => {
    render(<TemplateBuilder />);
    fireEvent.click(screen.getAllByRole("button", { name: "New template" })[0]);
    const body = screen.getByLabelText("Body") as HTMLTextAreaElement;
    fireEvent.change(body, { target: { value: "Hi " } });
    fireEvent.click(screen.getByRole("button", { name: "Insert actor_name into body" }));
    expect(body.value).toBe("Hi ${actor_name}");
  });

  it("test-sends from the edit dialog with a sample context", async () => {
    templatesQ.data = [tpl()];
    render(<TemplateBuilder />);
    fireEvent.click(screen.getByRole("button", { name: "Edit template Welcome" }));
    fireEvent.click(screen.getByRole("button", { name: "Send test notification" }));
    await waitFor(() => expect(test.mutateAsync).toHaveBeenCalled());
    expect(test.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ id: "t1", context: expect.objectContaining({ actor_name: expect.any(String), workspace_name: expect.any(String) }) }),
    );
  });

  it("edits an existing template (slug stays fixed)", async () => {
    templatesQ.data = [tpl()];
    render(<TemplateBuilder />);
    fireEvent.click(screen.getByRole("button", { name: "Edit template Welcome" }));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Welcome v2" } });
    fireEvent.click(screen.getByRole("button", { name: "Save template" }));
    await waitFor(() => expect(update.mutateAsync).toHaveBeenCalled());
    expect(update.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ id: "t1", data: expect.objectContaining({ name: "Welcome v2" }) }),
    );
  });

  it("deletes a template", async () => {
    templatesQ.data = [tpl()];
    render(<TemplateBuilder />);
    fireEvent.click(screen.getByRole("button", { name: "Remove template Welcome" }));
    await waitFor(() => expect(del.mutateAsync).toHaveBeenCalledWith("t1"));
  });

  it("blocks deleting a system template", () => {
    templatesQ.data = [tpl({ is_system: true })];
    render(<TemplateBuilder />);
    expect(screen.getByRole("button", { name: "Remove template Welcome" })).toBeDisabled();
  });

  it("blocks save on an unknown variable (typo)", () => {
    render(<TemplateBuilder />);
    fireEvent.click(screen.getAllByRole("button", { name: "New template" })[0]);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Bad" } });
    fireEvent.change(screen.getByLabelText("Body"), { target: { value: "Hi ${custmer_name}" } });
    expect(screen.getByText("Unknown variable: custmer_name")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create template" })).toBeDisabled();
  });

  it("renders the preview from sample JSON and reports invalid JSON", () => {
    templatesQ.data = [tpl({ body_template: "Welcome to ${workspace_name}", subject_template: "" })];
    render(<TemplateBuilder />);
    fireEvent.click(screen.getByRole("button", { name: "Edit template Welcome" }));
    const json = screen.getByLabelText("Preview sample data (JSON)");
    fireEvent.change(json, { target: { value: '{"workspace_name":"Acme"}' } });
    expect(within(screen.getByLabelText("Template preview")).getByText("Welcome to Acme")).toBeInTheDocument();
    fireEvent.change(json, { target: { value: "{bad" } });
    expect(screen.getByText("Invalid JSON.")).toBeInTheDocument();
  });
});
