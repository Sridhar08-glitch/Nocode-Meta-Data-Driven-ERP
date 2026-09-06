import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { FormSubmission, PublicFormDef } from "@/lib/public-forms/admin-api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const formsQ = { isLoading: false, isError: false, data: { results: [] as PublicFormDef[] } };
const subsQ = { isLoading: false, isError: false, data: { results: [] as FormSubmission[], count: 0 } };
const update = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const approve = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const reject = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };

vi.mock("@/lib/public-forms/admin-hooks", () => ({
  usePublicForms: () => formsQ,
  useUpdatePublicForm: () => update,
  useFormSubmissions: () => subsQ,
  useApproveSubmission: () => approve,
  useRejectSubmission: () => reject,
}));

import { PublicFormsAdmin } from "./public-forms-admin";

const form = (over: Partial<PublicFormDef> = {}): PublicFormDef => ({
  id: "f1", entity: "ent1", entity_slug: "lead", name: "Contact us",
  is_default: false, is_public: false, created_at: "", ...over,
});
const sub = (over: Partial<FormSubmission> = {}): FormSubmission => ({
  id: "s1", form_id: "f1", entity_id: "ent1", status: "pending", data: { email: "a@b.com" },
  created_record_id: null, submitter_name: "Jane", submitter_email: "jane@x.com",
  honeypot_triggered: false, spam_score: 0, validation_errors: [], rejection_reason: "",
  created_at: "2026-06-20T09:00:00Z", ...over,
});

beforeEach(() => {
  formsQ.data = { results: [] };
  subsQ.data = { results: [], count: 0 };
  for (const m of [update, approve, reject]) m.mutateAsync.mockClear();
  vi.clearAllMocks();
});

describe("PublicFormsAdmin", () => {
  it("publishes a form by toggling is_public", async () => {
    formsQ.data = { results: [form()] };
    render(<PublicFormsAdmin />);
    fireEvent.click(screen.getByRole("switch", { name: "Publish Contact us" }));
    await waitFor(() =>
      expect(update.mutateAsync).toHaveBeenCalledWith({ id: "f1", data: { is_public: true } }),
    );
  });

  it("shows the copy-URL action only for public forms", () => {
    formsQ.data = { results: [form({ is_public: true })] };
    render(<PublicFormsAdmin />);
    expect(screen.getByRole("button", { name: "Copy public URL for Contact us" })).toBeInTheDocument();
  });

  it("approves a pending submission from the inbox", async () => {
    formsQ.data = { results: [form()] };
    subsQ.data = { results: [sub()], count: 1 };
    render(<PublicFormsAdmin />);
    fireEvent.click(screen.getByRole("button", { name: "Submissions for Contact us" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Approve submission s1" }));
    await waitFor(() => expect(approve.mutateAsync).toHaveBeenCalledWith({ formId: "f1", subId: "s1" }));
  });

  it("rejects a submission with a reason", async () => {
    formsQ.data = { results: [form()] };
    subsQ.data = { results: [sub()], count: 1 };
    render(<PublicFormsAdmin />);
    fireEvent.click(screen.getByRole("button", { name: "Submissions for Contact us" }));
    fireEvent.click(await screen.findByRole("button", { name: "Reject submission s1" }));
    fireEvent.change(screen.getByLabelText("Rejection reason"), { target: { value: "spam" } });
    fireEvent.click(screen.getByRole("button", { name: "Reject" }));
    await waitFor(() =>
      expect(reject.mutateAsync).toHaveBeenCalledWith({ formId: "f1", subId: "s1", reason: "spam" }),
    );
  });

  it("renders an empty state when there are no forms", () => {
    render(<PublicFormsAdmin />);
    expect(screen.getByText("No forms")).toBeInTheDocument();
  });
});
