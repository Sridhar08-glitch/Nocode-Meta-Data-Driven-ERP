import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { EmailTemplate } from "@/lib/email-templates/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const listQ = { isLoading: false, isError: false, data: { results: [] as EmailTemplate[], count: 0 } };
const create = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const update = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const del = { mutateAsync: vi.fn(() => Promise.resolve(null)), isPending: false };
const renderM = { mutateAsync: vi.fn(() => Promise.resolve({ subject: "Hi Ada", html: "<p>Hi Ada</p>" })), isPending: false };
const testSend = { mutateAsync: vi.fn(() => Promise.resolve({ sent: true })), isPending: false };
vi.mock("@/lib/email-templates/hooks", () => ({
  useEmailTemplates: () => listQ,
  useCreateEmailTemplate: () => create,
  useUpdateEmailTemplate: () => update,
  useDeleteEmailTemplate: () => del,
  useRenderEmailTemplate: () => renderM,
  useTestSendEmailTemplate: () => testSend,
}));

import { EmailTemplateBuilder } from "./email-template-builder";

const tpl = (over: Partial<EmailTemplate> = {}): EmailTemplate => ({
  id: "t1", name: "Welcome", slug: "welcome", locale: "en", subject_template: "Hi ${name}", body_html: "<p>Hi ${name}</p>",
  blocks: [], variables: [], version: 1, is_active: true, created_at: "", updated_at: "", ...over,
});

beforeEach(() => {
  listQ.data = { results: [], count: 0 };
  for (const m of [create, update, del, renderM, testSend]) m.mutateAsync.mockClear();
  vi.clearAllMocks();
});

describe("EmailTemplateBuilder", () => {
  it("creates a locale-aware template", async () => {
    render(<EmailTemplateBuilder />);
    fireEvent.click(screen.getAllByRole("button", { name: "New template" })[0]);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Order shipped" } });
    fireEvent.change(screen.getByLabelText("Locale"), { target: { value: "fr-FR" } });
    fireEvent.change(screen.getByLabelText("Body (HTML, sanitized server-side)"), { target: { value: "<p>Bonjour</p>" } });
    fireEvent.click(screen.getByRole("button", { name: "Create template" }));
    await waitFor(() => expect(create.mutateAsync).toHaveBeenCalled());
    expect(create.mutateAsync).toHaveBeenCalledWith(expect.objectContaining({ slug: "order_shipped", locale: "fr-FR", body_html: "<p>Bonjour</p>" }));
  });

  it("renders a server preview from the edit dialog", async () => {
    listQ.data = { results: [tpl()], count: 1 };
    render(<EmailTemplateBuilder />);
    fireEvent.click(screen.getByRole("button", { name: "Edit Welcome" }));
    fireEvent.change(screen.getByLabelText("Sample context (JSON)"), { target: { value: '{"name":"Ada"}' } });
    fireEvent.click(screen.getByRole("button", { name: "Render preview" }));
    await waitFor(() => expect(renderM.mutateAsync).toHaveBeenCalledWith({ id: "t1", context: { name: "Ada" } }));
    expect(await screen.findByLabelText("Email preview")).toBeInTheDocument();
  });

  it("test-sends to a recipient", async () => {
    listQ.data = { results: [tpl()], count: 1 };
    render(<EmailTemplateBuilder />);
    fireEvent.click(screen.getByRole("button", { name: "Edit Welcome" }));
    fireEvent.change(screen.getByLabelText("Test recipient"), { target: { value: "qa@acme.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send test email" }));
    await waitFor(() => expect(testSend.mutateAsync).toHaveBeenCalledWith(expect.objectContaining({ id: "t1", toEmail: "qa@acme.com" })));
  });
});
