import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { LineageGraph, LineageNode } from "@/lib/lineage/api";

const node = (id: string, name: string, type = "entity"): LineageNode => ({
  id, node_type: type, object_id: `${id}-obj`, object_slug: name.toLowerCase(), display_name: name,
});

const nodesQ = { isLoading: false, isError: false, data: { results: [node("n1", "Leads")], count: 1 } };
const upQ = { isLoading: false, isError: false, data: undefined as LineageGraph | undefined };
const downQ = { isLoading: false, isError: false, data: undefined as LineageGraph | undefined };
vi.mock("@/lib/lineage/hooks", () => ({
  useLineageNodes: () => nodesQ,
  useUpstream: () => upQ,
  useDownstream: () => downQ,
}));

import { LineageGraphPanel } from "./lineage-graph";

beforeEach(() => {
  upQ.data = undefined;
  downQ.data = undefined;
});

describe("LineageGraphPanel", () => {
  it("selects a node and shows upstream + downstream nodes", () => {
    upQ.data = { nodes: [node("n1", "Leads"), node("imp1", "Import job", "import_job")], edges: [] };
    downQ.data = { nodes: [node("n1", "Leads"), node("rep1", "Leads report", "report")], edges: [] };
    render(<LineageGraphPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Select Leads" }));
    // selected node panel + upstream/downstream (excluding the selected node itself)
    expect(within(screen.getByLabelText("upstream nodes")).getByText("Import job")).toBeInTheDocument();
    expect(within(screen.getByLabelText("downstream nodes")).getByText("Leads report")).toBeInTheDocument();
    // the selected node is not duplicated into either column
    expect(within(screen.getByLabelText("upstream nodes")).queryByText("Leads")).not.toBeInTheDocument();
  });

  it("prompts to pick a node before selection", () => {
    render(<LineageGraphPanel />);
    expect(screen.getByText("Select a node")).toBeInTheDocument();
  });
});
