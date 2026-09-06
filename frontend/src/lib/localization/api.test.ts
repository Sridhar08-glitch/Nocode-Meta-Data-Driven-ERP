import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({ apiGet: vi.fn(() => Promise.resolve({})), apiSend: vi.fn(() => Promise.resolve({})) }));
import { apiGet, apiSend } from "@/lib/api/request";
import { localizationApi } from "./api";

beforeEach(() => {
  vi.mocked(apiGet).mockClear();
  vi.mocked(apiSend).mockClear();
});

describe("localizationApi", () => {
  it("reads/writes locale + entity labels", () => {
    localizationApi.getLocale();
    localizationApi.setLocale({ default_locale: "fr-FR" });
    localizationApi.listEntityLabels();
    localizationApi.createEntityLabel({ entity_id: "e1", locale: "fr-FR", singular: "Prospect", plural: "Prospects" });
    localizationApi.deleteEntityLabel("l1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/localization/locale/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/localization/locale/", "PATCH", { default_locale: "fr-FR" });
    expect(apiGet).toHaveBeenCalledWith("/api/v1/localization/entity-labels/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/localization/entity-labels/", "POST", expect.objectContaining({ entity_id: "e1" }));
    expect(apiSend).toHaveBeenCalledWith("/api/v1/localization/entity-labels/l1/", "DELETE");
  });
});
