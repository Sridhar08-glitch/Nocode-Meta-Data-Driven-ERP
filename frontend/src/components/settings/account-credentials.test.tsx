import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const changePassword = vi.fn().mockResolvedValue({ detail: "ok" });
const changeEmail = vi.fn().mockResolvedValue({ detail: "ok" });
vi.mock("@/lib/auth/api", () => ({
  authApi: {
    changePassword: (d: unknown) => changePassword(d),
    changeEmail: (d: unknown) => changeEmail(d),
  },
}));

import { AccountCredentials } from "./account-credentials";

beforeEach(() => vi.clearAllMocks());

describe("AccountCredentials", () => {
  it("submits a password change with current + new password", async () => {
    render(<AccountCredentials />);
    fireEvent.change(screen.getByLabelText("Current password"), { target: { value: "oldpw" } });
    fireEvent.change(screen.getByLabelText("New password"), { target: { value: "N3wStr0ngerPwd!" } });
    fireEvent.click(screen.getByRole("button", { name: "Change password" }));
    await waitFor(() =>
      expect(changePassword).toHaveBeenCalledWith({ current_password: "oldpw", password: "N3wStr0ngerPwd!" }));
    expect(await screen.findByText(/Other sessions were signed out/)).toBeInTheDocument();
  });

  it("submits an email change with new email + password", async () => {
    render(<AccountCredentials />);
    fireEvent.change(screen.getByLabelText("New email address"), { target: { value: "new@acme.com" } });
    fireEvent.change(screen.getByLabelText("Confirm with password"), { target: { value: "pw" } });
    fireEvent.click(screen.getByRole("button", { name: "Send confirmation" }));
    await waitFor(() =>
      expect(changeEmail).toHaveBeenCalledWith({ new_email: "new@acme.com", password: "pw" }));
  });
});
