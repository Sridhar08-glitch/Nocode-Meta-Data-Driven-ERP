import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { EntityLabel, WorkspaceLocale } from "@/lib/localization/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));
vi.mock("@/lib/metadata/hooks", () => ({ useEntities: () => ({ data: [{ id: "e1", name: "Leads", slug: "leads" }] }) }));

const localeQ = {
  isLoading: false, isError: false,
  data: { default_locale: "en-US", default_timezone: "UTC", default_currency: "USD", enabled_locales: ["en-US"] } as WorkspaceLocale,
};
const labelsQ = { data: { results: [] as EntityLabel[], count: 0 } };
const setLocale = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const createLabel = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const delLabel = { mutateAsync: vi.fn(() => Promise.resolve(null)), isPending: false };
vi.mock("@/lib/localization/hooks", () => ({
  useLocale: () => localeQ,
  useSetLocale: () => setLocale,
  useEntityLabels: () => labelsQ,
  useCreateEntityLabel: () => createLabel,
  useDeleteEntityLabel: () => delLabel,
}));

import { LocalizationSettings } from "./localization-settings";

beforeEach(() => {
  labelsQ.data = { results: [], count: 0 };
  setLocale.mutateAsync.mockClear();
  createLabel.mutateAsync.mockClear();
  vi.clearAllMocks();
});

describe("LocalizationSettings", () => {
  it("saves locale defaults with parsed enabled_locales", async () => {
    render(<LocalizationSettings />);
    expect(screen.getByLabelText("Default locale")).toHaveValue("en-US");
    fireEvent.change(screen.getByLabelText("Enabled locales (comma-separated)"), { target: { value: "en-US, fr-FR" } });
    fireEvent.change(screen.getByLabelText("Currency"), { target: { value: "eur" } });
    fireEvent.click(screen.getByRole("button", { name: "Save defaults" }));
    await waitFor(() => expect(setLocale.mutateAsync).toHaveBeenCalled());
    expect(setLocale.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ default_currency: "EUR", enabled_locales: ["en-US", "fr-FR"] }),
    );
  });

  it("adds an entity label", async () => {
    render(<LocalizationSettings />);
    fireEvent.click(screen.getByRole("combobox", { name: "Entity" }));
    fireEvent.click(await screen.findByRole("option", { name: "Leads" }));
    fireEvent.change(screen.getByLabelText("Locale"), { target: { value: "fr-FR" } });
    fireEvent.change(screen.getByLabelText("Singular"), { target: { value: "Prospect" } });
    fireEvent.change(screen.getByLabelText("Plural"), { target: { value: "Prospects" } });
    fireEvent.click(screen.getByRole("button", { name: "Add label" }));
    await waitFor(() => expect(createLabel.mutateAsync).toHaveBeenCalled());
    expect(createLabel.mutateAsync).toHaveBeenCalledWith({ entity_id: "e1", locale: "fr-FR", singular: "Prospect", plural: "Prospects" });
  });

  it("filters entity labels by search", () => {
    labelsQ.data = {
      results: [
        { id: "l1", entity_id: "e1", field_id: null, locale: "fr-FR", singular: "Prospect", plural: "Prospects" },
        { id: "l2", entity_id: "e1", field_id: null, locale: "de-DE", singular: "Kontakt", plural: "Kontakte" },
      ],
      count: 2,
    };
    render(<LocalizationSettings />);
    expect(screen.getByText("Prospect / Prospects")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Search translations"), { target: { value: "kontakt" } });
    expect(screen.queryByText("Prospect / Prospects")).not.toBeInTheDocument();
    expect(screen.getByText("Kontakt / Kontakte")).toBeInTheDocument();
  });

  it("restores locale defaults after confirmation", () => {
    render(<LocalizationSettings />);
    fireEvent.change(screen.getByLabelText("Currency"), { target: { value: "JPY" } });
    fireEvent.click(screen.getByRole("button", { name: "Restore defaults" }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Restore defaults" }));
    expect(screen.getByLabelText("Currency")).toHaveValue("USD");
  });
});
