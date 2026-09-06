import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AnalyzeResult } from "@/lib/dependency/api";
import type { ImpactResult } from "@/lib/metadata/builder-api";

import { ImpactWarningDialog } from "./impact-warning-dialog";

function renderDialog(
  result: ImpactResult,
  onConfirm = vi.fn(),
  onCancel = vi.fn(),
  analyze?: AnalyzeResult,
) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <ImpactWarningDialog
        open
        title="Delete field “status”?"
        queryKey={["impact-test", Math.random()]}
        fetcher={() => Promise.resolve(result)}
        analyzeQueryKey={analyze ? ["impact-analyze", Math.random()] : undefined}
        analyzeFetcher={analyze ? () => Promise.resolve(analyze) : undefined}
        onConfirm={onConfirm}
        onCancel={onCancel}
      />
    </QueryClientProvider>,
  );
  return { onConfirm, onCancel };
}

describe("ImpactWarningDialog", () => {
  it("lists dependents and warns when references exist", async () => {
    renderDialog({
      count: 2,
      dependents: [
        { type: "form", name: "Lead form", detail: "Field placed on this form", approximate: false, id: "f1" },
        { type: "rule", name: "Status watcher", detail: "watched", approximate: false, id: "r1" },
      ],
    });
    expect(await screen.findByText(/referenced by 2 configuration object/)).toBeInTheDocument();
    const list = screen.getByLabelText("Impact dependents");
    expect(list).toHaveTextContent("Lead form");
    expect(list).toHaveTextContent("Status watcher");
  });

  it("says it's safe when there are no references, and confirms", async () => {
    const { onConfirm } = renderDialog({ count: 0, dependents: [] });
    expect(await screen.findByText(/No known references/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Delete anyway" }));
    await waitFor(() => expect(onConfirm).toHaveBeenCalled());
  });

  it("marks approximate matches", async () => {
    renderDialog({
      count: 1,
      dependents: [{ type: "report", name: "Pipeline", detail: "Referenced in report query", approximate: true, id: "rep1" }],
    });
    expect(await screen.findByText(/possible match/)).toBeInTheDocument();
  });

  it("enriches with risk + used-by when an analyze fetcher is provided", async () => {
    renderDialog(
      { count: 0, dependents: [] },
      vi.fn(),
      vi.fn(),
      {
        object_type: "field",
        object_id: "status",
        name: "Status",
        used_by_count: 4,
        by_type: { report: 3, workflow: 1 },
        dependents: [],
        risk: { level: "critical", count: 4, exact: 4, has_automation: true, score: 0.9 },
      },
    );
    const panel = await screen.findByLabelText("Risk analysis");
    expect(panel).toHaveTextContent(/critical risk/);
    expect(panel).toHaveTextContent("Used by 4 objects");
    expect(panel).toHaveTextContent("Report: 3");
  });

  it("works without an analyze fetcher (no risk panel rendered)", async () => {
    renderDialog({ count: 0, dependents: [] });
    expect(await screen.findByText(/No known references/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Risk analysis")).not.toBeInTheDocument();
  });
});
