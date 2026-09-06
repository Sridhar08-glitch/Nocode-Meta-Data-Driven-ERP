import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({ apiGet: vi.fn(() => Promise.resolve({})), apiSend: vi.fn(() => Promise.resolve({})) }));
import { apiGet, apiSend } from "@/lib/api/request";
import { isRtlLocale, localizationApi } from "./api";

beforeEach(() => {
  vi.mocked(apiGet).mockClear();
  vi.mocked(apiSend).mockClear();
});

describe("isRtlLocale", () => {
  it("flags Arabic/Hebrew/Persian as RTL and others LTR", () => {
    expect(isRtlLocale("ar-EG")).toBe(true);
    expect(isRtlLocale("he-IL")).toBe(true);
    expect(isRtlLocale("fa")).toBe(true);
    expect(isRtlLocale("en-US")).toBe(false);
    expect(isRtlLocale("fr-FR")).toBe(false);
  });
});

describe("localizationApi", () => {
  it("reads/updates locale and fetches the flat translations map", () => {
    localizationApi.getLocale();
    localizationApi.updateLocale({ default_locale: "fr-FR" });
    localizationApi.translations("fr-FR", "ui");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/localization/locale/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/localization/locale/", "PATCH", { default_locale: "fr-FR" });
    expect(apiGet).toHaveBeenCalledWith("/api/v1/localization/translations/?locale=fr-FR&namespace=ui");
  });
});
