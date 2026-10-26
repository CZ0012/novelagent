import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it } from "vitest";
import type { ContextPack } from "./api";
import { activateLocale } from "./localization";
import { ContextBuildAction, ContextEvidence } from "./ContextEvidence";
type Evidence = Pick<ContextPack, "scene_plan" | "canon_entities" | "knowledge_boundaries" | "style_constraints" | "relevant_world_rules" | "retrieved_style_samples" | "provenance">;
function pack(): Evidence { return {
  scene_plan: { semantics: "approved_plan_not_realized_facts", planned_outcome: "林舟发现封蜡上的暗记。", emotional_turn: "警觉", target_length: 2500, causal_preconditions: [{ scene_id: "previous", relation_id: "cause-edge", planned_summary: "计划收到来信", planned_outcome: "计划保留信封" }], foreshadowing_actions: [{ id: "clue", relation_id: "clue-edge", action: "seed", clue_text: "封蜡上的圆环", planned_payoff: "此处不能显示的未来回收", seed_scene_ids: [], do_not_reveal_payoff: true }] },
  canon_entities: [{ id: "hero", type: "Character", properties: { name: "林舟" } }, { id: "secret", type: "Secret", properties: { name: "雾城的来历" } }],
  knowledge_boundaries: [{ character_id: "hero", knows: [], does_not_know: ["secret"], falsely_believes: [], suspects: ["suspected"], hides: [], source_refs: ["knowledge-query"] }],
  style_constraints: { pov: "第三人称限制视角", tone: "克制", profile_id: "approved-style", profile_sha256: "style-hash", rubric: ["用动作呈现情绪"], banned_patterns: ["反复解释感受"] },
  relevant_world_rules: ["记忆不能无代价转移。"], retrieved_style_samples: ["风从空巷穿过。"], provenance: { graph_query_ids: ["context-query"], draft_refs: [], style_sample_refs: ["sample"], author_instruction_refs: [], built_at: "2026-10-25T10:00:00Z" }
}; }
beforeEach(async () => { await activateLocale("zh-CN"); });
describe("author-visible context evidence", () => {
  it("offers an explicit guarded build/refresh action even without a Context Pack", async () => {
    const build = renderToStaticMarkup(<ContextBuildAction hasPack={false} disabled={false} onBuild={() => undefined} />); expect(build).toContain("构建上下文"); expect(build).not.toContain('disabled=""');
    const blocked = renderToStaticMarkup(<ContextBuildAction hasPack disabled onBuild={() => undefined} />); expect(blocked).toContain("刷新上下文"); expect(blocked).toContain('disabled=""');
    await activateLocale("en-US"); expect(renderToStaticMarkup(<ContextBuildAction hasPack={false} disabled onBuild={() => undefined} />)).toContain("Build context");
  });
  it("shows approved planning intent without presenting it as realized fact or revealing a seed payoff", () => {
    const html = renderToStaticMarkup(<ContextEvidence pack={pack()} labels={{ previous: "码头来信", clue: "封蜡线索" }} />);
    expect(html).toContain("已批准的场景写作计划"); expect(html).toContain("不代表事件已经发生"); expect(html).toContain("林舟发现封蜡上的暗记"); expect(html).toContain("警觉"); expect(html).toContain("2500"); expect(html).toContain("码头来信"); expect(html).toContain("只埋设线索"); expect(html).not.toContain("此处不能显示的未来回收"); expect(html).toContain("cause-edge");
  });
  it("shows optional current scene beats in the approved plan without translating author text", async () => {
    const data = pack(); data.scene_plan!.planned_summary = "13:21:40同伴离场；主角仍在门槛前核对铅封。";
    data.canon_entities!.push({ id: "future-chapter", type: "Chapter", properties: { summary: "后卷才揭露的真相不能补进这里" } });
    const chinese = renderToStaticMarkup(<ContextEvidence pack={data} />);
    expect(chinese).toContain("当前场景规划摘要"); expect(chinese).toContain(data.scene_plan!.planned_summary);
    expect(chinese).toContain("不代表事件已经发生"); expect(chinese).not.toContain("后卷才揭露的真相不能补进这里");
    await activateLocale("en-US");
    const english = renderToStaticMarkup(<ContextEvidence pack={data} />);
    expect(english).toContain("Current scene plan summary"); expect(english).toContain(data.scene_plan!.planned_summary);
    expect(english).toContain("not evidence that events already happened");
  });
  it("keeps missing or null summaries explicit and never upgrades a legacy summary to a plan", () => {
    const data = pack();
    const missing = renderToStaticMarkup(<ContextEvidence pack={data} />);
    expect(missing).toContain("<dt>当前场景规划摘要</dt><dd>未列出（不额外推断）</dd>");
    data.scene_plan!.planned_summary = null;
    expect(renderToStaticMarkup(<ContextEvidence pack={data} />)).toContain("<dt>当前场景规划摘要</dt><dd>未列出（不额外推断）</dd>");
    data.scene_plan = null;
    data.canon_entities!.push({ id: "legacy-scene", type: "Scene", properties: { summary: "只有摘要并不代表已有批准计划" } });
    const legacy = renderToStaticMarkup(<ContextEvidence pack={data} />);
    expect(legacy).toContain("未提供已批准的场景计划"); expect(legacy).not.toContain("只有摘要并不代表已有批准计划");
    expect(legacy).not.toContain("<dt>当前场景规划摘要</dt>");
  });
  it("distinguishes entry knowledge and suspicion, using the actual snapshot names and style evidence", () => {
    const html = renderToStaticMarkup(<ContextEvidence pack={pack()} labels={{ hero: "较新名称", suspected: "可疑账本" }} />);
    expect(html).toContain("场景开始时的知识边界"); expect(html).toContain("林舟"); expect(html).not.toContain("较新名称"); expect(html).toContain("明确未知"); expect(html).toContain("雾城的来历"); expect(html).toContain("怀疑"); expect(html).toContain("可疑账本"); expect(html).toContain("未列出（不额外推断）");
    expect(html).toContain("已批准的作品文风"); expect(html).toContain("用动作呈现情绪"); expect(html).toContain("记忆不能无代价转移"); expect(html).toContain("仅作表达参考"); expect(html).toContain("style-hash");
  });
  it("keeps optional legacy plans absent and author text untranslated in English UI", async () => {
    await activateLocale("en-US"); const data = pack(); data.scene_plan = null; data.knowledge_boundaries = [];
    const html = renderToStaticMarkup(<ContextEvidence pack={data} />);
    expect(html).toContain("no approved scene plan"); expect(html).toContain("Not listed; no inference"); expect(html).toContain("Approved project style"); expect(html).toContain("第三人称限制视角"); expect(html).not.toContain("2500");
  });
});
