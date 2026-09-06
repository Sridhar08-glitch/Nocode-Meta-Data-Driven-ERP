import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { InstalledPlugin, Plugin, PluginDetail } from "@/lib/marketplace/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const browseQ = { isLoading: false, isError: false, data: { results: [] as Plugin[] } };
const detailQ = { isLoading: false, data: undefined as PluginDetail | undefined };
const installedQ = { isLoading: false, isError: false, data: { results: [] as InstalledPlugin[] } };
const install = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const uninstall = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const upgrade = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const rollback = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
vi.mock("@/lib/marketplace/hooks", () => ({
  usePlugins: () => browseQ,
  usePluginDetail: () => detailQ,
  useInstalledPlugins: () => installedQ,
  useInstallPlugin: () => install,
  useUninstallPlugin: () => uninstall,
  useUpgradePlugin: () => upgrade,
  useRollbackPlugin: () => rollback,
}));

import { MarketplaceInstalled, MarketplaceStore } from "./marketplace-store";

const plugin = (over: Partial<Plugin> = {}): Plugin => ({
  id: "p1", slug: "crm", name: "CRM Pack", tagline: "Leads & deals", description: "Full CRM",
  category: "sales", status: "published", publisher_name: "Nexus", is_official: true,
  latest_version: "1.2.0", install_count: 5, icon_url: "", ...over,
});
const installed = (over: Partial<InstalledPlugin> = {}): InstalledPlugin => ({
  id: "i1", plugin_id: "p1", plugin_version_id: "v1", plugin_slug: "crm", installed_version: "1.0.0",
  status: "active", created_entity_ids: ["e1"], created_workflow_ids: [], created_rule_ids: [],
  created_report_ids: [], error_message: "", ...over,
});

beforeEach(() => {
  browseQ.data = { results: [] };
  installedQ.data = { results: [] };
  detailQ.data = undefined;
  for (const m of [install, uninstall, upgrade, rollback]) m.mutateAsync.mockClear();
  vi.clearAllMocks();
});

describe("MarketplaceStore", () => {
  it("opens a plugin and installs the chosen version", async () => {
    browseQ.data = { results: [plugin()] };
    detailQ.data = { ...plugin(), versions: [{ id: "v12", plugin_id: "p1", version: "1.2.0", changelog: "latest", is_published: true, created_at: "" }] };
    render(<MarketplaceStore />);
    fireEvent.click(screen.getByRole("button", { name: "Open CRM Pack" }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Install" }));
    await waitFor(() => expect(install.mutateAsync).toHaveBeenCalledWith({ pluginId: "p1", versionId: "v12" }));
  });

  it("rolls back an installed plugin", async () => {
    installedQ.data = { results: [installed()] };
    render(<MarketplaceInstalled onUpgrade={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Rollback crm" }));
    await waitFor(() => expect(rollback.mutateAsync).toHaveBeenCalledWith("i1"));
  });

  it("uninstalls (hard) after confirmation", async () => {
    installedQ.data = { results: [installed()] };
    render(<MarketplaceInstalled onUpgrade={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Uninstall crm" }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Hard uninstall" }));
    await waitFor(() => expect(uninstall.mutateAsync).toHaveBeenCalledWith({ id: "i1", hard: true }));
  });
});
