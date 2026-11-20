export const MAIN_AGENT_LAYOUT_KEY = "storygraph.ui.main-agent-layout.v1";
export const DEFAULT_MAIN_AGENT_SHARE = 48;
export function clampMainAgentShare(value: number): number {
  return Number.isFinite(value) ? Math.max(28, Math.min(72, Math.round(value))) : DEFAULT_MAIN_AGENT_SHARE;
}
export function readMainAgentShare(storage: Pick<Storage, "getItem">): number {
  try {
    const parsed = JSON.parse(storage.getItem(MAIN_AGENT_LAYOUT_KEY) ?? "null");
    return parsed?.version === 1 && typeof parsed.share === "number" ? clampMainAgentShare(parsed.share) : DEFAULT_MAIN_AGENT_SHARE;
  } catch { return DEFAULT_MAIN_AGENT_SHARE; }
}
export function writeMainAgentShare(storage: Pick<Storage, "setItem">, share: number) {
  try { storage.setItem(MAIN_AGENT_LAYOUT_KEY, JSON.stringify({ version: 1, share: clampMainAgentShare(share) })); } catch { /* Layout works with storage disabled. */ }
}
export function mainAgentKeyboardShare(key: string, share: number, shift = false): number | null {
  if (key === "Home") return 28;
  if (key === "End") return 72;
  if (key === "ArrowUp") return clampMainAgentShare(share + (shift ? 10 : 2));
  if (key === "ArrowDown") return clampMainAgentShare(share - (shift ? 10 : 2));
  return null;
}
