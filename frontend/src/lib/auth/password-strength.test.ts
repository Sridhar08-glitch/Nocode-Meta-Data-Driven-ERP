import { describe, expect, it } from "vitest";

import { scorePassword } from "./password-strength";

describe("scorePassword", () => {
  it("flags short passwords as failing the min length", () => {
    const r = scorePassword("short");
    expect(r.meetsMinLength).toBe(false);
    expect(r.suggestions).toContain("Use at least 10 characters");
  });

  it("caps all-numeric passwords as very weak", () => {
    const r = scorePassword("1234567890123");
    expect(r.score).toBeLessThanOrEqual(1);
    expect(r.suggestions).toContain("Don't use only numbers");
  });

  it("rates a long mixed password as strong", () => {
    const r = scorePassword("Sup3rStr0ng!pw99");
    expect(r.meetsMinLength).toBe(true);
    expect(r.score).toBeGreaterThanOrEqual(4);
    expect(r.label).toBe("Strong");
  });

  it("returns label within range for an empty password", () => {
    const r = scorePassword("");
    expect(r.score).toBe(0);
    expect(r.label).toBe("Very weak");
  });
});
