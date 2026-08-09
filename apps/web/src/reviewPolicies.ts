import { diffLines } from "diff";
import type {
  Draft,
  OutputLanguage,
  ProposalArtifact,
  ProposalArtifactType,
  ProposalRef,
  ProposalStatus,
  SourceDocumentSummary
} from "./api";

export type UniqueRefResolution =
  | { status: "none"; ref: null }
  | { status: "unique"; ref: string }
  | { status: "ambiguous"; ref: null };

export type PromotionTargetPolicy =
  | { status: "ready"; targetSceneId: string | null }
  | { status: "missing_scene"; targetSceneId: string | null }
  | { status: "mismatch"; targetSceneId: string }
  | { status: "ambiguous"; targetSceneId: null };

export type ProposalActionPolicy = {
  editable: boolean;
  showSubmit: boolean;
  showDecision: boolean;
  showPromotion: boolean;
  canSave: boolean;
  canSubmit: boolean;
  canDecide: boolean;
  canPromote: boolean;
  readonly: boolean;
};

export type SourceAgentEligibility =
  | "eligible"
  | "not_ready"
  | "unknown_language"
  | "project_language_unavailable"
  | "language_mismatch";

export type ProposalEditorSnapshot = {
  id: string;
  version: number;
  title: string;
  body: string;
};

export type ReviewDiffRow = {
  kind: "equal" | "changed" | "added" | "removed";
  left: string | null;
  right: string | null;
  leftLine: number | null;
  rightLine: number | null;
};

export type AgentIncludedDraftPolicy =
  | { status: "excluded"; draftId: null; version: null }
  | { status: "blocked_missing" | "blocked_dirty" | "blocked_scope"; draftId: null; version: null }
  | { status: "ready"; draftId: string; version: number };

export async function continueAfterSuccessfulSave(
  save: () => Promise<boolean>,
  destination: () => void | Promise<void>
): Promise<boolean> {
  if (!await save()) return false;
  await destination();
  return true;
}

export function projectRequestIsCurrent(
  requestSequence: number,
  currentSequence: number,
  requestApiBase: string,
  currentApiBase: string,
  requestProjectId: string,
  currentProjectId: string
): boolean {
  return (
    requestSequence === currentSequence &&
    requestApiBase === currentApiBase &&
    requestProjectId === currentProjectId
  );
}

export function resolveUniqueProposalRef(
  refs: ProposalRef[],
  kind: string
): UniqueRefResolution {
  const matches = Array.from(
    new Set(
      refs
        .filter((ref) => ref.kind === kind)
        .map((ref) => ref.ref.trim())
        .filter(Boolean)
    )
  );
  if (matches.length === 0) return { status: "none", ref: null };
  if (matches.length === 1) return { status: "unique", ref: matches[0] };
  return { status: "ambiguous", ref: null };
}

export function proposalIsDirty(
  selected: ProposalArtifact | null,
  title: string,
  body: string
): boolean {
  if (!selected) return title.length > 0 || body.length > 0;
  return title !== selected.title || body !== selected.body;
}

export function proposalAutoSelection(
  proposalIds: string[],
  currentProposalId: string | null,
  creatingNewProposal: boolean,
  preserveMissingSelection = false
): string | null {
  if (creatingNewProposal) return null;
  if (
    currentProposalId &&
    (proposalIds.includes(currentProposalId) || preserveMissingSelection)
  ) return currentProposalId;
  return proposalIds[0] ?? null;
}

export function shouldHydrateProposalEditor(
  snapshot: ProposalEditorSnapshot | null,
  incoming: ProposalArtifact,
  currentTitle: string,
  currentBody: string
): boolean {
  if (!snapshot || snapshot.id !== incoming.id) return true;
  if (currentTitle === incoming.title && currentBody === incoming.body) return true;
  return currentTitle === snapshot.title && currentBody === snapshot.body;
}

export function draftIsDirty(
  draft: Draft | null,
  editorText: string,
  editorSummary: string
): boolean {
  return draft
    ? editorText !== draft.text || editorSummary !== (draft.summary ?? "")
    : editorText.length > 0 || editorSummary.length > 0;
}

export function canRestoreSavedDraft(draft: Draft | null, dirty: boolean): boolean {
  return Boolean(draft) && dirty;
}

export function agentIncludedDraftPolicy(
  draft: Draft | null,
  include: boolean,
  dirty: boolean,
  expectedProjectId?: string,
  expectedSceneId?: string
): AgentIncludedDraftPolicy {
  if (!include) return { status: "excluded", draftId: null, version: null };
  if (!draft) return { status: "blocked_missing", draftId: null, version: null };
  if (dirty) return { status: "blocked_dirty", draftId: null, version: null };
  if (
    (expectedProjectId && draft.project_id !== expectedProjectId) ||
    (expectedSceneId && draft.scene_id !== expectedSceneId)
  ) return { status: "blocked_scope", draftId: null, version: null };
  return { status: "ready", draftId: draft.id, version: draft.version };
}

export function proposalActionPolicy(
  status: ProposalStatus,
  dirty: boolean,
  artifactType: ProposalArtifactType
): ProposalActionPolicy {
  const editable = status === "drafting" || status === "agent_revised" || status === "author_revised";
  const showDecision = status === "ready_for_review";
  const showPromotion = status === "accepted" && (
    artifactType === "scene_draft" ||
    artifactType === "fact_draft" ||
    artifactType === "project_structure_draft"
  );
  return {
    editable,
    showSubmit: editable,
    showDecision,
    showPromotion,
    canSave: editable && dirty,
    canSubmit: editable && !dirty,
    canDecide: showDecision && !dirty,
    canPromote: showPromotion && !dirty,
    readonly: status === "accepted" || status === "rejected" || status === "ready_for_review"
  };
}

export function promotionTargetPolicy(
  targetRefs: ProposalRef[],
  currentSceneId: string
): PromotionTargetPolicy {
  const target = resolveUniqueProposalRef(targetRefs, "scene");
  if (target.status === "ambiguous") return { status: "ambiguous", targetSceneId: null };
  if (!currentSceneId) {
    return {
      status: "missing_scene",
      targetSceneId: target.status === "unique" ? target.ref : null
    };
  }
  if (target.status === "unique" && target.ref !== currentSceneId) {
    return { status: "mismatch", targetSceneId: target.ref };
  }
  return {
    status: "ready",
    targetSceneId: target.status === "unique" ? target.ref : null
  };
}

export function sourceAgentEligibility(
  source: SourceDocumentSummary,
  projectLanguage: OutputLanguage | null,
  crossLanguagePolicy: "project_only" | "explicit_reference"
): SourceAgentEligibility {
  if (source.extraction_status !== "ready") return "not_ready";
  if (source.language === "und" || !source.language.trim()) return "unknown_language";
  if (!projectLanguage) return "project_language_unavailable";
  if (source.language !== projectLanguage && crossLanguagePolicy !== "explicit_reference") {
    return "language_mismatch";
  }
  return "eligible";
}

export function sourceCanHandoff(source: SourceDocumentSummary): boolean {
  return (
    source.extraction_status === "ready" &&
    source.language.trim().length > 0 &&
    source.language !== "und"
  );
}

export function addStableSourceSelection(
  current: ReadonlySet<string>,
  stableSourceId: string,
  limit = 32
): Set<string> {
  const next = new Set(current);
  if (stableSourceId && next.size < limit) next.add(stableSourceId);
  return next;
}

export function canOpenPromotedDraft(
  derivedResolution: UniqueRefResolution,
  exactDraftReady: boolean
): boolean {
  return derivedResolution.status === "unique" && exactDraftReady;
}

export function exactDraftMatchesEditorScene(
  exactDraftSceneId: string,
  editorSceneId: string
): boolean {
  return Boolean(editorSceneId) && exactDraftSceneId === editorSceneId;
}

export function buildReviewDiff(baseline: string, proposal: string): ReviewDiffRow[] {
  const rows: ReviewDiffRow[] = [];
  let leftLine = 1;
  let rightLine = 1;
  let pendingLeft: string[] = [];
  let pendingRight: string[] = [];

  const flushChanged = () => {
    const count = Math.max(pendingLeft.length, pendingRight.length);
    for (let index = 0; index < count; index += 1) {
      const left = pendingLeft[index] ?? null;
      const right = pendingRight[index] ?? null;
      rows.push({
        kind: left !== null && right !== null ? "changed" : left !== null ? "removed" : "added",
        left,
        right,
        leftLine: left === null ? null : leftLine++,
        rightLine: right === null ? null : rightLine++
      });
    }
    pendingLeft = [];
    pendingRight = [];
  };

  for (const change of diffLines(
    normalizeNewlines(baseline),
    normalizeNewlines(proposal),
    { newlineIsToken: true }
  )) {
    const lines = splitDiffLines(change.value);
    if (change.removed) {
      pendingLeft.push(...lines);
    } else if (change.added) {
      pendingRight.push(...lines);
    } else {
      flushChanged();
      for (const line of lines) {
        rows.push({
          kind: "equal",
          left: line,
          right: line,
          leftLine: leftLine++,
          rightLine: rightLine++
        });
      }
    }
  }
  flushChanged();
  return rows;
}

function normalizeNewlines(value: string): string {
  return value.replace(/\r\n?/g, "\n");
}

function splitDiffLines(value: string): string[] {
  if (!value) return [];
  const lines = value.split("\n");
  if (lines[lines.length - 1] === "") lines.pop();
  return lines;
}
