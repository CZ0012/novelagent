import type { AgentDiscussionRequest, Draft, ProseInputGrants } from "./api";
async function sha256(text: string) { const digest = await globalThis.crypto.subtle.digest("SHA-256", new TextEncoder().encode(text)); return Array.from(new Uint8Array(digest), n => n.toString(16).padStart(2, "0")).join(""); }
/** A prose button authorizes only this instruction and its exact saved editing target. */
export async function proseInputGrants(request: AgentDiscussionRequest, draft: Draft | null): Promise<ProseInputGrants | undefined> {
  if (request.mode === "discuss") return undefined;
  const grant: ProseInputGrants = { instruction: true, instruction_sha256: await sha256(request.instruction.trim()), target: "none" };
  if (request.mode === "create_scene") return grant;
  if (!draft || !request.include_latest_draft || request.included_draft_id !== draft.id) throw new Error("Pinned saved Draft required.");
  Object.assign(grant, { target: request.mode === "revise_selection" ? "selection" : "draft", draft_id: draft.id, version: draft.version, text_sha256: await sha256(draft.text) });
  if (request.mode === "revise_selection") {
    const { selected_start: start, selected_end: end, selected_text: text } = request;
    if (start == null || end == null || !text || end <= start || draft.text.slice(start, end) !== text) throw new Error("Exact saved selection required.");
    Object.assign(grant, { start, end, expected_text: text, offset_unit: "utf16" });
  }
  return grant;
}
