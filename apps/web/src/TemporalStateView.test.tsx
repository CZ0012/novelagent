import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it } from "vitest";
import { activateLocale } from "./localization";
import type { TemporalStateProjection } from "./api";
import { parseTemporalPatch, temporalValueLabel, TemporalCandidateNotice, TemporalContext, TemporalProposalPreviews } from "./TemporalStateView";
const properties = { contract_version: "temporal_state_v1", field: "life_status", value: "dead", valid_from_scene: "scene-b", expected_slot_fingerprint: "a".repeat(64), source_text_sha256: "b".repeat(64) };
const projection: TemporalStateProjection = { contract_version: "temporal_state_v1", project_id: "book", subject_id: "hero", scene_id: "scene-b", at_scene_start: true, complete: false, states: [ { field: "life_status", status: "resolved", value: "alive", assertion_refs: ["state-first"] }, { field: "physical_state", status: "unknown", value: null, assertion_refs: [], reason: "missing_baseline" }, { field: "location_id", status: "ambiguous", value: null, assertion_refs: ["state-branch-a", "state-branch-b"], reason: "incomparable_scenes" } ] };
beforeEach(async () => { await activateLocale("zh-CN"); });
describe("explicit temporal state projections", () => {
  it("shows scene entry state with unknown/ambiguous slots and does not infer defaults", () => {
    const html = renderToStaticMarkup(<TemporalContext projections={[projection]} projectId="book" sceneId="scene-b" labels={{ hero: "林舟" }} />);
    expect(html).toContain("林舟 · 场景开始时"); expect(html).toContain("存活"); expect(html).toContain("未知"); expect(html).toContain("有歧义"); expect(html).toContain("状态信息不完整");
    expect(html).not.toContain("健康"); expect(html).toContain("不从人物描述推断初始状态");
    expect(html).toContain('<details><summary>状态来源与稳定引用</summary>'); expect(html).toContain("state-branch-a");
    expect(renderToStaticMarkup(<TemporalContext projections={[projection]} projectId="other" sceneId="scene-b" />)).toBe("");
  });
  it("distinguishes explicit unowned from unknown and resolves names rather than displaying IDs", () => {
    expect(temporalValueLabel("owner_id", null, "resolved")).toBe("明确无主");
    expect(temporalValueLabel("owner_id", null, "unknown")).toBe("未知");
    expect(temporalValueLabel("location_id", "city", "resolved", { city: "雾城" })).toBe("雾城");
    expect(temporalValueLabel("location_id", "city", "resolved")).toBe("已记录对象（见引用）");
    expect(temporalValueLabel("physical_state", "healing", "resolved")).toBe("恢复中");
  });
  it("separates pending state assertions from observation-only patches", () => {
    const html = renderToStaticMarkup(<TemporalCandidateNotice operation="append_state" properties={properties} subjectId="hero" labels={{ hero: "林舟", "scene-b": "雨夜" }} />);
    expect(html).toContain("记录时点状态"); expect(html).toContain("林舟 · 生命状态: 死亡"); expect(html).toContain("人工接受后"); expect(html).toContain("生效场景: 雨夜");
    expect(renderToStaticMarkup(<TemporalCandidateNotice operation="none" properties={{}} subjectId="hero" />)).toBe("");
    expect(parseTemporalPatch("append_state", { ...properties, value: "healthy" })).toBeNull();
    expect(parseTemporalPatch("append_state", { ...properties, source_text_sha256: "missing" })).toBeNull();
  });
  it("renders temporal candidates in fact proposals without raw JSON as the only explanation", () => {
    const body = JSON.stringify({ candidate_previews: [{ id: "candidate", subject_id: "hero", proposed_graph_patch: { operation: "append_state", properties } }] });
    expect(renderToStaticMarkup(<TemporalProposalPreviews body={body} />)).toContain("生命状态: 死亡");
    expect(renderToStaticMarkup(<TemporalProposalPreviews body="{" />)).toBe("");
  });
  it("uses English labels independently from author values and distinguishes through-scene", async () => {
    await activateLocale("en-US");
    const html = renderToStaticMarkup(<TemporalContext projections={[{ ...projection, at_scene_start: false }]} projectId="book" sceneId="scene-b" labels={{ hero: "林舟" }} />);
    expect(html).toContain("林舟 · Through this scene"); expect(html).toContain("Alive"); expect(html).toContain("Unknown"); expect(html).toContain("Ambiguous");
  });
});
