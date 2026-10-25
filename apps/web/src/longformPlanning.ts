import type { ProposalArtifact, ModelExecution, GraphNodePayload, TemporalStateField } from "./api";
export type BlueprintRequest = { instruction: string; target_length: number; volume_count: number; chapters_per_volume: number; scenes_per_chapter: number };
export type ExpansionRequest = { parent_proposal_id: string; parent_version: number; volume_index: number; chapter_start: number; chapter_count: number; instruction: string };
export type LongformStyle = { name: string; pov: string; tense: string; tone: string; diction: string; sentence_rhythm: string; dialogue_style: string; banned_patterns: string[]; rubric: string[] };
export type LongformBlueprint = { synopsis: string; world_rules: Array<{ id: string; domain: string; rule: string }>; entities: Array<{ id: string; kind: string; name: string; description: string; initial_state?: Partial<Record<TemporalStateField, string | null>> | null }>; character_arcs: Array<{ character_id: string; initial_state: string; desire: string; conflict: string; turning_points: Array<{ volume_index: number; change: string }>; final_state: string }>; style_brief: LongformStyle; volumes: Array<{ index: number; title: string; summary: string; central_conflict: string; climax: string; ending_hook: string; target_length: number }>; causal_links: Array<{ id: string; from_volume: number; to_volume: number; cause: string; effect: string }>; foreshadowing: Array<{ id: string; clue: string; payoff: string; seed_volume: number; payoff_volume: number; character_ids: string[] }> };
export type LongformExpansion = { volume_index: number; chapter_start: number; chapters: Array<{ index: number; title: string; summary: string; purpose: string; target_length: number; scenes: Array<{ id: string; title: string; summary: string; goal: string; conflict: string; outcome: string; emotional_turn: string; pov_character_id: string | null; location_id: string | null; required_characters: string[]; timeline_position: string; target_length: number; causal_dependencies: string[]; foreshadowing_seed_ids: string[]; foreshadowing_payoff_ids: string[] }> }> };
export type LongformPlan = { schema: "longform_plan_v1"; phase: "blueprint" | "expansion"; project_id: string; output_language: string; graph_snapshot: string; request: BlueprintRequest | ExpansionRequest; parent_proposal_id: string | null; parent_version: number | null; blueprint: LongformBlueprint | null; expansion: LongformExpansion | null };
export type LongformGenerationResult = { proposal: ProposalArtifact; output_language: string; model_execution: ModelExecution | null };
export type LongformApplyResult = { proposal: ProposalArtifact; nodes: GraphNodePayload[]; relationships: unknown[]; already_applied: boolean };
type Data = Record<string, unknown>;
const record = (v: unknown): v is Data => typeof v === "object" && v !== null && !Array.isArray(v);
const texts = (v: unknown, fields: string[]): v is Data => record(v) && fields.every((f) => typeof v[f] === "string");
const positive = (v: unknown, max = 2000000): v is number => Number.isSafeInteger(v) && (v as number) > 0 && (v as number) <= max;
const list = (v: unknown, check: (item: unknown) => boolean, max: number): boolean => Array.isArray(v) && v.length <= max && v.every(check);
const strings = (v: unknown): boolean => list(v, (item) => typeof item === "string", 100);
export function isRenderableBlueprint(b: unknown): b is LongformBlueprint {
  if (!texts(b, ["synopsis"])) return false;
  if (!list(b.world_rules, (v) => texts(v, ["id", "domain", "rule"]), 30) || !list(b.entities, (v) => texts(v, ["id", "kind", "name", "description"]), 60) || !list(b.volumes, (v) => texts(v, ["title", "summary", "central_conflict", "climax", "ending_hook"]) && positive(v.index, 12) && positive(v.target_length), 12) || !(b.volumes as unknown[]).length) return false;
  if (!texts(b.style_brief, ["name", "pov", "tense", "tone", "diction", "sentence_rhythm", "dialogue_style"]) || !strings(b.style_brief.banned_patterns) || !strings(b.style_brief.rubric)) return false;
  if (!list(b.character_arcs, (v) => texts(v, ["character_id", "initial_state", "desire", "conflict", "final_state"]) && list(v.turning_points, (point) => texts(point, ["change"]) && positive(point.volume_index, 12), 12), 30)) return false;
  if (!list(b.causal_links, (v) => texts(v, ["id", "cause", "effect"]) && positive(v.from_volume, 12) && positive(v.to_volume, 12), 60) || !list(b.foreshadowing, (v) => texts(v, ["id", "clue", "payoff"]) && positive(v.seed_volume, 12) && positive(v.payoff_volume, 12) && strings(v.character_ids), 60)) return false;
  return true;
}
export function isRenderableExpansion(e: unknown): e is LongformExpansion {
  if (!record(e) || !positive(e.volume_index, 12) || !positive(e.chapter_start, 60)) return false;
  if (!list(e.chapters, (c) => texts(c, ["title", "summary", "purpose"]) && positive(c.index, 60) && positive(c.target_length) && list(c.scenes, (v) => texts(v, ["id", "title", "summary", "goal", "conflict", "outcome", "emotional_turn", "pov_character_id", "location_id", "timeline_position"]) && positive(v.target_length) && ["required_characters", "causal_dependencies", "foreshadowing_seed_ids", "foreshadowing_payoff_ids"].every((f) => strings(v[f])), 6) && (c.scenes as unknown[]).length > 0, 5) || !(e.chapters as unknown[]).length) return false;
  return true;
}
/** Display recognition only. The backend validates complete schema and references before application. */
export function parseLongformPlan(proposal: ProposalArtifact | null): LongformPlan | null {
  if (!proposal || proposal.artifact_type !== "outline_draft" || proposal.body_format !== "structured_json" || proposal.body.length > 2000000) return null;
  try {
    const p = JSON.parse(proposal.body);
    if (!record(p) || p.schema !== "longform_plan_v1" || p.project_id !== proposal.project_id || !["zh-CN", "en-US"].includes(p.output_language as string) || p.output_language !== proposal.content_language || !record(p.request) || typeof p.graph_snapshot !== "string" || !/^[a-f0-9]{64}$/.test(p.graph_snapshot)) return null;
    if (p.phase === "blueprint") {
      const b = p.blueprint; const r = p.request;
      if (!texts(r, ["instruction"]) || !positive(r.target_length) || r.target_length < 10000 || !positive(r.volume_count, 12) || !positive(r.chapters_per_volume, 60) || !positive(r.scenes_per_chapter, 6) || !texts(b, ["synopsis"]) || p.expansion !== null || p.parent_proposal_id !== null || p.parent_version !== null) return null;
      if (!isRenderableBlueprint(b)) return null;
      return p as LongformPlan;
    }
    if (p.phase === "expansion") {
      const e = p.expansion;
      if (!record(e) || !positive(e.volume_index, 12) || !positive(e.chapter_start, 60) || typeof p.parent_proposal_id !== "string" || !p.parent_proposal_id || !positive(p.parent_version) || p.blueprint !== null) return null;
      if (!isRenderableExpansion(e)) return null;
      return p as LongformPlan;
    }
  } catch { /* Malformed artifacts stay non-executable. */ }
  return null;
}
export function longformApplied(proposal: ProposalArtifact): boolean {
  return proposal.status === "accepted" && proposal.derived_refs.some((ref) => ref.kind === "longform_application" && ref.ref === proposal.id);
}
export function nextPlanningBatch(blueprint: ProposalArtifact, proposals: ProposalArtifact[]): { volume_index: number; chapter_start: number; chapter_count: number; finished: boolean; completedBatches: number } {
  const p = parseLongformPlan(blueprint);
  const request = p?.request as BlueprintRequest | undefined;
  if (!request || p?.phase !== "blueprint") return { volume_index: 1, chapter_start: 1, chapter_count: 5, finished: false, completedBatches: 0 };
  const applied = proposals.filter((item) => item.project_id === blueprint.project_id && longformApplied(item)).map(parseLongformPlan).filter((item): item is LongformPlan => Boolean(item?.phase === "expansion" && item.parent_proposal_id === blueprint.id));
  for (let v = 1; v <= request.volume_count; v++) {
    const covered = new Set(applied.filter((item) => item.expansion?.volume_index === v).flatMap((item) => item.expansion!.chapters.map((chapter) => chapter.index)));
    let start = 1; while (covered.has(start)) start++;
    if (start <= request.chapters_per_volume) return { volume_index: v, chapter_start: start, chapter_count: Math.min(5, request.chapters_per_volume - start + 1), finished: false, completedBatches: applied.length };
  }
  return { volume_index: request.volume_count, chapter_start: request.chapters_per_volume + 1, chapter_count: 0, finished: true, completedBatches: applied.length };
}
