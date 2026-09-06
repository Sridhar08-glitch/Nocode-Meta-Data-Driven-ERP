import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { BrandingSettings as TBranding, SMTPConfig } from "@/lib/branding/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const brandingQ = { isLoading: false, isError: false, data: { app_name: "Acme", color_primary: "#112233" } as TBranding };
const smtpQ = { data: {} as SMTPConfig | Record<string, never> };
const update = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const saveSmtp = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const testSmtp = { mutateAsync: vi.fn(() => Promise.resolve({ success: true })), isPending: false };
vi.mock("@/lib/branding/hooks", () => ({
  useBranding: () => brandingQ,
  useUpdateBranding: () => update,
  useSmtpConfig: () => smtpQ,
  useSaveSmtp: () => saveSmtp,
  useTestSmtp: () => testSmtp,
}));

import { BrandingSettings } from "./branding-settings";

beforeEach(() => {
  update.mutateAsync.mockClear();
  saveSmtp.mutateAsync.mockClear();
  testSmtp.mutateAsync.mockClear();
  vi.clearAllMocks();
});

describe("BrandingSettings", () => {
  it("loads + saves branding fields", async () => {
    render(<BrandingSettings />);
    expect(screen.getByLabelText("App name")).toHaveValue("Acme");
    fireEvent.change(screen.getByLabelText("App name"), { target: { value: "Acme Corp" } });
    fireEvent.click(screen.getByRole("button", { name: "Save branding" }));
    await waitFor(() => expect(update.mutateAsync).toHaveBeenCalled());
    expect(update.mutateAsync).toHaveBeenCalledWith(expect.objectContaining({ app_name: "Acme Corp", color_primary: "#112233" }));
  });

  it("saves + tests SMTP", async () => {
    render(<BrandingSettings />);
    fireEvent.change(screen.getByLabelText("Host"), { target: { value: "smtp.acme.com" } });
    fireEvent.change(screen.getByLabelText("From email"), { target: { value: "no@acme.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Save SMTP" }));
    await waitFor(() => expect(saveSmtp.mutateAsync).toHaveBeenCalled());
    expect(saveSmtp.mutateAsync).toHaveBeenCalledWith(expect.objectContaining({ host: "smtp.acme.com", from_email: "no@acme.com" }));
    fireEvent.click(screen.getByRole("button", { name: "Send test" }));
    await waitFor(() => expect(testSmtp.mutateAsync).toHaveBeenCalled());
    // last-test history surfaces in-session
    await waitFor(() => expect(within(screen.getByLabelText("Last SMTP test")).getByText(/Success/)).toBeInTheDocument());
  });

  it("blocks save on an invalid hex color", () => {
    render(<BrandingSettings />);
    fireEvent.change(screen.getByLabelText("Primary hex"), { target: { value: "nope" } });
    expect(screen.getByText("Enter a hex color like #2563eb.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save branding" })).toBeDisabled();
  });

  it("blocks save on malformed custom CSS", () => {
    render(<BrandingSettings />);
    fireEvent.change(screen.getByLabelText("Custom CSS (sanitized server-side)"), { target: { value: ".a {" } });
    expect(screen.getByText(/never closed/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save branding" })).toBeDisabled();
  });

  it("live preview reflects unsaved app name", () => {
    render(<BrandingSettings />);
    fireEvent.change(screen.getByLabelText("App name"), { target: { value: "Acme Corp" } });
    expect(within(screen.getByLabelText("Branding preview")).getAllByText("Acme Corp").length).toBeGreaterThan(0);
  });

  it("restores defaults after confirmation", () => {
    render(<BrandingSettings />);
    fireEvent.click(screen.getByRole("button", { name: "Restore defaults" }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Restore defaults" }));
    expect(screen.getByLabelText("App name")).toHaveValue("");
    expect(screen.getByLabelText("Primary hex")).toHaveValue("#6366f1");
  });
});
