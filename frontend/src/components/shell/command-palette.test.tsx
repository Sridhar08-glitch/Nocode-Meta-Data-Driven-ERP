import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { SearchResponse } from "@/lib/search/api";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
const searchState = { data: undefined as SearchResponse | undefined, isLoading: false };
vi.mock("@/lib/search/hooks", () => ({ useSearch: () => searchState }));

import { CommandPalette } from "./command-palette";

function openPalette() {
  fireEvent.keyDown(document, { key: "k", metaKey: true });
}

beforeEach(() => {
  searchState.data = undefined;
  vi.clearAllMocks();
});

describe("CommandPalette", () => {
  it("is closed until Cmd/Ctrl+K, then opens", () => {
    render(<CommandPalette />);
    expect(screen.queryByLabelText("Command palette search")).not.toBeInTheDocument();
    openPalette();
    expect(screen.getByLabelText("Command palette search")).toBeInTheDocument();
  });

  it("opens a record from a search result (the DoD: Cmd+K opens any record)", () => {
    searchState.data = { results: [{ entity_slug: "deals", record_id: "d1", title: "Acme", snippet: "", rank: 1 }], total: 1 };
    render(<CommandPalette />);
    openPalette();
    fireEvent.click(screen.getByRole("button", { name: /Acme/ }));
    expect(push).toHaveBeenCalledWith("/e/deals/d1");
  });

  it("filters the quick-nav commands by the typed query", () => {
    render(<CommandPalette />);
    openPalette();
    fireEvent.change(screen.getByLabelText("Command palette search"), { target: { value: "report" } });
    expect(screen.getByRole("button", { name: "Reports" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Workflows" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reports" }));
    expect(push).toHaveBeenCalledWith("/reports");
  });

  it("toggles closed on a second Cmd+K", () => {
    render(<CommandPalette />);
    openPalette();
    expect(screen.getByLabelText("Command palette search")).toBeInTheDocument();
    openPalette();
    expect(screen.queryByLabelText("Command palette search")).not.toBeInTheDocument();
  });
});
