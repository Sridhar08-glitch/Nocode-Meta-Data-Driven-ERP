import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useParams: () => ({ slug: "acme" }),
  useRouter: () => ({ replace }),
}));

const meQ = { isLoading: false, isError: false, data: undefined as { email: string } | undefined };
const logout = { mutateAsync: vi.fn(() => Promise.resolve()), isPending: false };
vi.mock("@/lib/portal/hooks", () => ({
  usePortalMe: () => meQ,
  usePortalLogout: () => logout,
}));

import { PortalShell } from "./portal-shell";

beforeEach(() => {
  replace.mockClear();
  meQ.isLoading = false;
  meQ.isError = false;
  meQ.data = undefined;
});

describe("PortalShell (guard + realm isolation)", () => {
  it("redirects to portal login when unauthenticated", async () => {
    meQ.isError = true;
    render(<PortalShell><div>secret</div></PortalShell>);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/portal/acme/login"));
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
  });

  it("renders children + the portal user when authenticated", () => {
    meQ.data = { email: "client@acme.com" };
    render(<PortalShell><div>secret</div></PortalShell>);
    expect(screen.getByText("secret")).toBeInTheDocument();
    expect(screen.getByText("client@acme.com")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });
});
