import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({
  apiGet: vi.fn(() => Promise.resolve({})),
  apiSend: vi.fn(() => Promise.resolve({})),
}));

import { apiGet, apiSend } from "@/lib/api/request";

import { builderApi } from "./builder-api";

beforeEach(() => {
  vi.mocked(apiGet).mockClear();
  vi.mocked(apiSend).mockClear();
});

describe("builderApi entities", () => {
  it("createEntity POSTs the collection", () => {
    builderApi.createEntity({ slug: "lead", name: "Lead", plural_name: "Leads" });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/metadata/entities/", "POST", {
      slug: "lead",
      name: "Lead",
      plural_name: "Leads",
    });
  });
  it("updateEntity PATCHes by slug", () => {
    builderApi.updateEntity("lead", { name: "Leads" });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/metadata/entities/lead/", "PATCH", {
      name: "Leads",
    });
  });
  it("deleteEntity DELETEs by slug", () => {
    builderApi.deleteEntity("lead");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/metadata/entities/lead/", "DELETE");
  });
});

describe("builderApi fields", () => {
  it("listFields GETs the collection", () => {
    builderApi.listFields("lead");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/metadata/entities/lead/fields/");
  });
  it("createField POSTs", () => {
    builderApi.createField("lead", { slug: "name", name: "Name", field_type: "text" });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/metadata/entities/lead/fields/", "POST", {
      slug: "name",
      name: "Name",
      field_type: "text",
    });
  });
  it("updateField PATCHes by field slug", () => {
    builderApi.updateField("lead", "name", { is_required: true });
    expect(apiSend).toHaveBeenCalledWith(
      "/api/v1/metadata/entities/lead/fields/name/",
      "PATCH",
      { is_required: true },
    );
  });
  it("deleteField DELETEs by field slug", () => {
    builderApi.deleteField("lead", "name");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/metadata/entities/lead/fields/name/", "DELETE");
  });
  it("fetches entity + field impact", () => {
    builderApi.entityImpact("lead");
    builderApi.fieldImpact("lead", "status");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/metadata/entities/lead/impact/");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/metadata/entities/lead/fields/status/impact/");
  });
  it("promote/demote POST the field_slug body", () => {
    builderApi.promoteField("lead", "name");
    builderApi.demoteField("lead", "name");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/metadata/entities/lead/promote-field/", "POST", {
      field_slug: "name",
    });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/metadata/entities/lead/demote-field/", "POST", {
      field_slug: "name",
    });
  });
});

describe("builderApi schema versions + modules", () => {
  it("schemaVersions GETs, rollback POSTs the version path", () => {
    builderApi.schemaVersions("lead");
    builderApi.rollbackSchema("lead", 3);
    expect(apiGet).toHaveBeenCalledWith("/api/v1/metadata/entities/lead/schema-versions/");
    expect(apiSend).toHaveBeenCalledWith(
      "/api/v1/metadata/entities/lead/schema-versions/3/rollback/",
      "POST",
    );
  });
  it("createModule POSTs", () => {
    builderApi.createModule({ name: "Sales" });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/metadata/modules/", "POST", { name: "Sales" });
  });
  it("updateModule PATCHes / deleteModule DELETEs by id", () => {
    builderApi.updateModule("m1", { name: "CRM" });
    builderApi.deleteModule("m1");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/metadata/modules/m1/", "PATCH", { name: "CRM" });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/metadata/modules/m1/", "DELETE");
  });
});

describe("builderApi forms", () => {
  it("list/get/create/update/delete hit the form paths", () => {
    builderApi.listForms("lead");
    builderApi.getForm("lead", "f1");
    builderApi.createForm("lead", { name: "Intake" });
    builderApi.updateForm("lead", "f1", { name: "Edit" });
    builderApi.deleteForm("lead", "f1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/metadata/entities/lead/forms/");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/metadata/entities/lead/forms/f1/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/metadata/entities/lead/forms/", "POST", {
      name: "Intake",
    });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/metadata/entities/lead/forms/f1/", "PATCH", {
      name: "Edit",
    });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/metadata/entities/lead/forms/f1/", "DELETE");
  });
});
