import { describe, expect, it, vi } from "vitest";
import { backendVersionCompatibility, backendVersionRequestIsCurrent, readBackendVersion } from "./backendVersion";

describe("connected backend version diagnostics", () => {
  it("uses health version without fetching the full schema", async () => {
    const read = vi.fn().mockResolvedValue({ version: "0.1.13" });
    const version = await readBackendVersion(read);
    expect(read).toHaveBeenCalledTimes(1);
    expect(version).toEqual({ version: "0.1.13", source: "health" });
    expect(backendVersionCompatibility("0.1.13", version)).toBe("match");
  });
  it("detects a partial upgrade via the old backend OpenAPI version", async () => {
    const paths: string[] = [];
    const version = await readBackendVersion(async (path) => { paths.push(path); return path === "/health" ? { status: "ok" } : { info: { version: "0.1.10" } }; });
    expect(paths).toEqual(["/health", "/openapi.json"]);
    expect(version).toEqual({ version: "0.1.10", source: "openapi" });
    expect(backendVersionCompatibility("0.1.12", version)).toBe("mismatch");
  });
  it("keeps legacy missing, invalid and unreachable versions unknown", async () => {
    for (const read of [async () => ({}), async () => ({ version: "latest", info: { version: "latest" } }), async () => { throw new Error("offline"); }]) {
      const version = await readBackendVersion(read);
      expect(version).toEqual({ version: null, source: "unknown" });
      expect(backendVersionCompatibility("0.1.13", version)).toBe("unknown");
    }
  });
  it("rejects responses from an old connection or superseded refresh", () => {
    expect(backendVersionRequestIsCurrent(1, 2, "local-a", "local-a")).toBe(false);
    expect(backendVersionRequestIsCurrent(2, 2, "local-a", "local-b")).toBe(false);
    expect(backendVersionRequestIsCurrent(2, 2, "local-b", "local-b")).toBe(true);
  });
});
