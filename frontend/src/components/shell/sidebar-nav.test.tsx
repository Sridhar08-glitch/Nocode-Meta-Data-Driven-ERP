import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ResolvedNavigation } from "@/lib/studio/api";

vi.mock("next/navigation", () => ({ usePathname: () => "/home" }));
vi.mock("@/lib/metadata/hooks", () => ({
  useEntities: () => ({ data: [], isLoading: false }),
  useRuntimeEntities: () => ({ data: [], isSuccess: true, isLoading: false }),
  useModules: () => ({ data: [], isLoading: false }),
}));
vi.mock("@/lib/metadata/nav", () => ({
  buildNavGroups: () => [
    { module: { id: "m1", name: "CRM Module" }, entities: [{ id: "e1", slug: "leads", name: "Leads", plural_name: "Leads" }] },
  ],
}));
const activeApp = { activeAppId: null as string | null };
vi.mock("@/lib/studio/active-app", () => ({ useActiveApp: () => ({ activeAppId: activeApp.activeAppId, setActiveApp: vi.fn() }) }));
const navQ = { data: {} as ResolvedNavigation | Record<string, never> };
vi.mock("@/lib/studio/hooks", () => ({ useResolvedNav: () => navQ }));
// installed solutions gate the domain-module links; empty → fall back to showing all.
const installedQ = { data: { results: [] as { solution_slug: string }[] } };
vi.mock("@/lib/solution-templates/hooks", () => ({ useInstalledSolutions: () => installedQ }));
// tenant role gates admin-only links; default to owner so all links render.
const tenant = { workspace: { role: "owner" } as { role: string } | null };
vi.mock("@/lib/tenant/context", () => ({ useTenant: () => tenant }));
// i18n: translate one key, fall back to English for the rest — proves labels go through t().
vi.mock("@/lib/i18n/context", () => ({
  useI18n: () => ({ t: (k: string, f?: string) => (k === "nav.home" ? "Accueil" : f ?? k) }),
}));

import { SidebarNav } from "./sidebar-nav";

beforeEach(() => {
  activeApp.activeAppId = null;
  navQ.data = {};
  tenant.workspace = { role: "owner" };
});

describe("SidebarNav", () => {
  it("localizes fixed nav labels via t() (falls back to English otherwise)", () => {
    render(<SidebarNav />);
    expect(screen.getByText("Accueil")).toBeInTheDocument(); // nav.home translated
    expect(screen.getByText("Documents")).toBeInTheDocument(); // untranslated → English fallback
  });

  it("falls back to the metadata nav when no custom menu is published", () => {
    render(<SidebarNav />);
    expect(screen.getByText("CRM Module")).toBeInTheDocument();
    expect(screen.getByText("Leads")).toBeInTheDocument();
  });

  it("hides admin-only tools from non-admin roles (e.g. teacher/member)", () => {
    tenant.workspace = { role: "member" };
    render(<SidebarNav />);
    // admin-only tools are hidden
    expect(screen.queryByText("Admin")).not.toBeInTheDocument();
    expect(screen.queryByText("Permissions")).not.toBeInTheDocument();
    expect(screen.queryByText("Studio")).not.toBeInTheDocument();
    expect(screen.queryByText("Developer")).not.toBeInTheDocument();
    // everyday tools + entities remain
    expect(screen.getByText("Documents")).toBeInTheDocument();
    expect(screen.getByText("Reports")).toBeInTheDocument();
    expect(screen.getByText("Leads")).toBeInTheDocument();
  });

  it("shows admin-only tools to owner/admin roles", () => {
    tenant.workspace = { role: "admin" };
    render(<SidebarNav />);
    expect(screen.getByText("Admin")).toBeInTheDocument();
    expect(screen.getByText("Permissions")).toBeInTheDocument();
  });

  it("renders a resolved custom menu over the metadata nav", () => {
    activeApp.activeAppId = "a1";
    navQ.data = {
      id: "n1",
      name: "App nav",
      scope: "app",
      groups: [
        {
          label: "Reports Hub",
          items: [
            { label: "Pipeline", type: "entity", target: "deals" },
            { label: "Docs", type: "external", target: "https://example.com/docs" },
          ],
        },
      ],
    };
    render(<SidebarNav />);
    expect(screen.getByText("Reports Hub")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Pipeline" })).toHaveAttribute("href", "/e/deals");
    const ext = screen.getByRole("link", { name: "Docs" });
    expect(ext).toHaveAttribute("href", "https://example.com/docs");
    expect(ext).toHaveAttribute("target", "_blank");
    // metadata nav is replaced
    expect(screen.queryByText("CRM Module")).not.toBeInTheDocument();
  });
});
