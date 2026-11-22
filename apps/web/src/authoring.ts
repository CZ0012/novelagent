import type { VisibilitySpec } from "./WriterVisibilityPanel";
import { apiGet, apiPost, type Draft, type WriterChoice } from "./api";

export type AuthoringSourcePin = { kind: "source_document" | "outline"; id: string; version?: number | null; sha256: string };
export type AuthoringDraftPin = { scene_id: string; draft_id: string; version: number; text_sha256: string };
export type AuthoringEvidence = { draft: AuthoringDraftPin; start: number; end: number; expected_text: string; offset_unit: "utf16" };
export type AuthoringDesignItem = { id: string; kind: "world_fact" | "true_cause" | "character_belief" | "character_claim" | "open_question"; status: "open" | "alternative" | "author_decided"; text: string; character_id?: string | null; about_character_id?: string | null; alternative_group?: string | null; rationale: string; depends_on: string[]; evidence: AuthoringEvidence[] };
export type AuthoringKnowledge = { character_id: string; text: string; item_id?: string | null; evidence: AuthoringEvidence[] };
export type AuthoringAction = { character_id: string; intention: string; depends_on: string[] };
export type AuthoringCharacterPlan = { character_id: string; goal: string; belief_item_ids: string[]; knowledge_assumptions: string[]; intended_actions: AuthoringAction[] };
export type AuthoringSceneCard = { id: string; version: number; title: string; author_summary?: string; chapter_title: string; location: string; timeline_position: string; goal: string; conflict: string; emotional_turn: string; target_length: number; scene_id?: string | null; status: "proposed" | "approved"; pov_character_id?: string | null; entry_knowledge: AuthoringKnowledge[]; intended_actions: AuthoringAction[]; acquisitions: AuthoringKnowledge[]; writer_policy: VisibilitySpec; withheld: string[]; intended_outcome: string; depends_on: string[] };
export type AuthoringReaderRecord = { draft_id: string; version: number; text_sha256: string; start: number; end: number; offset_unit: "utf16"; expected_text: string; presentation: "narration" | "character_statement" | "clue" };
export type AuthoringWorkspace = { items: AuthoringDesignItem[]; character_plans: AuthoringCharacterPlan[]; scene_cards: AuthoringSceneCard[]; reader_records: AuthoringReaderRecord[] };
export type AuthoringPatch = { upsert_items: AuthoringDesignItem[]; upsert_character_plans: AuthoringCharacterPlan[]; upsert_scene_cards: AuthoringSceneCard[]; remove_item_ids: string[]; remove_character_ids: string[]; remove_card_ids: string[]; add_reader_records: AuthoringReaderRecord[]; remove_reader_records: AuthoringReaderRecord[] };
export function authoringPatchedWorkspace(workspace: AuthoringWorkspace, patch: AuthoringPatch): AuthoringWorkspace {
  function merge<T>(items: T[], upserts: T[], removes: string[], key: (item: T) => string) {
    const result = new Map(items.map(item => [key(item), item]));
    removes.forEach(id => result.delete(id)); upserts.forEach(item => result.set(key(item), item)); return [...result.values()];
  }
  return { items: merge(workspace.items, patch.upsert_items, patch.remove_item_ids, item => item.id), character_plans: merge(workspace.character_plans, patch.upsert_character_plans, patch.remove_character_ids, item => item.character_id), scene_cards: merge(workspace.scene_cards, patch.upsert_scene_cards, patch.remove_card_ids, item => item.id), reader_records: [...workspace.reader_records.filter(record => !patch.remove_reader_records.some(removed => JSON.stringify(removed) === JSON.stringify(record))), ...patch.add_reader_records] };
}
export type AuthoringProposal = { id: string; base_workspace_sha256: string; supersedes_proposal_id?: string | null; stale?: boolean; patch: AuthoringPatch; summary: string; affected_card_ids: string[]; affected_scene_ids: string[]; status: "pending" | "adopted" | "rejected"; evidence: AuthoringEvidence[]; created_at: string; reviewed_by?: string | null; reviewed_at?: string | null };
export type AuthoringSession = { writer_choice?: WriterChoice | null; contract_version: "authoring_session_v1"; id: string; project_id: string; version: number; content_language: string; turn_status: "idle" | "running" | "failed" | "unknown"; turn_id: string | null; turn_error_category: string | null; title: string; source_pins: AuthoringSourcePin[]; draft_pins: AuthoringDraftPin[]; messages: Array<{ id: string; role: "author" | "assistant" | "tool"; content: string; created_at: string; tool_name?: string | null; tool_call_id?: string | null }>; workspace: AuthoringWorkspace; proposals: AuthoringProposal[]; history_counts?: { messages: number; proposals: number }; history_has_more?: { messages: boolean; proposals: boolean }; created_at: string; updated_at: string };

export function authoringChanges(before: AuthoringWorkspace, after: AuthoringWorkspace) {
  const changes: Array<{ id: string; kind: "items" | "character_plans" | "scene_cards" | "reader_records"; before: unknown; after: unknown }> = [];
  for (const kind of ["items", "character_plans", "scene_cards", "reader_records"] as const) {
    const key = (value: unknown, index: number) => { const item = value as { id?: string; character_id?: string }; return item.id ?? item.character_id ?? String(index); };
    const previous = new Map(before[kind].map((item, index) => [key(item, index), item]));
    const next = new Map(after[kind].map((item, index) => [key(item, index), item]));
    for (const id of new Set([...previous.keys(), ...next.keys()])) if (JSON.stringify(previous.get(id)) !== JSON.stringify(next.get(id))) changes.push({ id, kind, before: previous.get(id), after: next.get(id) });
  }
  return changes;
}

export async function authoringSha256(text: string) {
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(bytes), value => value.toString(16).padStart(2, "0")).join("");
}

export type AuthoringPreview = { mode: "isolated"; writer_view: Record<string, unknown>; messages: Array<{ role: string; content: string }>; source_context_sha256: string; policy: VisibilitySpec; card_id: string; card_version: number; expected_policy_version: number };
export type AuthoringStructurePreview = { operation?: "create" | "update"; current_scene?: { id: string; type: string; properties: Record<string, unknown> } | null; changes?: Array<{ field: string; before: unknown; after: unknown }>; reuse?: Array<{ id: string; type: string; name?: string | null; public_name?: string | null }>; source_sha256: string; card_version: number; scene_id: string; chapter_id: string; nodes: Array<{ id: string; type: string; properties: Record<string, unknown> }>; relationships: Array<{ id: string; type: string; source_id: string; target_id: string; properties: Record<string, unknown> }>; character_mapping: Record<string, string>; gaps: string[] };
export const authoringPath = (project: string, session?: string) => `/projects/${encodeURIComponent(project)}/authoring-sessions${session ? `/${encodeURIComponent(session)}` : ""}`;
export async function listAuthoringSessions(base: string, project: string) { return (await apiGet<{ sessions: Array<Pick<AuthoringSession, "id" | "project_id" | "title" | "version" | "updated_at">> }>(base, authoringPath(project))).sessions; }
export async function getAuthoringSession(base: string, project: string, id: string) { return (await apiGet<{ session: AuthoringSession }>(base, authoringPath(project, id))).session; }
export async function postAuthoringSession(base: string, project: string, id: string | undefined, suffix: string, body: unknown) { return (await apiPost<{ session: AuthoringSession }>(base, authoringPath(project, id) + suffix, body)).session; }
export async function previewAuthoringStructure(base: string, project: string, session: AuthoringSession, cardId: string) { return apiPost<AuthoringStructurePreview>(base, authoringPath(project, session.id) + `/cards/${encodeURIComponent(cardId)}/structure-preview`, { expected_version: session.version }); }
export async function applyAuthoringStructure(base: string, project: string, session: AuthoringSession, cardId: string, preview: AuthoringStructurePreview, rationale: string) { return apiPost<{ session: AuthoringSession; scene_id: string; chapter_id: string }>(base, authoringPath(project, session.id) + `/cards/${encodeURIComponent(cardId)}/structure-apply`, { expected_version: session.version, card_version: preview.card_version, source_sha256: preview.source_sha256, reviewer: "author", rationale }); }
export function authoringReconciliationCards(session: AuthoringSession, draft: Draft | null) {
  return draft?.project_id === session.project_id ? session.workspace.scene_cards.filter(card => card.scene_id === draft.scene_id) : [];
}
export function authoringReconciliationCard(session: AuthoringSession, draft: Draft | null, selectedId?: string) {
  const cards = authoringReconciliationCards(session, draft);
  return selectedId ? cards.find(card => card.id === selectedId) ?? null : cards.length === 1 ? cards[0] : null;
}
export async function reconcileAuthoringDraft(base: string, session: AuthoringSession, draft: Draft, selectedId?: string) {
  const card = authoringReconciliationCard(session, draft, selectedId);
  if (!card) throw new Error("Select an exact same-scene design card before reconciliation.");
  return postAuthoringSession(base, session.project_id, session.id, "/reconcile", { expected_version: session.version, card_id: card.id, card_version: card.version, draft_id: draft.id, draft_version: draft.version, text_sha256: await authoringSha256(draft.text), max_steps: 6 });
}
export type AuthoringHistoryKind = "messages" | "proposals";
export type AuthoringHistoryRecord = AuthoringSession["messages"][number] | AuthoringProposal;
export type AuthoringHistoryPage = { records: AuthoringHistoryRecord[]; total_matches: number; returned_count: number; offset: number; more: boolean; next_offset: number | null; order: "newest_first" };
export function authoringCanAdopt(proposal: Pick<AuthoringProposal, "status" | "stale">) { return proposal.status === "pending" && proposal.stale === false; }
export async function readAuthoringHistory(base: string, project: string, sessionId: string, kind: AuthoringHistoryKind, query = "", offset = 0) {
  const params = new URLSearchParams({ kind, query, offset: String(offset), limit: "40" });
  return apiGet<AuthoringHistoryPage>(base, authoringPath(project, sessionId) + "/history?" + params.toString());
}
export async function readAuthoringProposal(base: string, project: string, sessionId: string, id: string) { return (await apiGet<{ proposal: AuthoringProposal }>(base, authoringPath(project, sessionId) + `/proposals/${encodeURIComponent(id)}`)).proposal; }
export async function updateAuthoringSources(base: string, project: string, sessionId: string, expectedVersion: number, sourceIds: string[], outlineIds: string[]) { return postAuthoringSession(base, project, sessionId, "/sources", { expected_version: expectedVersion, source_document_ids: sourceIds, outline_proposal_ids: outlineIds }); }


export type AuthoringNavigation = { writer_choice?: WriterChoice | null; target: "conversation" | "design" | "checks" | "manuscript" | "sources" | "graph" | "settings" | "planning" | "proposals" | "writer" | "continuity"; scene_id?: string; chapter_id?: string };
export function authoringToolNavigation(content: string): AuthoringNavigation | null {
  try {
    const trace = JSON.parse(content);
    if (trace?.tool !== "open_workflow" || (trace.op !== undefined && trace.op !== "open_workflow") || trace.result?.executed !== false) return null;
    const value: unknown = trace.result.navigation;
    if (!value || typeof value !== "object") return null;
    const target = value as Record<string, unknown>;
    const requested = trace.args?.target;
    const openTarget = trace.result.status === "requires_author_action" && requested === target.target;
    const selectScene = trace.result.status === "requires_scene_selection"
      && (requested === "writer" || requested === "continuity")
      && target.target === "manuscript" && target.scene_id === undefined;
    if (!openTarget && !selectScene) return null;
    if (!["conversation", "design", "checks", "manuscript", "sources", "graph", "settings", "planning", "proposals", "writer", "continuity"].includes(String(target.target))) return null;
    if ((target.scene_id !== undefined && typeof target.scene_id !== "string") || (target.chapter_id !== undefined && typeof target.chapter_id !== "string")) return null;
    return { target: target.target as AuthoringNavigation["target"], ...(target.scene_id ? { scene_id: target.scene_id as string } : {}), ...(target.chapter_id ? { chapter_id: target.chapter_id as string } : {}) };
  } catch { return null; }
}
export function authoringCanPinDraft(projectId: string, sceneId: string | undefined, draft: Draft | null, dirty: boolean) {
  return !!sceneId && !!draft && !dirty && draft.project_id === projectId && draft.scene_id === sceneId;
}

export type AuthoringPassageSelection = { draftId: string; start: number; end: number; text: string };
export function authoringValidPassage(projectId: string, sceneId: string | undefined, draft: Draft | null, dirty: boolean, selection: AuthoringPassageSelection | null | undefined) {
  if (!sceneId || !authoringCanPinDraft(projectId, sceneId, draft, dirty) || !draft || !selection || selection.draftId !== draft.id) return false;
  const { start, end, text } = selection;
  const splitSurrogate = (position: number) => position > 0 && position < draft.text.length && /[\uD800-\uDBFF]/.test(draft.text[position - 1]) && /[\uDC00-\uDFFF]/.test(draft.text[position]);
  return Number.isInteger(start) && Number.isInteger(end) && start >= 0 && end > start && end - start <= 8000 && end <= draft.text.length && !!text.trim() && draft.text.slice(start, end) === text && !splitSurrogate(start) && !splitSurrogate(end);
}
