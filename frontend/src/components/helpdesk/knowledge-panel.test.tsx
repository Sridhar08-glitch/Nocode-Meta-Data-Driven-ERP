import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { KnowledgeArticleHit } from "@/lib/helpdesk/api";

const recQ = { isLoading: false, isError: false, data: null as KnowledgeArticleHit[] | null };
const recommendSpy = vi.fn();

vi.mock("@/lib/helpdesk/hooks", () => ({
  useKnowledgeRecommend: (params: { category?: string; q?: string }, active: boolean) => {
    recommendSpy(params, active);
    return recQ;
  },
}));

import { KnowledgePanel, Results } from "./knowledge-panel";

beforeEach(() => {
  recQ.data = null;
  recQ.isLoading = false;
  recQ.isError = false;
  vi.clearAllMocks();
});

describe("KnowledgePanel", () => {
  it("prompts for input before searching", () => {
    render(<KnowledgePanel />);
    expect(screen.getByText("Enter a category or keywords")).toBeInTheDocument();
  });

  it("recommends articles for the entered category + keywords", () => {
    recQ.data = [];
    render(<KnowledgePanel />);
    fireEvent.change(screen.getByLabelText("Category"), { target: { value: "billing" } });
    fireEvent.change(screen.getByLabelText("Keywords"), { target: { value: "invoice refund" } });
    fireEvent.click(screen.getByRole("button", { name: "Recommend" }));
    expect(recommendSpy).toHaveBeenCalledWith({ category: "billing", q: "invoice refund" }, true);
  });
});

describe("Results", () => {
  it("lists recommended articles with their score", () => {
    recQ.data = [
      { id: "a1", title: "How to reset your password", category: "auth", score: 9 },
      { id: "a2", title: "Billing FAQ", category: "billing", score: 4 },
    ];
    render(<Results params={{ q: "password" }} />);
    expect(screen.getByText("How to reset your password")).toBeInTheDocument();
    expect(screen.getByText("Billing FAQ")).toBeInTheDocument();
    expect(screen.getByText("9")).toBeInTheDocument();
    expect(screen.getByText("2 recommended articles")).toBeInTheDocument();
  });

  it("shows an empty state when nothing matches", () => {
    recQ.data = [];
    render(<Results params={{ q: "zzz" }} />);
    expect(screen.getByText("No matching articles")).toBeInTheDocument();
  });
});
