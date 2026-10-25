import type { CandidateFact, Draft, GraphNodePayload, TemporalStateField } from "./api";
export type TemporalHistory = { project_id: string; subject_id: string; slots: Array<{ field: TemporalStateField; slot_fingerprint: string; total_assertions: number; truncated: boolean; assertions: Array<{ assertion: GraphNodePayload; active: boolean }> }> };
export type ExactCorrectionSelection = { text: string; start: number; end: number };
export type TemporalCorrectionRequest = { assertion_id: string; source_draft_id: string; expected_draft_version: number; expected_source_sha256: string; source_span: { start_offset: number; end_offset: number; quote: string }; value: string | null; expected_slot_fingerprint: string; rationale: string };
export type TemporalReference = { id: string; label: string; type: string };
export type TemporalCorrectionOptions = { draft: Draft | null; draftDirty: boolean; sceneId: string; selection: ExactCorrectionSelection | null; busy: boolean; canPropose: boolean; references: TemporalReference[]; execute: (label: string, action: () => Promise<unknown>) => Promise<void>; onSubmitted: (candidate: CandidateFact) => Promise<void>; onOpenSourceScene: (id: string) => void; canOpenSourceScene: (id: string) => boolean };
export function exactCorrectionSpan(text: string, selection: ExactCorrectionSelection | null): TemporalCorrectionRequest["source_span"] | null {
  if (!selection || !Number.isSafeInteger(selection.start) || !Number.isSafeInteger(selection.end) || selection.start < 0 || selection.end <= selection.start || selection.end > text.length || text.slice(selection.start, selection.end) !== selection.text || !selection.text.trim() || [...selection.text].length > 500) return null;
  const splitsPair = (index: number) => index > 0 && index < text.length && text.charCodeAt(index - 1) >= 0xd800 && text.charCodeAt(index - 1) <= 0xdbff && text.charCodeAt(index) >= 0xdc00 && text.charCodeAt(index) <= 0xdfff;
  if (splitsPair(selection.start) || splitsPair(selection.end)) return null;
  return { start_offset: [...text.slice(0, selection.start)].length, end_offset: [...text.slice(0, selection.end)].length, quote: selection.text };
}
/** Read offsets from the original saved text node; never map normalized textarea offsets. */
export function readonlyCorrectionSelection(root: HTMLElement, savedText: string, selection: Selection | null): ExactCorrectionSelection | null {
  if (!selection || selection.isCollapsed || selection.rangeCount !== 1 || root.textContent !== savedText || root.childNodes.length !== 1 || root.firstChild?.nodeType !== 3) return null;
  const range = selection.getRangeAt(0); const node = root.firstChild;
  const boundary = (container: Node, offset: number): number | null => container === node ? offset : container === root && offset === 0 ? 0 : container === root && offset === 1 ? savedText.length : null;
  const start = boundary(range.startContainer, range.startOffset); const end = boundary(range.endContainer, range.endOffset);
  if (start === null || end === null) return null;
  const result = { text: savedText.slice(start, end), start, end };
  return exactCorrectionSpan(savedText, result) ? result : null;
}
export function correctionValueAllowed(field: TemporalStateField, value: string | null, references: TemporalReference[]): boolean {
  if (!["life_status", "physical_state", "location_id", "owner_id"].includes(field)) return false;
  if (field === "life_status") return value === "alive" || value === "dead";
  if (field === "physical_state") return value === "healthy" || value === "injured" || value === "healing";
  if (field === "owner_id" && value === null) return true;
  return Boolean(value && references.some((ref) => ref.id === value && (field === "location_id" ? ref.type === "Location" : ref.type === "Character" || ref.type === "Organization")));
}
export async function prepareTemporalCorrection({ projectId, assertion, fingerprint, draft, dirty, selection, value, rationale, references }: { projectId: string; assertion: GraphNodePayload; fingerprint: string; draft: Draft | null; dirty: boolean; selection: ExactCorrectionSelection | null; value: string | null; rationale: string; references: TemporalReference[] }): Promise<TemporalCorrectionRequest | null> {
  const field = assertion.properties.field as TemporalStateField;
  if (!draft || dirty || assertion.type !== "Event" || assertion.properties.event_kind !== "temporal_state_assertion_v1" || assertion.properties.project_id !== projectId || draft.project_id !== projectId || draft.scene_id !== assertion.properties.valid_from_scene || !/^[a-f0-9]{64}$/.test(fingerprint) || !rationale.trim() || [...rationale].length > 1000 || !correctionValueAllowed(field, value, references) || value === assertion.properties.value || !globalThis.crypto?.subtle) return null;
  const span = exactCorrectionSpan(draft.text, selection);
  if (!span) return null;
  const hash = await globalThis.crypto.subtle.digest("SHA-256", new TextEncoder().encode(draft.text));
  return { assertion_id: assertion.id, source_draft_id: draft.id, expected_draft_version: draft.version, expected_source_sha256: Array.from(new Uint8Array(hash), (n) => n.toString(16).padStart(2, "0")).join(""), source_span: span, value, expected_slot_fingerprint: fingerprint, rationale };
}
