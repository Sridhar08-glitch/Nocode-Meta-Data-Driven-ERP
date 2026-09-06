import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Tag } from "@/lib/tagging/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const recordTags = { data: { results: [] as Tag[], count: 0 } };
const allTags = { data: { results: [] as Tag[], count: 0 } };
const attach = { mutateAsync: vi.fn(() => Promise.resolve({ detail: "attached" })), isPending: false };
const detach = { mutateAsync: vi.fn(() => Promise.resolve({ removed: 1 })), isPending: false };
vi.mock("@/lib/tagging/hooks", () => ({
  useRecordTags: () => recordTags,
  useTags: () => allTags,
  useAttachTag: () => attach,
  useDetachTag: () => detach,
}));

import { RecordTags } from "./record-tags";

const tag = (id: string, name: string): Tag => ({ id, name, slug: name.toLowerCase(), color: "#f00", group: "" });

beforeEach(() => {
  recordTags.data = { results: [], count: 0 };
  allTags.data = { results: [], count: 0 };
  attach.mutateAsync.mockClear();
  detach.mutateAsync.mockClear();
  vi.clearAllMocks();
});

describe("RecordTags", () => {
  it("attaches a tag chosen from the available (not-yet-applied) tags", async () => {
    recordTags.data = { results: [tag("t1", "VIP")], count: 1 };
    allTags.data = { results: [tag("t1", "VIP"), tag("t2", "Hot")], count: 2 };
    render(<RecordTags entitySlug="deals" recordId="r1" />);
    fireEvent.click(screen.getByRole("button", { name: "+ Tag" }));
    fireEvent.click(screen.getByRole("combobox", { name: "Add tag" }));
    // VIP is already applied → only Hot is offered
    expect(screen.queryByRole("option", { name: "VIP" })).not.toBeInTheDocument();
    fireEvent.click(await screen.findByRole("option", { name: "Hot" }));
    await waitFor(() => expect(attach.mutateAsync).toHaveBeenCalledWith("t2"));
  });

  it("detaches an applied tag", async () => {
    recordTags.data = { results: [tag("t1", "VIP")], count: 1 };
    render(<RecordTags entitySlug="deals" recordId="r1" />);
    fireEvent.click(screen.getByRole("button", { name: "Remove tag VIP" }));
    await waitFor(() => expect(detach.mutateAsync).toHaveBeenCalledWith("t1"));
  });
});
