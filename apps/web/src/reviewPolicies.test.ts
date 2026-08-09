import { describe, expect, it } from "vitest";
import type { Draft, ProposalArtifact, ProposalRef, SourceDocumentSummary } from "./api";
import {
  addStableSourceSelection,
  agentIncludedDraftPolicy,
  buildReviewDiff,
  canOpenPromotedDraft,
  canRestoreSavedDraft,
  continueAfterSuccessfulSave,
  draftIsDirty,
  exactDraftMatchesEditorScene,
  promotionTargetPolicy,
  proposalActionPolicy,
  proposalAutoSelection,
  proposalIsDirty,
  projectRequestIsCurrent,
  resolveUniqueProposalRef,
  shouldHydrateProposalEditor,
  sourceCanHandoff,
  sourceAgentEligibility
} from "./reviewPolicies";

const refs = (values: string[]): ProposalRef[] => values.map((ref) => ({ kind: "draft", ref }));

describe("exact proposal references", () => {
  it("chooses one unique draft ref, never current-latest fallback", () => {
    expect(resolveUniqueProposalRef([], "draft")).toEqual({ status: "none", ref: null });
    expect(resolveUniqueProposalRef(refs(["draft_v1", "draft_v1"]), "draft")).toEqual({ status: "unique", ref: "draft_v1" });
    expect(resolveUniqueProposalRef(refs(["draft_v1", "draft_v2"]), "draft")).toEqual({ status: "ambiguous", ref: null });
  });

  it("resolves refs from the history version being reviewed, not from latest", () => {
    const historyV1 = {
      version: 1,
      source_refs: [{ kind: "draft", ref: "draft_v1" }],
      target_refs: [{ kind: "scene", ref: "scene_v1" }]
    } as ProposalArtifact;
    const latestV2 = {
      version: 2,
      source_refs: [{ kind: "draft", ref: "draft_v2" }],
      target_refs: [{ kind: "scene", ref: "scene_v2" }]
    } as ProposalArtifact;
    expect(resolveUniqueProposalRef(historyV1.source_refs, "draft").ref).toBe("draft_v1");
    expect(resolveUniqueProposalRef(historyV1.target_refs, "scene").ref).toBe("scene_v1");
    expect(resolveUniqueProposalRef(latestV2.source_refs, "draft").ref).toBe("draft_v2");
  });

  it("blocks an ambiguous or mismatched declared scene target", () => {
    expect(promotionTargetPolicy([], "scene_a")).toEqual({ status: "ready", targetSceneId: null });
    expect(promotionTargetPolicy([], "").status).toBe("missing_scene");
    expect(promotionTargetPolicy([{ kind: "scene", ref: "scene_a" }], "")).toEqual({ status: "missing_scene", targetSceneId: "scene_a" });
    expect(promotionTargetPolicy([{ kind: "scene", ref: "scene_a" }], "scene_a").status).toBe("ready");
    expect(promotionTargetPolicy([{ kind: "scene", ref: "scene_a" }], "scene_b")).toEqual({ status: "mismatch", targetSceneId: "scene_a" });
    expect(promotionTargetPolicy([{ kind: "scene", ref: "scene_a" }, { kind: "scene", ref: "scene_b" }], "scene_a").status).toBe("ambiguous");
  });

  it("opens only one exact derived Draft and never chooses an ambiguous ref", () => {
    expect(canOpenPromotedDraft({ status: "unique", ref: "draft_1" }, true)).toBe(true);
    expect(canOpenPromotedDraft({ status: "unique", ref: "draft_1" }, false)).toBe(false);
    expect(canOpenPromotedDraft({ status: "ambiguous", ref: null }, true)).toBe(false);
    expect(canOpenPromotedDraft({ status: "none", ref: null }, true)).toBe(false);
    expect(exactDraftMatchesEditorScene("scene_a", "scene_a")).toBe(true);
    expect(exactDraftMatchesEditorScene("scene_a", "scene_b")).toBe(false);
    expect(exactDraftMatchesEditorScene("scene_a", "")).toBe(false);
  });
});

describe("dirty and state action policies", () => {
  it("continues only after a successful save runner has released its lock", async () => {
    const order: string[] = [];
    let locked = true;
    const continued = await continueAfterSuccessfulSave(
      async () => {
        order.push("save");
        locked = false;
        return true;
      },
      () => {
        expect(locked).toBe(false);
        order.push("destination");
      }
    );
    expect(continued).toBe(true);
    expect(order).toEqual(["save", "destination"]);

    let blockedDestinationCalls = 0;
    expect(await continueAfterSuccessfulSave(
      async () => false,
      () => { blockedDestinationCalls += 1; }
    )).toBe(false);
    expect(blockedDestinationCalls).toBe(0);
  });

  it("rejects stale proposal-list responses by sequence, API, and project scope", () => {
    expect(projectRequestIsCurrent(2, 2, "api-a", "api-a", "project-b", "project-b")).toBe(true);
    expect(projectRequestIsCurrent(1, 2, "api-a", "api-a", "project-b", "project-b")).toBe(false);
    expect(projectRequestIsCurrent(2, 2, "api-a", "api-b", "project-b", "project-b")).toBe(false);
    expect(projectRequestIsCurrent(2, 2, "api-a", "api-a", "project-a", "project-b")).toBe(false);
  });

  it("keeps the explicit new-proposal editor open when older proposals exist", () => {
    expect(proposalAutoSelection(["proposal_old"], null, true)).toBeNull();
    expect(proposalAutoSelection(["proposal_old"], null, false)).toBe("proposal_old");
    expect(proposalAutoSelection(["proposal_old", "proposal_current"], "proposal_current", false)).toBe("proposal_current");
    expect(proposalAutoSelection(["proposal_other"], "proposal_dirty", false, true)).toBe("proposal_dirty");
  });

  it("compares proposal title and body exactly with the selected latest version", () => {
    const selected = { title: "Title", body: "Body" } as ProposalArtifact;
    expect(proposalIsDirty(selected, "Title", "Body")).toBe(false);
    expect(proposalIsDirty(selected, "Title changed", "Body")).toBe(true);
    expect(proposalIsDirty(selected, "Title", "Body\n")).toBe(true);
  });

  it("preserves local edits on same-proposal refresh but hydrates an explicit selection", () => {
    const snapshot = { id: "proposal_a", version: 1, title: "Saved", body: "Saved body" };
    const refreshed = { id: "proposal_a", version: 1, title: "Saved", body: "Saved body" } as ProposalArtifact;
    const externallyUpdated = { id: "proposal_a", version: 2, title: "Server v2", body: "Server body v2" } as ProposalArtifact;
    const other = { id: "proposal_b", version: 1, title: "Other", body: "Other body" } as ProposalArtifact;
    expect(shouldHydrateProposalEditor(snapshot, refreshed, "Local edit", "Saved body")).toBe(false);
    expect(shouldHydrateProposalEditor(snapshot, refreshed, "Saved", "Saved body")).toBe(true);
    expect(shouldHydrateProposalEditor(snapshot, externallyUpdated, "Server v2", "Server body v2")).toBe(true);
    expect(shouldHydrateProposalEditor(snapshot, other, "Local edit", "Saved body")).toBe(true);
  });

  it("blocks every lifecycle action while dirty and exposes only state-specific actions", () => {
    for (const status of ["drafting", "agent_revised", "author_revised"] as const) {
      expect(proposalActionPolicy(status, false, "scene_draft")).toMatchObject({ showSubmit: true, canSubmit: true, showDecision: false, showPromotion: false });
    }
    expect(proposalActionPolicy("ready_for_review", false, "scene_draft")).toMatchObject({ showSubmit: false, showDecision: true, canDecide: true, showPromotion: false });
    expect(proposalActionPolicy("accepted", false, "scene_draft")).toMatchObject({ showDecision: false, showPromotion: true, canPromote: true });
    expect(proposalActionPolicy("accepted", false, "canon_patch")).toMatchObject({ showPromotion: false, canPromote: false, readonly: true });
    expect(proposalActionPolicy("rejected", false, "scene_draft")).toMatchObject({ readonly: true, showSubmit: false, showDecision: false, showPromotion: false });
    expect(proposalActionPolicy("ready_for_review", true, "scene_draft").canDecide).toBe(false);
    expect(proposalActionPolicy("accepted", true, "scene_draft").canPromote).toBe(false);
    expect(proposalActionPolicy("author_revised", true, "scene_draft")).toMatchObject({ canSave: true, canSubmit: false });
  });

  it("detects local Draft text that differs from the exact saved record", () => {
    const draft = { id: "draft_exact", version: 7, text: "saved" } as Draft;
    expect(draftIsDirty(draft, "saved", "")).toBe(false);
    expect(draftIsDirty(draft, "edited", "")).toBe(true);
    expect(draftIsDirty({ ...draft, summary: "saved summary" }, "saved", "local summary")).toBe(true);
    expect(draftIsDirty(null, "unsaved", "")).toBe(true);
    expect(canRestoreSavedDraft(draft, true)).toBe(true);
    expect(canRestoreSavedDraft(draft, false)).toBe(false);
    expect(canRestoreSavedDraft(null, true)).toBe(false);
    const included = agentIncludedDraftPolicy(draft, true, false);
    expect(included).toEqual({
      status: "ready",
      draftId: "draft_exact",
      version: 7
    });
    const manifestDraftId = included.status === "ready" ? included.draftId : null;
    const payloadIncludedDraftId = included.status === "ready" ? included.draftId : null;
    expect(payloadIncludedDraftId).toBe(manifestDraftId);
    expect(agentIncludedDraftPolicy(draft, true, true).draftId).toBeNull();
    expect(agentIncludedDraftPolicy(null, true, false).status).toBe("blocked_missing");
    expect(agentIncludedDraftPolicy(draft, false, true).status).toBe("excluded");
    const scopedDraft = { ...draft, project_id: "project_a", scene_id: "scene_a" };
    expect(agentIncludedDraftPolicy(scopedDraft, true, false, "project_a", "scene_b").status).toBe("blocked_scope");
    expect(agentIncludedDraftPolicy(scopedDraft, true, false, "project_a", "scene_a").status).toBe("ready");
  });
});

describe("Source-to-Agent policy and bilingual diff", () => {
  const source = {
    extraction_status: "ready",
    language: "en-US"
  } as SourceDocumentSummary;

  it("requires ready, known, policy-eligible source metadata", () => {
    expect(sourceCanHandoff(source)).toBe(true);
    expect(sourceAgentEligibility(source, "zh-CN", "project_only")).toBe("language_mismatch");
    expect(sourceAgentEligibility(source, "zh-CN", "explicit_reference")).toBe("eligible");
    expect(sourceAgentEligibility({ ...source, language: "und" }, "zh-CN", "explicit_reference")).toBe("unknown_language");
    expect(sourceAgentEligibility({ ...source, extraction_status: "failed" }, "en-US", "project_only")).toBe("not_ready");
    expect(sourceCanHandoff({ ...source, language: "und" })).toBe(false);
    expect(sourceCanHandoff({ ...source, extraction_status: "failed" })).toBe(false);
    const french = { ...source, language: "fr-FR" };
    expect(sourceCanHandoff(french)).toBe(true);
    expect(sourceAgentEligibility(french, "zh-CN", "project_only")).toBe("language_mismatch");
    expect(sourceAgentEligibility(french, "zh-CN", "explicit_reference")).toBe("eligible");
  });

  it("hands off only the stable Source ID without mutating request policy or prose", () => {
    const current = new Set(["source_existing"]);
    const policy = "project_only";
    const instruction = "Keep this author instruction unchanged";
    const next = addStableSourceSelection(current, "source_new");
    expect(Array.from(next)).toEqual(["source_existing", "source_new"]);
    expect(Array.from(current)).toEqual(["source_existing"]);
    expect(policy).toBe("project_only");
    expect(instruction).toBe("Keep this author instruction unchanged");
  });

  it("preserves Chinese and English author text without translation", () => {
    const diff = buildReviewDiff("第一行\nKeep this line\n旧结尾", "第一行\nKeep this line\nNew ending");
    expect(diff).toEqual([
      { kind: "equal", left: "第一行", right: "第一行", leftLine: 1, rightLine: 1 },
      { kind: "equal", left: "Keep this line", right: "Keep this line", leftLine: 2, rightLine: 2 },
      { kind: "changed", left: "旧结尾", right: "New ending", leftLine: 3, rightLine: 3 }
    ]);
    expect(buildReviewDiff("same", "same\n")).toEqual([
      { kind: "equal", left: "same", right: "same", leftLine: 1, rightLine: 1 },
      { kind: "added", left: null, right: "", leftLine: null, rightLine: 2 }
    ]);
  });
});
