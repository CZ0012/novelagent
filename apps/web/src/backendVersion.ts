export type BackendVersion = {
  version: string | null;
  source: "health" | "openapi" | "unknown";
};

export type VersionCompatibility = "match" | "mismatch" | "unknown";

export function normalizedReleaseVersion(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const version = value.trim().replace(/^v/, "");
  return /^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$/.test(version) ? version : null;
}

export function backendVersionCompatibility(appVersion: string, backend: BackendVersion): VersionCompatibility {
  const app = normalizedReleaseVersion(appVersion);
  if (!app || !backend.version) return "unknown";
  return app === backend.version ? "match" : "mismatch";
}

/** Read only version metadata; older installations may expose it only in OpenAPI. */
export async function readBackendVersion(read: (path: string) => Promise<unknown>): Promise<BackendVersion> {
  try {
    const health = await read("/health") as { version?: unknown } | null;
    const version = normalizedReleaseVersion(health?.version);
    if (version) return { version, source: "health" };
  } catch { /* The legacy OpenAPI route is still a useful independent diagnostic. */ }
  try {
    const schema = await read("/openapi.json") as { info?: { version?: unknown } } | null;
    const version = normalizedReleaseVersion(schema?.info?.version);
    if (version) return { version, source: "openapi" };
  } catch { /* Unknown is never treated as matching or current. */ }
  return { version: null, source: "unknown" };
}

export function backendVersionRequestIsCurrent(sequence: number, latestSequence: number, apiBase: string, activeApiBase: string): boolean {
  return sequence === latestSequence && apiBase === activeApiBase;
}
