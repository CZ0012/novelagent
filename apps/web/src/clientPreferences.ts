export const API_BASE_STORAGE_KEY = "storygraph.api_base.v1";
export const DEFAULT_API_BASE = "http://127.0.0.1:8000";

export function normalizeApiBase(value: string): string | null {
  try {
    const url = new URL(value.trim());
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || url.search || url.hash) return null;
    return url.toString().replace(/\/$/, "");
  } catch { return null; }
}

export function loadBrowserApiBase(): string {
  try { return normalizeApiBase(window.localStorage.getItem(API_BASE_STORAGE_KEY) ?? "") ?? DEFAULT_API_BASE; }
  catch { return DEFAULT_API_BASE; }
}

export function saveBrowserApiBase(value: string): void {
  const normalized = normalizeApiBase(value);
  if (!normalized) return;
  try { window.localStorage.setItem(API_BASE_STORAGE_KEY, normalized); }
  catch { /* An unavailable client preference never blocks an explicit connection. */ }
}
