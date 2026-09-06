import { describe, expect, it } from "vitest";

import { isHexColor, validateBrandingForm, validateCustomCss } from "./validation";

describe("isHexColor", () => {
  it("accepts #rgb and #rrggbb", () => {
    expect(isHexColor("#2563eb")).toBe(true);
    expect(isHexColor("#fff")).toBe(true);
  });
  it("rejects malformed values", () => {
    expect(isHexColor("2563eb")).toBe(false);
    expect(isHexColor("#xyzxyz")).toBe(false);
    expect(isHexColor("#12")).toBe(false);
  });
});

describe("validateCustomCss", () => {
  it("passes well-formed CSS", () => {
    expect(validateCustomCss(".a { color: red; }")).toBeNull();
  });
  it("flags unbalanced braces", () => {
    expect(validateCustomCss(".a { color: red;")).toMatch(/never closed/);
    expect(validateCustomCss(".a } ")).toMatch(/no matching/);
  });
  it("flags empty rules", () => {
    expect(validateCustomCss(".a {}")).toMatch(/Empty rule/);
  });
  it("flags oversized payloads", () => {
    expect(validateCustomCss("a".repeat(20_001))).toMatch(/too large/);
  });
});

describe("validateBrandingForm", () => {
  it("is clean for valid input", () => {
    expect(validateBrandingForm({ color_primary: "#2563eb", custom_css: ".x { color: blue; }" }).hasErrors).toBe(false);
  });
  it("reports a bad color and bad css", () => {
    const v = validateBrandingForm({ color_primary: "nope", custom_css: ".x {" });
    expect(v.colors.color_primary).toBeTruthy();
    expect(v.cssError).toBeTruthy();
    expect(v.hasErrors).toBe(true);
  });
  it("treats empty colors as unset (valid)", () => {
    expect(validateBrandingForm({ color_primary: "" }).hasErrors).toBe(false);
  });
});
