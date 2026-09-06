import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({ apiGet: vi.fn(() => Promise.resolve({})), apiSend: vi.fn(() => Promise.resolve({})) }));
import { apiGet, apiSend } from "@/lib/api/request";
import { brandingApi } from "./api";

beforeEach(() => {
  vi.mocked(apiGet).mockClear();
  vi.mocked(apiSend).mockClear();
});

describe("brandingApi", () => {
  it("reads/writes branding + SMTP", () => {
    brandingApi.get();
    brandingApi.update({ app_name: "Acme" });
    brandingApi.getSmtp();
    brandingApi.saveSmtp({ host: "smtp.acme.com", port: 587, username: "u", password: "secret", from_email: "no@acme.com" });
    brandingApi.testSmtp();
    expect(apiGet).toHaveBeenCalledWith("/api/v1/branding/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/branding/", "PATCH", { app_name: "Acme" });
    expect(apiGet).toHaveBeenCalledWith("/api/v1/branding/smtp/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/branding/smtp/", "PATCH", expect.objectContaining({ host: "smtp.acme.com" }));
    expect(apiSend).toHaveBeenCalledWith("/api/v1/branding/smtp/test/", "POST");
  });
});
