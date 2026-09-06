import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Application } from "@/lib/studio/api";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const setActiveApp = vi.fn();
const active = { activeAppId: null as string | null };
vi.mock("@/lib/studio/active-app", () => ({ useActiveApp: () => ({ activeAppId: active.activeAppId, setActiveApp }) }));

const switcherQ = { data: { results: [] as Application[], count: 0 } };
vi.mock("@/lib/studio/hooks", () => ({ useAppSwitcher: () => switcherQ }));

import { AppSwitcher } from "./app-switcher";

const app = (id: string, name: string): Application => ({
  id, name, slug: name.toLowerCase(), description: "", icon: "", color: "",
  included_entity_ids: [], navigation_id: null, home_layout_id: null, role_ids: [],
  theme_overrides: {}, order: 0, is_published: true, is_active: true, created_by: null,
  created_at: "", updated_at: "",
});

beforeEach(() => {
  active.activeAppId = null;
  switcherQ.data = { results: [], count: 0 };
  push.mockClear();
  setActiveApp.mockClear();
});

describe("AppSwitcher", () => {
  it("renders nothing when no apps are published", () => {
    const { container } = render(<AppSwitcher />);
    expect(container).toBeEmptyDOMElement();
  });

  it("activates an app and navigates home", async () => {
    switcherQ.data = { results: [app("a1", "Sales"), app("a2", "Support")], count: 2 };
    render(<AppSwitcher />);
    const trigger = screen.getByRole("button", { name: "Switch application" });
    trigger.focus();
    fireEvent.keyDown(trigger, { key: "Enter" });
    const items = await screen.findAllByRole("menuitem");
    fireEvent.click(items.find((el) => el.textContent?.includes("Support"))!);
    expect(setActiveApp).toHaveBeenCalledWith("a2");
    expect(push).toHaveBeenCalledWith("/home");
  });

  it("can reset to all apps", async () => {
    active.activeAppId = "a1";
    switcherQ.data = { results: [app("a1", "Sales")], count: 1 };
    render(<AppSwitcher />);
    const trigger = screen.getByRole("button", { name: "Switch application" });
    trigger.focus();
    fireEvent.keyDown(trigger, { key: "Enter" });
    const items = await screen.findAllByRole("menuitem");
    fireEvent.click(items.find((el) => el.textContent?.includes("All apps"))!);
    expect(setActiveApp).toHaveBeenCalledWith(null);
  });
});
