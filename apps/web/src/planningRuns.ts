import { apiPost, type ModelTask, type ProposalArtifact } from "./api";
import { isRenderableBlueprint, isRenderableExpansion, type BlueprintRequest, type LongformBlueprint, type LongformExpansion } from "./longformPlanning";
export const MAX_PLANNING_RUN_CALLS = 512;
export type PlanningRunRequest = BlueprintRequest & { batch_size: number; max_calls: number; max_repairs_per_step: number; seed_blueprint_id?: string; seed_blueprint_version?: number };
export type PlanningArtifactRef = { id: string; version: number; body_sha256: string };
export type PlanningRunStatus = "queued" | "running" | "paused" | "awaiting_review" | "completed";
export type PlanningRunStage = "blueprint" | "expansion" | "book_review" | "bundle" | "done";
export type PlanningRevisionMode = "targeted" | "full";
export type PlanningRestartRecovery = { preserve_later_outputs: boolean; revision_mode: PlanningRevisionMode };
export type PlanningRunStep = { index: number; phase: "blueprint" | "expansion"; volume_index: number | null; chapter_start: number | null; chapter_count: number | null; status: "pending" | "generated" | "needs_revision" | "passed"; proposal_ref: PlanningArtifactRef | null; review_id: string | null; repairs: number; retained_output_ref?: PlanningArtifactRef | null; revision_mode?: PlanningRevisionMode };
export type PlanningRun = { id: string; project_id: string; version: number; status: PlanningRunStatus; stage: PlanningRunStage; request: PlanningRunRequest; output_language: string; canon_fingerprint: string; calls_reserved: number; max_calls: number; stop_requested: boolean; pause_reason: string | null; pending_call: { id: string; task: ModelTask; operation: string; step_index: number } | null; steps: PlanningRunStep[]; bundle_proposal_id: string | null; final_review_id?: string | null; created_at: string; updated_at: string };
export type PlanningBranch = { schema: "longform_branch_plan_v1"; run_id: string; project_id: string; output_language: string; canon_fingerprint: string; step_index: number; phase: "blueprint" | "expansion"; blueprint_ref: PlanningArtifactRef | null; previous_refs: PlanningArtifactRef[]; blueprint: LongformBlueprint | null; expansion: LongformExpansion | null };
export type PlanningBookBundle = { schema: "longform_book_bundle_v1"; run_id: string; project_id: string; output_language: string; canon_fingerprint: string; blueprint_ref: PlanningArtifactRef; expansion_refs: PlanningArtifactRef[]; final_review_id: string };
export function blueprintInputValid(request: BlueprintRequest): boolean {
  const bounded = (value: number, min: number, max: number) => Number.isSafeInteger(value) && value >= min && value <= max;
  return Boolean(request.instruction.trim()) && [...request.instruction].length <= 12000 && bounded(request.target_length, 10000, 2000000) && bounded(request.volume_count, 1, 12) && bounded(request.chapters_per_volume, 1, 60) && bounded(request.scenes_per_chapter, 1, 6);
}
export function planningRunInputValid(request: PlanningRunRequest): boolean {
  return blueprintInputValid(request) && ((request.seed_blueprint_id === undefined && request.seed_blueprint_version === undefined) || Boolean(request.seed_blueprint_id && Number.isSafeInteger(request.seed_blueprint_version) && request.seed_blueprint_version! >= 1)) && Number.isSafeInteger(request.batch_size) && request.batch_size >= 1 && request.batch_size <= 5 && Number.isSafeInteger(request.max_calls) && request.max_calls >= 1 && request.max_calls <= MAX_PLANNING_RUN_CALLS && Number.isSafeInteger(request.max_repairs_per_step) && request.max_repairs_per_step >= 0 && request.max_repairs_per_step <= 2;
}
export function planningRunReady(run: PlanningRun): boolean {
  return (run.status === "awaiting_review" || run.status === "completed") && run.stage === "done" && Boolean(run.bundle_proposal_id) && Boolean(run.final_review_id) && !run.pending_call && run.steps.length > 0 && run.steps.every((step) => step.status === "passed" && step.proposal_ref && step.review_id);
}
export function planningRunNeedsUncertainRetry(run: PlanningRun): boolean { return run.status === "paused" && (run.pause_reason === "uncertain_call" || Boolean(run.pending_call)); }
export function planningRunCanResume(run: PlanningRun, maxCalls = run.max_calls): boolean { return run.status === "paused" && run.pause_reason !== "canon_changed" && run.pause_reason !== "source_changed" && run.pause_reason !== "connection_changed" && Number.isSafeInteger(maxCalls) && maxCalls >= run.max_calls && maxCalls <= MAX_PLANNING_RUN_CALLS && maxCalls > run.calls_reserved; }
export function planningBookApplied(proposal: ProposalArtifact): boolean { return proposal.status === "accepted" && proposal.derived_refs.some((ref) => ref.kind === "longform_book_application" && ref.ref === proposal.id); }
const validRef = (ref: unknown): ref is PlanningArtifactRef => typeof ref === "object" && ref !== null && "id" in ref && typeof ref.id === "string" && Boolean(ref.id) && "version" in ref && Number.isSafeInteger(ref.version) && Number(ref.version) > 0 && "body_sha256" in ref && typeof ref.body_sha256 === "string" && /^[a-f0-9]{64}$/.test(ref.body_sha256);
export function parsePlanningBook(proposal: ProposalArtifact | null): PlanningBookBundle | null {
  if (!proposal || proposal.artifact_type !== "outline_draft" || proposal.body_format !== "structured_json" || proposal.body.length > 2000000) return null;
  try { const p = JSON.parse(proposal.body); return p.schema === "longform_book_bundle_v1" && p.project_id === proposal.project_id && p.output_language === proposal.content_language && typeof p.run_id === "string" && /^[a-f0-9]{64}$/.test(p.canon_fingerprint) && validRef(p.blueprint_ref) && Array.isArray(p.expansion_refs) && p.expansion_refs.length > 0 && p.expansion_refs.length <= 720 && p.expansion_refs.every(validRef) && new Set([p.blueprint_ref, ...p.expansion_refs].map((ref: PlanningArtifactRef) => ref.id)).size === p.expansion_refs.length + 1 && typeof p.final_review_id === "string" && Boolean(p.final_review_id) ? p : null; } catch { return null; }
}

export function parsePlanningBranch(proposal: ProposalArtifact, runId?: string): PlanningBranch | null {
  if (proposal.artifact_type !== "outline_draft" || proposal.body_format !== "structured_json" || proposal.body.length > 2000000) return null;
  try { const p = JSON.parse(proposal.body); if (p.schema !== "longform_branch_plan_v1" || typeof p.run_id !== "string" || !p.run_id || (runId !== undefined && p.run_id !== runId) || p.project_id !== proposal.project_id || p.output_language !== proposal.content_language || !/^[a-f0-9]{64}$/.test(p.canon_fingerprint) || !Number.isSafeInteger(p.step_index) || p.step_index < 0) return null;
    return p.phase === "blueprint" && p.expansion === null && isRenderableBlueprint(p.blueprint) || p.phase === "expansion" && p.blueprint === null && isRenderableExpansion(p.expansion) ? p : null;
  } catch { return null; }
}
export async function pinnedPlanningArtifactMatches(proposal: ProposalArtifact, ref: PlanningArtifactRef, projectId: string): Promise<boolean> {
  if (proposal.project_id !== projectId || proposal.id !== ref.id || proposal.version !== ref.version || !globalThis.crypto?.subtle) return false;
  const hash = await globalThis.crypto.subtle.digest("SHA-256", new TextEncoder().encode(proposal.body));
  return Array.from(new Uint8Array(hash), (byte) => byte.toString(16).padStart(2, "0")).join("") === ref.body_sha256;
}

export function planningRunResumeBody(run: PlanningRun, explicitUncertainConsent: boolean, maxCalls = run.max_calls, restartFromStep: number | null = null, revisionInstruction = "", recovery?: PlanningRestartRecovery): { expected_version: number; retry_uncertain_call: boolean; max_calls?: number; restart_from_step?: number; revision_instruction?: string; preserve_later_outputs?: boolean; revision_mode?: PlanningRevisionMode } | null {
  if (!planningRunCanResume(run, maxCalls) || (planningRunNeedsUncertainRetry(run) && !explicitUncertainConsent)) return null;
  if (restartFromStep !== null && (!Number.isSafeInteger(restartFromStep) || !run.steps.some((step) => step.index === restartFromStep))) return null;
  if ([...revisionInstruction].length > 12000 || (revisionInstruction.trim() && restartFromStep === null)) return null;
  if (recovery && ((recovery.preserve_later_outputs || recovery.revision_mode === "full") && restartFromStep === null || recovery.revision_mode === "full" && !revisionInstruction.trim())) return null;
  return { ...(restartFromStep !== null ? { restart_from_step: restartFromStep, ...(revisionInstruction.trim() ? { revision_instruction: revisionInstruction } : {}), ...(recovery ? { preserve_later_outputs: recovery.preserve_later_outputs, revision_mode: recovery.revision_mode } : {}) } : {}), expected_version: run.version, retry_uncertain_call: planningRunNeedsUncertainRetry(run) && explicitUncertainConsent, ...(maxCalls !== run.max_calls ? { max_calls: maxCalls } : {}) };
}
export function mergePlanningRunRecords(records: PlanningRun[], incoming: PlanningRun, projectId: string): PlanningRun[] {
  if (incoming.project_id !== projectId) return records;
  const current = records.find((run) => run.id === incoming.id);
  if (current && current.version > incoming.version) return records;
  return [incoming, ...records.filter((run) => run.id !== incoming.id)].sort((a, b) => b.updated_at.localeCompare(a.updated_at));
}

export function planningRunCreateRequest(visible: BlueprintRequest, batchSize: number, maxCalls: number, maxRepairs: number, seed?: { id: string; version: number; request: BlueprintRequest } | null): PlanningRunRequest {
  const source = seed?.request ?? visible;
  return { instruction: source.instruction, target_length: source.target_length, volume_count: source.volume_count, chapters_per_volume: source.chapters_per_volume, scenes_per_chapter: source.scenes_per_chapter, batch_size: batchSize, max_calls: maxCalls, max_repairs_per_step: maxRepairs, ...(seed ? { seed_blueprint_id: seed.id, seed_blueprint_version: seed.version } : {}) };
}

export function planningRunRecheckBody(run: PlanningRun): { expected_version: number; recheck_current_step: true } | null {
  if (!planningRunCanResume(run) || planningRunNeedsUncertainRetry(run)) return null;
  const step = run.steps.find((item) => item.status !== "passed");
  if (!step?.proposal_ref || !validRef(step.proposal_ref)) return null;
  return { expected_version: run.version, recheck_current_step: true };
}

export function planningRunCopyBlueprintBody(run: PlanningRun): { expected_version: number } | null {
  if (!["paused", "awaiting_review"].includes(run.status) || run.pending_call || run.pause_reason === "uncertain_call") return null;
  const blueprint = run.steps.find((step) => step.index === 0 && step.phase === "blueprint");
  return blueprint?.status === "passed" && blueprint.proposal_ref && validRef(blueprint.proposal_ref) && blueprint.review_id ? { expected_version: run.version } : null;
}
export async function copyPlanningRunBlueprint(apiBase: string, projectId: string, run: PlanningRun): Promise<ProposalArtifact> {
  const body = planningRunCopyBlueprintBody(run);
  if (run.project_id !== projectId || !body) throw new Error("Planning blueprint copy is unavailable.");
  const response = await apiPost<{ proposal: ProposalArtifact }>(apiBase, `/projects/${encodeURIComponent(projectId)}/planning-runs/${encodeURIComponent(run.id)}/copy-blueprint`, body);
  return response.proposal;
}
