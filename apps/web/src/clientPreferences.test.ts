import { describe, expect, it } from "vitest";
import { normalizeApiBase } from "./clientPreferences";

describe("browser backend address preference", () => {
  it("normalizes a non-default local API address and optional proxy prefix", () => {
    expect(normalizeApiBase(" http://127.0.0.1:8765/ ")).toBe("http://127.0.0.1:8765");
    expect(normalizeApiBase("https://example.test/storygraph/")).toBe("https://example.test/storygraph");
  });
  it("refuses credential-bearing, query-bearing, fragment and non-HTTP addresses", () => {
    for (const value of ["https://user:secret@example.test", "https://example.test?key=secret", "https://example.test#secret", "file:///tmp/a", "invalid"]) {
      expect(normalizeApiBase(value)).toBeNull();
    }
  });
});
