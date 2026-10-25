import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it } from "vitest";
import type { ProposalArtifact } from "./api";
import { activateLocale } from "./localization";
import { GenerationReviewPanel, reviewAllowsAdoption, reviewAllowsPlanApplication, reviewMatchesTarget, proposalSemanticReviewBlocked, type GenerationReviewResult, type GenerationReviewTarget } from "./GenerationReviewPanel";
const target: GenerationReviewTarget = { target_type: "proposal", target_id: "proposal-a", expected_version: 4 };
function result(): GenerationReviewResult {
  return { current: true, report: { contract_version: "generation_review_v1", id: "review-a", project_id: "book", target_type: "proposal", target_id: "proposal-a", target_version: 4, output_language: "zh-CN", target_text_sha256: "text", canon_fingerprint: "canon", canon_evidence_fingerprint: "evidence", style_fingerprint: "style", status: "pass", summary: "已检查所选范围", issues: [], dimensions_checked: ["world_rule"], coverage: { method: "semantic_model", canon_complete: true, target_complete: true, scope: "scene", omitted_unrelated_facts: 3, missing_context: [], limitations: ["仅检查当前场景"] }, created_at: "2026-10-25" } };
}
beforeEach(async () => { await activateLocale("zh-CN"); });
describe("exact semantic review adoption boundary", () => {
  it("requires server freshness and exact project/type/ID/version identity", () => {
    expect(reviewMatchesTarget(result(), "book", target)).toBe(true);
    expect(reviewMatchesTarget({ ...result(), current: false }, "book", target)).toBe(false);
    expect(reviewMatchesTarget(result(), "other", target)).toBe(false);
    expect(reviewMatchesTarget(result(), "book", { ...target, target_type: "draft" })).toBe(false);
    expect(reviewMatchesTarget(result(), "book", { ...target, target_id: "other" })).toBe(false);
    expect(reviewMatchesTarget(result(), "book", { ...target, expected_version: 5 })).toBe(false);
    expect(reviewMatchesTarget(result(), "book", null)).toBe(false);
  });
  it("never authorizes adoption using blocked, stale, inconclusive or incomplete coverage", () => {
    expect(reviewAllowsAdoption(result(), "book", target)).toBe(true);
    expect(reviewAllowsAdoption(null, "book", target)).toBe(false);
    for (const status of ["needs_revision", "blocked", "inconclusive"] as const) { const item = result(); item.report.status = status; expect(reviewAllowsAdoption(item, "book", target)).toBe(false); }
    for (const field of ["canon_complete", "target_complete"] as const) { const item = result(); item.report.coverage[field] = false; expect(reviewAllowsAdoption(item, "book", target)).toBe(false); }
    expect(reviewAllowsAdoption(result(), "book", { ...target, expected_version: 5 })).toBe(false);
  });
  it("requires semantic review after acceptance rewrites proposal provenance to manual", () => {
    const accepted = { id: "proposal-a", project_id: "book", artifact_type: "scene_draft", status: "accepted", version: 4, provenance: { created_by: "author", created_via: "manual" } } as ProposalArtifact;
    expect(proposalSemanticReviewBlocked(accepted, null, "book", true)).toBe(true);
    expect(proposalSemanticReviewBlocked(accepted, result(), "book", true)).toBe(false);
    expect(proposalSemanticReviewBlocked({ ...accepted, version: 5 }, result(), "book", true)).toBe(true);
    expect(proposalSemanticReviewBlocked(accepted, { ...result(), current: false }, "book", true)).toBe(true);
    const blocked = result(); blocked.report.status = "blocked";
    expect(proposalSemanticReviewBlocked(accepted, blocked, "book", false)).toBe(true);
    expect(proposalSemanticReviewBlocked(accepted, null, "book", false)).toBe(false);
  });
  it("requires plan-purpose complete fresh coverage for first plan application", () => {
    const item = result(); expect(reviewAllowsPlanApplication(item, "book", target)).toBe(false);
    item.report.purpose = "plan"; item.report.coverage.scope = "plan";
    expect(reviewAllowsPlanApplication(item, "book", target)).toBe(true);
    expect(reviewAllowsPlanApplication(item, "book", { ...target, expected_version: 5 })).toBe(false);
    item.current = false; expect(reviewAllowsPlanApplication(item, "book", target)).toBe(false);
    item.current = true; item.report.status = "needs_revision"; expect(reviewAllowsPlanApplication(item, "book", target)).toBe(false);
  });
  it("renders explicit paid review and keeps missing or dirty target actions unavailable", () => {
    const props = { apiBase: "http://localhost:8000", projectId: "book", target, dirty: true, busy: false, canGenerate: true, modelReady: true, modelLabel: "continuity-model", execute: async () => undefined, onReport: () => undefined };
    const html = renderToStaticMarkup(<GenerationReviewPanel {...props} />);
    expect(html).toContain("确切已保存版本"); expect(html).toContain("请先保存或放弃编辑"); expect(html).toMatch(/class="primary" disabled=""/); expect(html).toContain("continuity-model");
    expect(renderToStaticMarkup(<GenerationReviewPanel {...props} target={null} dirty={false} />)).toContain("打开已保存正文");
  });
  it("offers natural state extraction only for an exact saved Draft and keeps dirty sends blocked", () => {
    const props = { apiBase: "http://localhost", projectId: "book", target: { target_type: "draft" as const, target_id: "draft-a", expected_version: 2, scene_id: "scene-a" }, dirty: true, busy: false, canGenerate: true, modelReady: true, modelLabel: "review", extractionReady: true, extractionModelLabel: "extract", onExtract: () => undefined, execute: async () => undefined, onReport: () => undefined };
    const html = renderToStaticMarkup(<GenerationReviewPanel {...props} />); expect(html).toContain("只生成待审协作草稿"); expect(html).toContain('disabled="">从已保存正文提取状态变化');
    expect(renderToStaticMarkup(<GenerationReviewPanel {...props} target={target} />)).not.toContain('class="natural-state-extraction"');
  });
  it("renders independent rule/model language in English", async () => {
    await activateLocale("en-US"); const html = renderToStaticMarkup(<GenerationReviewPanel apiBase="http://localhost" projectId="book" target={target} dirty={false} busy={false} canGenerate={false} modelReady={false} modelLabel="missing" execute={async () => undefined} onReport={() => undefined} />);
    expect(html).toContain("Semantic review"); expect(html).toContain("Neither guarantees finding every contradiction"); expect(html).toMatch(/class="primary" disabled=""/);
  });
});
