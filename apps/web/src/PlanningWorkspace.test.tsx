import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it } from "vitest";
import type { ProposalArtifact } from "./api";
import { activateLocale } from "./localization";
import { LongformPreview, PlanningWorkspace } from "./PlanningWorkspace";
import { longformApplied, nextPlanningBatch, parseLongformPlan, type LongformBlueprint } from "./longformPlanning";

const blueprint: LongformBlueprint = {
  synopsis: "一名送信人发现城市失去了记忆。", world_rules: [{ id: "rule_memory", domain: "记忆", rule: "遗忘需要付出代价。" }], entities: [{ id: "hero", kind: "Character", name: "林舟", description: "送信人。" }, { id: "city", kind: "Location", name: "雾城", description: "记忆消失的城市。" }],
  character_arcs: [{ character_id: "hero", initial_state: "回避过去", desire: "找回记忆", conflict: "信件揭开隐瞒", turning_points: [{ volume_index: 1, change: "选择追索" }], final_state: "承担责任" }],
  style_brief: { name: "克制叙述", pov: "第三人称", tense: "过去", tone: "冷静", diction: "具体", sentence_rhythm: "短句", dialogue_style: "含蓄", banned_patterns: ["过多状语"], rubric: ["用动作体现情感"] },
  volumes: [{ index: 1, title: "遗失之城", summary: "寻找线索。", central_conflict: "记忆与责任", climax: "揭开信件", ending_hook: "另一封信", target_length: 250000 }, { index: 2, title: "回声", summary: "承担责任。", central_conflict: "真相与代价", climax: "归还记忆", ending_hook: "新的旅程", target_length: 250000 }],
  causal_links: [{ id: "cause", from_volume: 1, to_volume: 2, cause: "发现信件", effect: "重访故地" }], foreshadowing: [{ id: "clue", clue: "无字信封", payoff: "记忆恢复后文字显现", seed_volume: 1, payoff_volume: 2, character_ids: ["hero"] }]
};
function proposal(id = "blueprint"): ProposalArtifact {
  return { id, contract_version: "proposal_artifact_v1", project_id: "book", artifact_type: "outline_draft", status: "accepted", content_language: "zh-CN", title: "全书蓝图", body_format: "structured_json", body: JSON.stringify({ schema: "longform_plan_v1", phase: "blueprint", project_id: "book", output_language: "zh-CN", graph_snapshot: "a".repeat(64), request: { instruction: "规划作品", target_length: 500000, volume_count: 2, chapters_per_volume: 6, scenes_per_chapter: 1 }, parent_proposal_id: null, parent_version: null, blueprint, expansion: null }), version: 4, source_refs: [], target_refs: [], derived_refs: [{ kind: "longform_application", ref: id }], provenance: { created_by: "agent", created_via: "llm" }, review_decision: { status: "accepted" }, created_at: "2026-10-25", updated_at: "2026-10-25" };
}
function expansion(id: string, volume: number, indices: number[], applied = true): ProposalArtifact {
  const p = proposal(id); const envelope = JSON.parse(p.body);
  p.body = JSON.stringify({ ...envelope, phase: "expansion", parent_proposal_id: "blueprint", parent_version: 4, blueprint: null, request: { parent_proposal_id: "blueprint", parent_version: 4, volume_index: volume, chapter_start: indices[0], chapter_count: indices.length, instruction: "" }, expansion: { volume_index: volume, chapter_start: indices[0], chapters: indices.map((index) => ({ index, title: `第${index}章`, summary: "探索真相", purpose: "推进主线", target_length: 40000, scenes: [{ id: `v0${volume}_c00${index}_s01`, title: "来信", summary: "送信人打开信封。", goal: "寻找线索", conflict: "信件被封印", outcome: "发现地址", emotional_turn: "疑虑", pov_character_id: "hero", location_id: "city", required_characters: ["hero"], timeline_position: "第一日", target_length: 40000, causal_dependencies: [], foreshadowing_seed_ids: ["clue"], foreshadowing_payoff_ids: [] }] })) } });
  if (!applied) p.derived_refs = [];
  return p;
}
beforeEach(async () => { await activateLocale("zh-CN"); });
describe("persistent staged book planning", () => {
  it("recognizes exact scope and safely renders blueprint and batch plans", () => {
    const b = parseLongformPlan(proposal())!;
    const html = renderToStaticMarkup(<LongformPreview plan={b} />);
    expect(html).toContain("遗失之城"); expect(html).toContain("克制叙述"); expect(html).toContain("用动作体现情感"); expect(html).toContain("仅规划");
    expect(renderToStaticMarkup(<LongformPreview plan={parseLongformPlan(expansion("batch", 1, [1, 2]))!} />)).toContain("推进主线");
  });
  it("does not confuse acceptance, other markers or foreign proposals with application", () => {
    const p = proposal(); expect(longformApplied(p)).toBe(true);
    p.derived_refs = [{ kind: "graph_node", ref: p.id }]; expect(longformApplied(p)).toBe(false);
    p.derived_refs = [{ kind: "longform_application", ref: "other" }]; expect(longformApplied(p)).toBe(false);
    p.derived_refs = [{ kind: "longform_application", ref: p.id }]; p.status = "ready_for_review"; expect(longformApplied(p)).toBe(false);
    p.project_id = "foreign"; expect(parseLongformPlan(p)).toBeNull();
  });
  it("recovers sequential next batches from applied receipts only, including gaps and volume rollover", () => {
    const p = proposal(); const first = expansion("first", 1, [1, 2, 3, 4, 5]);
    expect(nextPlanningBatch(p, [first, expansion("pending", 1, [6], false)])).toMatchObject({ volume_index: 1, chapter_start: 6, chapter_count: 1, finished: false });
    expect(nextPlanningBatch(p, [first, expansion("last", 1, [6])])).toMatchObject({ volume_index: 2, chapter_start: 1, chapter_count: 5 });
    expect(nextPlanningBatch(p, [expansion("gap", 1, [2, 3])])).toMatchObject({ volume_index: 1, chapter_start: 1 });
    expect(nextPlanningBatch(p, [first, expansion("last", 1, [6]), expansion("second", 2, [1, 2, 3, 4, 5]), expansion("end", 2, [6])])).toMatchObject({ finished: true, completedBatches: 4 });
    const foreign = expansion("foreign", 1, [1, 2, 3]); foreign.project_id = "other";
    expect(nextPlanningBatch(p, [foreign])).toMatchObject({ chapter_start: 1, completedBatches: 0 });
  });
  it.each([{ graph_snapshot: "bad" }, { blueprint: { ...blueprint, style_brief: null } }, { blueprint: { ...blueprint, volumes: [null] } }, { blueprint: { ...blueprint, character_arcs: [{ turning_points: null }] } }, { request: { target_length: 500000, volume_count: 999999 } }])("rejects malformed author edits without crashing readable preview: %j", (patch) => {
    const p = proposal(); p.body = JSON.stringify({ ...JSON.parse(p.body), ...patch }); expect(parseLongformPlan(p)).toBeNull();
  });
  it("offers project planning before scenes exist and renders both locale catalogs", async () => {
    const props = { projectId: "book", proposals: [], busy: false, canGenerate: true, modelReady: true, modelLabel: "planning-model", onGenerate: () => undefined, onExpand: () => undefined, onOpen: () => undefined };
    let html = renderToStaticMarkup(<PlanningWorkspace {...props} />); expect(html).toContain("无需先建场景"); expect(html).toContain('value="500000"'); expect(html).toContain('max="12"');
    await activateLocale("en-US"); html = renderToStaticMarkup(<PlanningWorkspace {...props} />); expect(html).toContain("Book planning"); expect(html).toContain("a scene is not required");
  });
});
