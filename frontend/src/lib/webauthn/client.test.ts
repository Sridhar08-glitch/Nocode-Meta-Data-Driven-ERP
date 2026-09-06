import { describe, expect, it } from "vitest";

import { base64urlToBuffer, bufferToBase64url } from "./client";

describe("base64url codecs", () => {
  it("round-trips arbitrary bytes", () => {
    const bytes = new Uint8Array([0, 1, 2, 250, 251, 252, 253, 254, 255]);
    const encoded = bufferToBase64url(bytes.buffer);
    expect(encoded).not.toMatch(/[+/=]/); // url-safe, unpadded
    const decoded = new Uint8Array(base64urlToBuffer(encoded));
    expect(Array.from(decoded)).toEqual(Array.from(bytes));
  });

  it("decodes a known base64url value", () => {
    // "hello" → aGVsbG8
    const buf = base64urlToBuffer("aGVsbG8");
    expect(new TextDecoder().decode(buf)).toBe("hello");
  });

  it("encodes to a known base64url value", () => {
    const buf = new TextEncoder().encode("hello").buffer;
    expect(bufferToBase64url(buf)).toBe("aGVsbG8");
  });
});
