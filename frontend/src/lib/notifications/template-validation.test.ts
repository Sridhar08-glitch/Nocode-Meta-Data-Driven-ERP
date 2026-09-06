import { describe, expect, it } from "vitest";

import { extractVariables, validateTemplate } from "./template-validation";

describe("extractVariables", () => {
  it("collects deduped ${name} refs across parts", () => {
    expect(extractVariables("Hi ${actor_name}", "${actor_name} — ${workspace_name}").sort()).toEqual([
      "actor_name",
      "workspace_name",
    ]);
  });
});

describe("validateTemplate", () => {
  it("passes a template using only known variables", () => {
    expect(validateTemplate(["Hi ${customer_name}", "Ticket ${ticket_id}"]).errors).toEqual([]);
  });

  it("flags an unknown variable (typo)", () => {
    const v = validateTemplate(["${custmer_name}"]);
    expect(v.unknown).toEqual(["custmer_name"]);
    expect(v.errors).toContain("Unknown variable: custmer_name");
  });

  it("flags an unterminated / unmatched-brace variable", () => {
    const v = validateTemplate(["Hello ${customer_name"]);
    expect(v.malformed).toContain("${customer_name");
    expect(v.errors.some((e) => /Malformed variable/.test(e))).toBe(true);
  });

  it("flags invalid syntax inside braces", () => {
    expect(validateTemplate(["${na me}"]).malformed).toContain("${na me}");
    expect(validateTemplate(["${ }"]).malformed).toContain("${ }");
  });

  it("skips the unknown check when no metadata is supplied", () => {
    expect(validateTemplate(["${anything_goes}"], []).errors).toEqual([]);
  });
});
