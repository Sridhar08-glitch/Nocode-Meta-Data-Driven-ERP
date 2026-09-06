import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { BusinessRule } from "@/lib/rules/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));
vi.mock("@/lib/metadata/hooks", () => ({ useEntities: () => ({ data: [{ id: "e1", name: "Deals", slug: "deals" }] }) }));

const rulesQ = { isLoading: false, isError: false, data: { results: [] as BusinessRule[], count: 0 } };
const create = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const del = { mutateAsync: vi.fn(() => Promise.resolve(null)), isPending: false };
vi.mock("@/lib/rules/hooks", () => ({ useRules: () => rulesQ, useCreateRule: () => create, useDeleteRule: () => del }));

import { RuleBuilder } from "./rule-builder";

beforeEach(() => {
  rulesQ.data = { results: [], count: 0 };
  create.mutateAsync.mockClear().mockResolvedValue({});
  del.mutateAsync.mockClear().mockResolvedValue(null);
  vi.clearAllMocks();
});

describe("RuleBuilder", () => {
  it("creates a rule with entity, trigger, condition and a set_field action", async () => {
    render(<RuleBuilder />);
    fireEvent.click(screen.getAllByRole("button", { name: "New rule" })[0]);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Auto review" } });
    fireEvent.click(screen.getByRole("combobox", { name: "Entity" }));
    fireEvent.click(await screen.findByRole("option", { name: "Deals" }));
    fireEvent.change(screen.getByLabelText(/Condition/), { target: { value: "amount > 1000" } });
    fireEvent.change(screen.getByLabelText("Action 1 field"), { target: { value: "stage" } });
    fireEvent.change(screen.getByLabelText("Action 1 value"), { target: { value: "review" } });
    fireEvent.click(screen.getByRole("button", { name: "Create rule" }));
    await waitFor(() => expect(create.mutateAsync).toHaveBeenCalled());
    expect(create.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "Auto review",
        slug: "auto_review",
        entity_id: "e1",
        trigger_on: "before_update",
        condition_nql: "amount > 1000",
        actions: [{ type: "set_field", field: "stage", value: "review" }],
      }),
    );
  });

  it("strips config when the action is block_save", async () => {
    render(<RuleBuilder />);
    fireEvent.click(screen.getAllByRole("button", { name: "New rule" })[0]);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Guard" } });
    fireEvent.click(screen.getByRole("combobox", { name: "Entity" }));
    fireEvent.click(await screen.findByRole("option", { name: "Deals" }));
    fireEvent.click(screen.getByRole("combobox", { name: "Action 1 type" }));
    fireEvent.click(await screen.findByRole("option", { name: "Block the save" }));
    fireEvent.click(screen.getByRole("button", { name: "Create rule" }));
    await waitFor(() =>
      expect(create.mutateAsync).toHaveBeenCalledWith(expect.objectContaining({ actions: [{ type: "block_save" }] })),
    );
  });

  it("deletes a rule", async () => {
    rulesQ.data = { results: [{ id: "r1", name: "Old", trigger_on: "after_create", actions: [], priority: 100, is_active: true } as unknown as BusinessRule], count: 1 };
    render(<RuleBuilder />);
    fireEvent.click(screen.getByRole("button", { name: "Remove rule Old" }));
    await waitFor(() => expect(del.mutateAsync).toHaveBeenCalledWith("r1"));
  });
});
