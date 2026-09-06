import { describe, expect, it } from "vitest";

import { queryKeys } from "./keys";

describe("queryKeys", () => {
  const scope = { tenant: "acme", schemaVersion: 3 };

  it("namespaces by tenant + schemaVersion", () => {
    expect(queryKeys.metadata.entities(scope)).toEqual(["meta", "acme", 3, "entities"]);
    expect(queryKeys.records.detail(scope, "lead", "id-1")).toEqual([
      "data",
      "acme",
      3,
      "lead",
      "detail",
      "id-1",
    ]);
  });

  it("different tenants produce different keys (no cross-tenant bleed)", () => {
    const a = queryKeys.records.list({ tenant: "a", schemaVersion: 1 }, "lead");
    const b = queryKeys.records.list({ tenant: "b", schemaVersion: 1 }, "lead");
    expect(a).not.toEqual(b);
  });

  it("a schemaVersion change invalidates metadata keys", () => {
    const v1 = queryKeys.metadata.entity({ tenant: "acme", schemaVersion: 1 }, "lead");
    const v2 = queryKeys.metadata.entity({ tenant: "acme", schemaVersion: 2 }, "lead");
    expect(v1).not.toEqual(v2);
  });

  it("includes list params in the key", () => {
    const key = queryKeys.records.list(scope, "lead", { filter: { status: "open" } });
    expect(key[5]).toEqual({ filter: { status: "open" } });
  });

  it("covers form-schema, tenant-context and notification keys", () => {
    expect(queryKeys.metadata.formSchema(scope, "lead")).toEqual([
      "meta",
      "acme",
      3,
      "form-schema",
      "lead",
    ]);
    expect(queryKeys.tenantContext("acme")).toEqual(["tenant", "acme", "context"]);
    expect(queryKeys.notifications.unreadCount("acme")).toEqual([
      "notifications",
      "acme",
      "unread-count",
    ]);
    expect(queryKeys.notifications.list("acme")).toEqual(["notifications", "acme", "list"]);
  });

  it("defaults schemaVersion placeholder when omitted", () => {
    expect(queryKeys.metadata.entities({ tenant: "acme" })[2]).toBe("v");
  });
});
