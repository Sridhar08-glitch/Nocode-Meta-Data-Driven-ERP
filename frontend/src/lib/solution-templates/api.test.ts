import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({ apiGet: vi.fn(() => Promise.resolve({})), apiSend: vi.fn(() => Promise.resolve({})) }));
import { apiGet, apiSend } from "@/lib/api/request";
import { solutionTemplatesApi } from "./api";

beforeEach(() => {
  vi.mocked(apiGet).mockClear();
  vi.mocked(apiSend).mockClear();
});

describe("solutionTemplatesApi", () => {
  it("browses, previews the library, previews a template, installs, lists installed, and uninstalls", () => {
    solutionTemplatesApi.list();
    solutionTemplatesApi.list({ search: "crm", category: "sales" });
    solutionTemplatesApi.library();
    solutionTemplatesApi.preview("t1");
    solutionTemplatesApi.install("t1");
    solutionTemplatesApi.installed();
    solutionTemplatesApi.uninstall("i1");
    solutionTemplatesApi.uninstall("i2", true);

    expect(apiGet).toHaveBeenCalledWith("/api/v1/solution-templates/");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/solution-templates/?category=sales&search=crm");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/solution-templates/library/");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/solution-templates/t1/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/solution-templates/t1/install/", "POST");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/solution-templates/installed/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/solution-templates/installed/i1/uninstall/", "POST", { hard: false });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/solution-templates/installed/i2/uninstall/", "POST", { hard: true });
  });

  it("drives the create-solution wizard (options/resolve/preview/create)", () => {
    const selection = {
      solution_type: "crm",
      industry: "retail",
      business_objects: ["customer", "contact"],
      workflows: ["approval"],
      roles: ["administrator"],
      dashboards: ["executive"],
      reports: ["summary"],
      config: {
        solution_name: "Sales CRM",
        application_name: "Sales CRM",
        description: "",
        icon: "Users",
        color: "#2563eb",
      },
    };
    solutionTemplatesApi.wizardOptions();
    solutionTemplatesApi.resolveDependencies(["customer", "contact"]);
    solutionTemplatesApi.previewSolution(selection);
    solutionTemplatesApi.createSolution(selection);

    expect(apiGet).toHaveBeenCalledWith("/api/v1/solution-templates/wizard/options/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/solution-templates/wizard/resolve/", "POST", {
      business_objects: ["customer", "contact"],
    });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/solution-templates/wizard/preview/", "POST", selection);
    expect(apiSend).toHaveBeenCalledWith("/api/v1/solution-templates/wizard/create/", "POST", selection);
  });
});
