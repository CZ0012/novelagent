import { describe, expect, it } from "vitest";
import type { ProposalArtifact } from "./api";
import { compositionApplicationRecorded, parseComposition, canApplyComposition } from "./CompositionPanel";

function proposal(overrides: Record<string, unknown> = {}): ProposalArtifact {
  return { contract_version: "proposal_artifact_v1", title: "审阅草稿", target_refs: [], source_refs: [], provenance: { created_by: "agent", created_via: "llm" }, version: 1, review_decision: { status: "accepted" }, created_at: "2026-09-25T00:00:00Z", updated_at: "2026-09-25T00:00:00Z", id: "proposal-a", project_id: "project-a", artifact_type: "outline_draft", status: "accepted", content_language: "zh-CN", body_format: "structured_json", derived_refs: [], body: JSON.stringify({ schema: "manuscript_composition_v1", project_id: "project-a", output_language: "zh-CN", scope: "chapter", volume_title: null, volume_index: 1, base_chapter_index: 0, chapters: [{ title: "第一章", summary: "发现一封信。", purpose: "引出谜团。", scenes: [{ title: "来信", summary: "主角打开信封。", goal: "找到来信者。", conflict: "地址已被抹去。", prose: "雾从码头涌来。\n\n他看了一眼信封。" }] }], ...overrides }) };
}
describe("reviewable manuscript composition", () => {
  it("recognizes the exact schema and supports inherited volume titles for a new chapter", () => {
    expect(parseComposition(proposal())?.chapters[0].scenes[0].prose).toContain("\n\n");
    expect(parseComposition(proposal({ volume_title: "群星" }))?.volume_title).toBe("群星");
    expect(parseComposition(proposal({ scope: "volume", volume_title: "群星" }))?.scope).toBe("volume");
  });
  it.each([{ schema: "other" }, { project_id: "another-project" }, { output_language: "en-US" }, { output_language: "fr-FR" }, { volume_index: 0 }, { base_chapter_index: -1 }, { base_chapter_index: 1.5 }, { scope: "volume", volume_title: null }, { extra: "unexpected" }])("does not expose application for invalid or mismatched scope %j", (patch) => {
    expect(parseComposition(proposal(patch))).toBeNull();
  });
  it("rejects unknown fields and oversized scene prose, allowing Unicode length in code points", () => {
    const parsed = parseComposition(proposal())!;
    parsed.chapters[0].scenes[0].prose = "🌟".repeat(8000);
    const p = proposal(); p.body = JSON.stringify(parsed); expect(parseComposition(p)).not.toBeNull();
    parsed.chapters[0].scenes[0].prose += "星";
    p.body = JSON.stringify(parsed); expect(parseComposition(p)).toBeNull();
    const fresh = parseComposition(proposal())!;
    p.body = JSON.stringify({ ...fresh, chapters: [{ ...fresh.chapters[0], private_reference: "unexpected" }] });
    expect(parseComposition(p)).toBeNull();
  });
  it("requires all unique graph and Draft receipts before calling a proposal applied", () => {
    const p = proposal(); const prefix = "a".repeat(20);
    p.derived_refs = [{ kind: "graph_node", ref: `chapter_cmp_${prefix}_1` }, { kind: "graph_node", ref: `scene_cmp_${prefix}_1_1` }, { kind: "draft", ref: `draft_cmp_${prefix}_1` }];
    expect(compositionApplicationRecorded(p)).toBe(true);
    p.derived_refs.pop(); expect(compositionApplicationRecorded(p)).toBe(false);
    p.derived_refs.push({ ...p.derived_refs[0] }); expect(compositionApplicationRecorded(p)).toBe(false);
    p.status = "drafting"; expect(compositionApplicationRecorded(p)).toBe(false);
  });
  it("exposes application for the latest accepted composition while rejecting dirty, foreign, or unreviewed proposals", () => {
    const p = proposal();
    expect(canApplyComposition(p, false, "project-a")).toBe(true);
    expect(canApplyComposition(p, true, "project-a")).toBe(false);
    expect(canApplyComposition(p, false, "other-project")).toBe(false);
    p.status = "ready_for_review";
    expect(canApplyComposition(p, false, "project-a")).toBe(false);
  });
  it("keeps generic outline drafts non-executable", () => {
    const p = proposal(); p.body = "A chapter outline"; p.body_format = "plain_text";
    expect(parseComposition(p)).toBeNull(); expect(compositionApplicationRecorded(p)).toBe(false);
  });
});
