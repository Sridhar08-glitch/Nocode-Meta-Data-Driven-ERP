import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Passkey } from "@/lib/auth/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const api = vi.hoisted(() => ({
  mfaSetupInitiate: vi.fn(),
  mfaSetupConfirm: vi.fn(),
  mfaDisable: vi.fn(),
  passkeyRegisterBegin: vi.fn(),
  passkeyRegisterComplete: vi.fn(),
  listPasskeys: vi.fn(),
  deletePasskey: vi.fn(),
}));
vi.mock("@/lib/auth/api", () => ({ authApi: api }));

const webauthn = vi.hoisted(() => ({ registerPasskey: vi.fn(), isPasskeySupported: vi.fn(() => true) }));
vi.mock("@/lib/webauthn/client", () => webauthn);

const authState = vi.hoisted(() => ({ user: { id: "u1", email: "a@b.com", full_name: "A", mfa_enabled: false }, setUser: vi.fn() }));
vi.mock("@/lib/auth/session", () => ({ useAuthStore: (sel: (s: typeof authState) => unknown) => sel(authState) }));

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SecuritySettings } from "./security-settings";

function renderWithQuery(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  authState.user = { id: "u1", email: "a@b.com", full_name: "A", mfa_enabled: false };
  authState.setUser.mockClear();
  for (const fn of Object.values(api)) fn.mockReset();
  api.listPasskeys.mockResolvedValue([] as Passkey[]);
  webauthn.registerPasskey.mockReset().mockResolvedValue({ id: "cred", rawId: "r", type: "public-key", response: { attestationObject: "a", clientDataJSON: "c" } });
  webauthn.isPasskeySupported.mockReturnValue(true);
  vi.clearAllMocks();
  api.listPasskeys.mockResolvedValue([]);
});

describe("SecuritySettings — TOTP", () => {
  it("runs the enroll flow: initiate → confirm → backup codes → enables", async () => {
    api.mfaSetupInitiate.mockResolvedValue({ secret: "ABCD1234", qr_uri: "otpauth://x" });
    api.mfaSetupConfirm.mockResolvedValue({ detail: "ok", backup_codes: ["aaa-bbb", "ccc-ddd"] });
    renderWithQuery(<SecuritySettings />);
    fireEvent.click(screen.getByRole("button", { name: "Set up" }));
    expect(await screen.findByLabelText("TOTP secret")).toHaveTextContent("ABCD1234");
    fireEvent.change(screen.getByLabelText("6-digit code"), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: /Verify/ }));
    await waitFor(() => expect(api.mfaSetupConfirm).toHaveBeenCalledWith("123456"));
    expect(await screen.findByLabelText("Backup codes")).toHaveTextContent("aaa-bbb");
    expect(authState.setUser).toHaveBeenCalledWith(expect.objectContaining({ mfa_enabled: true }));
  });

  it("disables TOTP with a password", async () => {
    authState.user = { ...authState.user, mfa_enabled: true };
    api.mfaDisable.mockResolvedValue({ detail: "ok" });
    renderWithQuery(<SecuritySettings />);
    fireEvent.click(screen.getByRole("button", { name: "Disable" })); // section button → opens dialog
    const dialog = screen.getByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Confirm your password"), { target: { value: "pw" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Disable" }));
    await waitFor(() => expect(api.mfaDisable).toHaveBeenCalledWith("pw"));
    expect(authState.setUser).toHaveBeenCalledWith(expect.objectContaining({ mfa_enabled: false }));
  });
});

describe("SecuritySettings — Passkeys", () => {
  it("registers a passkey via the WebAuthn ceremony", async () => {
    api.passkeyRegisterBegin.mockResolvedValue({ publicKey: { challenge: "x" } });
    api.passkeyRegisterComplete.mockResolvedValue({ detail: "ok" });
    renderWithQuery(<SecuritySettings />);
    fireEvent.click(screen.getByRole("button", { name: "Add passkey" }));
    fireEvent.change(screen.getByLabelText("Name (optional)"), { target: { value: "MacBook" } });
    fireEvent.click(screen.getByRole("button", { name: "Register passkey" }));
    await waitFor(() => expect(api.passkeyRegisterComplete).toHaveBeenCalled());
    expect(webauthn.registerPasskey).toHaveBeenCalledWith({ challenge: "x" });
    expect(api.passkeyRegisterComplete).toHaveBeenCalledWith(expect.objectContaining({ name: "MacBook" }));
  });

  it("lists and deletes a passkey", async () => {
    api.listPasskeys.mockResolvedValue([{ id: "k1", name: "YubiKey", created_at: "2026-01-01", last_used_at: null }]);
    api.deletePasskey.mockResolvedValue(undefined);
    renderWithQuery(<SecuritySettings />);
    expect(await screen.findByText("YubiKey")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Remove passkey YubiKey" }));
    await waitFor(() => expect(api.deletePasskey).toHaveBeenCalledWith("k1"));
  });
});
