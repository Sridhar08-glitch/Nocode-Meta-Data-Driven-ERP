import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({ apiGet: vi.fn(() => Promise.resolve({ results: [] })), apiSend: vi.fn(() => Promise.resolve({})) }));
import { apiGet, apiSend } from "@/lib/api/request";
import { emailTemplatesApi } from "./api";

beforeEach(() => { vi.mocked(apiGet).mockClear(); vi.mocked(apiSend).mockClear(); });

describe("emailTemplatesApi", () => {
  it("CRUDs + renders + test-sends", () => {
    emailTemplatesApi.list();
    emailTemplatesApi.create({ name: "Welcome", slug: "welcome", locale: "fr-FR", body_html: "<p>hi</p>" });
    emailTemplatesApi.render("t1", { name: "Ada" });
    emailTemplatesApi.testSend("t1", "a@b.com", { name: "Ada" });
    expect(apiGet).toHaveBeenCalledWith("/api/v1/templates/email/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/templates/email/", "POST", expect.objectContaining({ locale: "fr-FR" }));
    expect(apiSend).toHaveBeenCalledWith("/api/v1/templates/email/t1/render/", "POST", { context: { name: "Ada" } });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/templates/email/t1/test-send/", "POST", { to_email: "a@b.com", context: { name: "Ada" } });
  });
});
