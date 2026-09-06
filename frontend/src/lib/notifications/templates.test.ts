import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({ apiGet: vi.fn(() => Promise.resolve([])), apiSend: vi.fn(() => Promise.resolve({})) }));
import { apiGet, apiSend } from "@/lib/api/request";
import { preferencesApi, renderPreview, templatesApi, templateVariables } from "./api";

beforeEach(() => {
  vi.mocked(apiGet).mockClear();
  vi.mocked(apiSend).mockClear();
});

describe("template helpers", () => {
  it("extracts ${var} placeholders from subject + body", () => {
    expect(templateVariables("Hi ${actor_name}", "Welcome to ${workspace_name}, ${actor_name}").sort()).toEqual([
      "actor_name",
      "workspace_name",
    ]);
  });
  it("renders a preview, leaving unknown vars intact", () => {
    expect(renderPreview("Hi ${name}, ${missing}", { name: "Ada" })).toBe("Hi Ada, ${missing}");
  });
});

describe("templatesApi", () => {
  it("CRUDs templates and test-sends with context", () => {
    templatesApi.list();
    templatesApi.create({ slug: "welcome", name: "Welcome", channel: "email", subject_template: "Hi", body_template: "Hello ${name}" });
    templatesApi.update("t1", { name: "Welcome v2" });
    templatesApi.remove("t1");
    templatesApi.test("t1", { name: "Ada" });
    expect(apiGet).toHaveBeenCalledWith("/api/v1/notifications/templates/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/notifications/templates/", "POST", expect.objectContaining({ slug: "welcome", channel: "email" }));
    expect(apiSend).toHaveBeenCalledWith("/api/v1/notifications/templates/t1/", "PATCH", { name: "Welcome v2" });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/notifications/templates/t1/", "DELETE");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/notifications/templates/t1/test/", "POST", { context: { name: "Ada" } });
  });
});

describe("preferencesApi", () => {
  it("lists + upserts a preference via PUT", () => {
    preferencesApi.list();
    preferencesApi.set("record_assigned", "email", false);
    expect(apiGet).toHaveBeenCalledWith("/api/v1/notifications/preferences/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/notifications/preferences/", "PUT", {
      event_type: "record_assigned",
      channel: "email",
      enabled: false,
    });
  });
});
