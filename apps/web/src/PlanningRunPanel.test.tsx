import { webcrypto } from "node:crypto";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ProposalArtifact } from "./api";
import { activateLocale } from "./localization";
import { PlanningRunProgress, PlanningRestartControls, planningRunOptionLabel } from "./PlanningRunPanel";
import { PlanningRunReview } from "./PlanningRunReview";
import { PlanningBundlePreview } from "./PlanningBundlePreview";
import { planningRunCopyBlueprintBody, copyPlanningRunBlueprint, mergePlanningRunRecords, parsePlanningBook, parsePlanningBranch, pinnedPlanningArtifactMatches, planningRunInputValid, planningRunCreateRequest, planningRunNeedsUncertainRetry, planningRunReady, planningRunResumeBody, planningRunRecheckBody, type PlanningArtifactRef, type PlanningBookBundle, type PlanningRun } from "./planningRuns";
const ref: PlanningArtifactRef = { id: "branch-a", version: 2, body_sha256: "a".repeat(64) };
function run(): PlanningRun { return { id: "run-a", project_id: "book", version: 7, status: "awaiting_review", stage: "done", request: { instruction: "设计一个完整故事", target_length: 500000, volume_count: 1, chapters_per_volume: 2, scenes_per_chapter: 1, batch_size: 2, max_calls: 80, max_repairs_per_step: 2 }, output_language: "zh-CN", canon_fingerprint: "f".repeat(64), calls_reserved: 7, max_calls: 80, stop_requested: false, pause_reason: null, pending_call: null, steps: [ { index: 0, phase: "blueprint", volume_index: null, chapter_start: null, chapter_count: null, status: "passed", proposal_ref: ref, review_id: "review-blueprint", repairs: 1 }, { index: 1, phase: "expansion", volume_index: 1, chapter_start: 1, chapter_count: 2, status: "passed", proposal_ref: { ...ref, id: "branch-b" }, review_id: "review-expansion", repairs: 0 } ], final_review_id: "review-book", bundle_proposal_id: "bundle", created_at: "2026-10-25", updated_at: "2026-10-25" }; }
function proposal(body: unknown): ProposalArtifact { return { id: "bundle", contract_version: "proposal_artifact_v1", project_id: "book", artifact_type: "outline_draft", status: "accepted", content_language: "zh-CN", title: "整本规划包", body_format: "structured_json", body: JSON.stringify(body), version: 4, source_refs: [], target_refs: [], derived_refs: [], provenance: { created_by: "author", created_via: "manual" }, review_decision: { status: "accepted" }, created_at: "2026-10-25", updated_at: "2026-10-25" }; }
function bundleBody(): PlanningBookBundle { return { schema: "longform_book_bundle_v1", run_id: "run-a", project_id: "book", output_language: "zh-CN", canon_fingerprint: "f".repeat(64), blueprint_ref: ref, expansion_refs: [{ ...ref, id: "branch-b" }], final_review_id: "review-book" }; }
beforeEach(async () => { await activateLocale("zh-CN"); });
describe("bounded whole-book planning run controls", () => {
  it("labels runs with UI-localized browser dates and readable ordinals rather than internal IDs", async () => {
    const value = { ...run(), updated_at: "2026-10-25T13:00:00Z", output_language: "en-US" };
    const chinese = planningRunOptionLabel(value, 2); expect(chinese).toContain("规划运行 2"); expect(chinese).toContain("等待人工审阅"); expect(chinese).not.toContain(value.id); expect(chinese).not.toContain("T13:00");
    await activateLocale("en-US"); const english = planningRunOptionLabel({ ...value, output_language: "zh-CN" }, 3); expect(english).toContain("Planning run 3"); expect(english).toContain("Awaiting human review"); expect(english).not.toContain(value.id); expect(english).not.toContain("T13:00");
  });
  it("validates blueprint, batch, call and repair budgets before a paid create action", () => {
    const request = run().request; expect(planningRunInputValid(request)).toBe(true);
    for (const patch of [{ instruction: " " }, { target_length: 5000 }, { volume_count: 13 }, { batch_size: 0 }, { batch_size: 6 }, { max_calls: 129 }, { max_calls: 0 }, { max_repairs_per_step: 3 }, { max_repairs_per_step: -1 }, { max_calls: 1.5 }]) expect(planningRunInputValid({ ...request, ...patch })).toBe(false);
  });
  it("never calls a run complete while steps, reports, final check or bundle are missing", () => {
    const value = run(); expect(planningRunReady(value)).toBe(true);
    expect(planningRunReady({ ...value, stage: "book_review" })).toBe(false);
    expect(planningRunReady({ ...value, status: "paused" })).toBe(false);
    expect(planningRunReady({ ...value, final_review_id: null })).toBe(false);
    expect(planningRunReady({ ...value, bundle_proposal_id: null })).toBe(false);
    expect(planningRunReady({ ...value, steps: [] })).toBe(false);
    for (const patch of [{ status: "generated" as const }, { review_id: null }, { proposal_ref: null }]) expect(planningRunReady({ ...value, steps: [{ ...value.steps[0], ...patch }] })).toBe(false);
  });
  it("requires explicit consent to retry uncertain paid work with the exact run version", () => {
    const value = { ...run(), status: "paused" as const, pause_reason: "uncertain_call", pending_call: { id: "pending", task: "planning" as const, operation: "generate", step_index: 1 } };
    expect(planningRunNeedsUncertainRetry(value)).toBe(true);
    expect(planningRunResumeBody(value, false)).toBeNull();
    expect(planningRunResumeBody(value, true)).toEqual({ expected_version: 7, retry_uncertain_call: true });
    expect(planningRunResumeBody({ ...value, pause_reason: "canon_changed" }, true)).toBeNull();
    expect(planningRunResumeBody({ ...value, pause_reason: "connection_changed" }, true)).toBeNull();
    expect(planningRunResumeBody({ ...value, pause_reason: "source_changed" }, true)).toBeNull();
    expect(planningRunResumeBody({ ...value, status: "running" }, true)).toBeNull();
  });
  it("raises an exhausted call budget only through explicit resume input", () => {
    const value = { ...run(), status: "paused" as const, pause_reason: "call_budget", calls_reserved: 80 };
    expect(planningRunResumeBody(value, false)).toBeNull();
    expect(planningRunResumeBody(value, false, 100)).toEqual({ expected_version: 7, retry_uncertain_call: false, max_calls: 100 });
    expect(planningRunResumeBody(value, false, 129)).toBeNull(); expect(planningRunResumeBody(value, false, 70)).toBeNull();
  });
  it("pins seed ID/version and copies the original flat request without invisible or changed inputs", () => {
    const original = run().request;
    const body = planningRunCreateRequest({ ...original, instruction: "different visible edit", target_length: 10000 }, 5, 90, 1, { id: "designed-blueprint", version: 6, request: original });
    expect(body).toMatchObject({ seed_blueprint_id: "designed-blueprint", seed_blueprint_version: 6, instruction: original.instruction, target_length: 500000, batch_size: 5, max_calls: 90 });
    expect(planningRunInputValid(body)).toBe(true);
    expect(planningRunInputValid({ ...body, seed_blueprint_version: undefined })).toBe(false);
    const plain = planningRunCreateRequest({ ...original, unexpected_secret: "never-copy" } as typeof original, 5, 80, 2);
    expect(plain).not.toHaveProperty("seed_blueprint_id"); expect(plain).not.toHaveProperty("unexpected_secret");
  });
  it("restarts a selected stage only on explicit instruction and preserves the total call cap", () => {
    const value = { ...run(), status: "paused" as const, pause_reason: "repair_limit" };
    expect(planningRunResumeBody(value, false, 80)).toEqual({ expected_version: 7, retry_uncertain_call: false });
    expect(planningRunResumeBody(value, false, 80, 1, "只修正时间冲突")).toEqual({ expected_version: 7, retry_uncertain_call: false, restart_from_step: 1, revision_instruction: "只修正时间冲突" });
    expect(planningRunResumeBody(value, false, 80, 0)).toEqual({ expected_version: 7, retry_uncertain_call: false, restart_from_step: 0 });
    expect(planningRunResumeBody(value, false, 80, null, "隐式改写")).toBeNull();
    expect(planningRunResumeBody(value, false, 80, 99, "错误阶段")).toBeNull();
    expect(planningRunResumeBody(value, false, 80, 0, "字".repeat(12001))).toBeNull();
  });
  it("rechecks only the current exact result without rewriting or resetting repair counts", () => {
    const value = { ...run(), status: "paused" as const, pause_reason: "repair_limit", steps: [{ ...run().steps[0], status: "needs_revision" as const, repairs: 2 }, run().steps[1]] };
    const before = JSON.stringify(value);
    expect(planningRunRecheckBody(value)).toEqual({ expected_version: 7, recheck_current_step: true });
    expect(JSON.stringify(value)).toBe(before);
    expect(planningRunRecheckBody({ ...value, pending_call: { id: "uncertain", task: "continuity", operation: "review", step_index: 0 } })).toBeNull();
    expect(planningRunRecheckBody({ ...value, pause_reason: "uncertain_call" })).toBeNull();
    expect(planningRunRecheckBody({ ...value, status: "running" })).toBeNull();
    expect(planningRunRecheckBody({ ...value, calls_reserved: 80 })).toBeNull();
    expect(planningRunRecheckBody({ ...value, steps: [{ ...value.steps[0], proposal_ref: null }] })).toBeNull();
    expect(planningRunRecheckBody({ ...value, steps: [{ ...value.steps[0], proposal_ref: { ...ref, body_sha256: "invalid" } }] })).toBeNull();
    expect(planningRunRecheckBody({ ...value, steps: run().steps })).toBeNull();
  });
  it("copies only a passed exact blueprint from an idle unpublished run", () => {
    const value = { ...run(), status: "paused" as const, pause_reason: "connection_changed" };
    const before = JSON.stringify(value);
    expect(planningRunCopyBlueprintBody(value)).toEqual({ expected_version: 7 });
    expect(JSON.stringify(value)).toBe(before);
    expect(planningRunCopyBlueprintBody(run())).toEqual({ expected_version: 7 });
    for (const status of ["queued", "running", "completed"] as const) expect(planningRunCopyBlueprintBody({ ...value, status })).toBeNull();
    expect(planningRunCopyBlueprintBody({ ...value, pause_reason: "uncertain_call" })).toBeNull();
    expect(planningRunCopyBlueprintBody({ ...value, pending_call: { id: "pending", task: "continuity", operation: "review", step_index: 1 } })).toBeNull();
    expect(planningRunCopyBlueprintBody({ ...value, steps: [{ ...value.steps[0], status: "needs_revision" }] })).toBeNull();
    expect(planningRunCopyBlueprintBody({ ...value, steps: [{ ...value.steps[0], review_id: null }] })).toBeNull();
  });
  it("copy uses only the local copy endpoint and never starts or resumes a paid run", async () => {
    const value = { ...run(), status: "paused" as const, pause_reason: "connection_changed" };
    const copied = { ...proposal(bundleBody()), id: "copy-new", status: "agent_revised" as const, version: 1 };
    const fetchMock = vi.fn(async (_url: RequestInfo | URL, _init?: RequestInit) => new Response(JSON.stringify({ proposal: copied }), { status: 200 })); vi.stubGlobal("fetch", fetchMock);
    expect(await copyPlanningRunBlueprint("http://localhost", "book", value)).toEqual(copied);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("http://localhost/projects/book/planning-runs/run-a/copy-blueprint");
    expect(JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string)).toEqual({ expected_version: 7 });
    await expect(copyPlanningRunBlueprint("http://localhost", "foreign", value)).rejects.toThrow();
    expect(fetchMock).toHaveBeenCalledTimes(1); vi.unstubAllGlobals();
  });
  it("retains later outputs only on an explicit restart and requires instructions for full revision", () => {
    const value = { ...run(), status: "paused" as const, pause_reason: "repair_limit" };
    const retained = { preserve_later_outputs: true, revision_mode: "targeted" as const };
    expect(planningRunResumeBody(value, false, 80, null, "", retained)).toBeNull();
    expect(planningRunResumeBody(value, false, 80, 0, "", retained)).toEqual({ expected_version: 7, retry_uncertain_call: false, restart_from_step: 0, preserve_later_outputs: true, revision_mode: "targeted" });
    const full = { preserve_later_outputs: true, revision_mode: "full" as const };
    expect(planningRunResumeBody(value, false, 80, 0, " ", full)).toBeNull();
    expect(planningRunResumeBody(value, false, 80, 0, "完整修订当前蓝图", full)).toEqual({ expected_version: 7, retry_uncertain_call: false, restart_from_step: 0, revision_instruction: "完整修订当前蓝图", preserve_later_outputs: true, revision_mode: "full" });
    expect(planningRunResumeBody(value, false, 80)).toEqual({ expected_version: 7, retry_uncertain_call: false });
    const uncertain = { ...value, pause_reason: "uncertain_call" };
    expect(planningRunResumeBody(uncertain, false, 80, 0, "定点修订", retained)).toBeNull();
    expect(planningRunResumeBody(uncertain, true, 80, 0, "定点修订", retained)?.retry_uncertain_call).toBe(true);
  });
  it("shows chosen-restart recovery controls without triggering actions or inheriting old passes", () => {
    const onMode = vi.fn(); const onPreserve = vi.fn(); const onInstruction = vi.fn();
    const html = renderToStaticMarkup(<PlanningRestartControls busy={false} mode="targeted" preserveLater={false} instruction="" onMode={onMode} onPreserve={onPreserve} onInstruction={onInstruction} />);
    expect(html).toContain('value="targeted" selected=""'); expect(html).toContain('value="regenerate" selected=""'); expect(html).toContain("保留后续规划并重新检查");
    expect(onMode).not.toHaveBeenCalled(); expect(onPreserve).not.toHaveBeenCalled(); expect(onInstruction).not.toHaveBeenCalled();
    const full = renderToStaticMarkup(<PlanningRestartControls busy={false} mode="full" preserveLater instruction="" onMode={onMode} onPreserve={onPreserve} onInstruction={onInstruction} />);
    expect(full).toContain("完整修订必须填写明确要求"); expect(full).toContain("必须重新付费审阅，不继承旧通过报告");
    const value = run(); value.steps[1] = { ...value.steps[1], status: "pending", proposal_ref: null, review_id: null, retained_output_ref: { ...ref, id: "original-later-plan" } };
    expect(planningRunReady(value)).toBe(false);
    const progress = renderToStaticMarkup(<PlanningRunProgress run={value} finalReviewReady onOpenBundle={() => undefined} />);
    expect(progress).toContain("已保留来源，待重新校验与审阅"); expect(progress).toContain("保留的原始来源（只读）: original-later-plan"); expect(progress).not.toContain('>审阅整本规划包</button>');
  });
  it("does not let an older poll or foreign project replace an exact-version mutation response", () => {
    const value = run(); const records = [value];
    expect(mergePlanningRunRecords(records, { ...value, version: 6, status: "running" }, "book")).toBe(records);
    expect(mergePlanningRunRecords(records, { ...value, version: 8, project_id: "other" }, "book")).toBe(records);
    expect(mergePlanningRunRecords(records, { ...value, version: 8, status: "completed" }, "book")[0].status).toBe("completed");
  });
  it("shows staged work and gaps until the whole-book report is verified", () => {
    let html = renderToStaticMarkup(<PlanningRunProgress run={run()} onOpenBundle={() => undefined} />);
    expect(html).toContain("暂存规划，不是正典"); expect(html).toContain("规划尚未完成"); expect(html).not.toContain('>审阅整本规划包</button>');
    html = renderToStaticMarkup(<PlanningRunProgress run={run()} finalReviewReady onOpenBundle={() => undefined} />);
    expect(html).toContain("全部阶段及整本检查通过"); expect(html).toContain('>审阅整本规划包</button>'); expect(html).toContain("7 / 80");
  });
});
describe("pinned noncanon bundle review", () => {
  it("recognizes only a project/language-scoped exact manifest and rejects duplicate branch refs", () => {
    expect(parsePlanningBook(proposal(bundleBody()))?.final_review_id).toBe("review-book");
    for (const patch of [{ project_id: "other" }, { output_language: "en-US" }, { final_review_id: "" }, { expansion_refs: [] }, { expansion_refs: [ref] }]) expect(parsePlanningBook(proposal({ ...bundleBody(), ...patch }))).toBeNull();
  });
  it("checks exact version and checksum, without latest-proposal fallback", async () => {
    vi.stubGlobal("crypto", webcrypto);
    const value = proposal(bundleBody()); value.id = ref.id; value.version = ref.version;
    const hash = await webcrypto.subtle.digest("SHA-256", new TextEncoder().encode(value.body));
    const pinned = { ...ref, body_sha256: Array.from(new Uint8Array(hash), (n) => n.toString(16).padStart(2, "0")).join("") };
    expect(await pinnedPlanningArtifactMatches(value, pinned, "book")).toBe(true);
    expect(await pinnedPlanningArtifactMatches({ ...value, version: 3 }, pinned, "book")).toBe(false);
    expect(await pinnedPlanningArtifactMatches({ ...value, body: value.body + " " }, pinned, "book")).toBe(false);
    expect(await pinnedPlanningArtifactMatches(value, pinned, "other")).toBe(false);
    vi.unstubAllGlobals();
  });
  it("distinguishes a branch artifact from an individually executable longform plan", () => {
    const value = proposal({ schema: "longform_branch_plan_v1", run_id: "run-a", project_id: "book", output_language: "zh-CN", canon_fingerprint: "f".repeat(64), step_index: 1, phase: "expansion", blueprint_ref: ref, previous_refs: [], blueprint: null, expansion: { volume_index: 1, chapter_start: 1, chapters: [{ index: 1, title: "来信", summary: "主角收到信", purpose: "引出冲突", target_length: 500000, scenes: [{ id: "v01_c001_s01", title: "来信", summary: "一封信带来线索", goal: "寻找寄信人", conflict: "地址被抹去", outcome: "发现暗记", emotional_turn: "警觉", pov_character_id: "hero", location_id: "city", required_characters: ["hero"], timeline_position: "第一日", target_length: 500000, causal_dependencies: [], foreshadowing_seed_ids: [], foreshadowing_payoff_ids: [] }] }] } });
    expect(parsePlanningBranch(value, "run-a")?.expansion?.chapters[0].title).toBe("来信");
    expect(parsePlanningBranch(value, "another-run")).toBeNull();
    expect(parsePlanningBook(value)).toBeNull();
  });
  it("uses pinned whole-book review language rather than claiming a manifest-only check", async () => {
    let html = renderToStaticMarkup(<PlanningBundlePreview apiBase="http://localhost" bundle={bundleBody()} />);
    expect(html).toContain("尚未生成的正文未检查"); expect(html).toContain("不能保证发现所有矛盾");
    await activateLocale("en-US"); html = renderToStaticMarkup(<PlanningRunReview apiBase="http://localhost" projectId="book" runId="run-a" reviewId="review-book" />);
    expect(html).toContain("scene summaries/outcomes"); expect(html).toContain("unwritten prose is not checked"); expect(html).toContain("does not replace author approval");
  });
});
