import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, expect, it } from "vitest";
import { activateLocale } from "./localization";
import { VisibilityActualPreview, emptyVisibility, visibilitySaveBody, type VisibilityPreview, visibleStyleFields, visibilityDraftKey } from "./WriterVisibilityPanel";

beforeEach(async () => { await activateLocale("zh-CN"); });
it("previews only actual backend messages with an explicit isolation/legacy distinction", async () => {
  const preview: VisibilityPreview = { mode: "isolated", writer_view: {}, messages: [{ role:"user", content:'{"characters":[{"handle":"C1","public_name":"检修员"}],"claims":[{"text":"他相信P"}]}' }] };
  const chinese = renderToStaticMarkup(<VisibilityActualPreview preview={preview} />);
  expect(chinese).toContain("实际发送给正文模型"); expect(chinese).toContain("检修员"); expect(chinese).toContain("他相信P");
  expect(chinese).not.toContain("AUTHOR_PRIVATE");
  await activateLocale("en-US");
  const english = renderToStaticMarkup(<VisibilityActualPreview preview={{ ...preview, mode:"legacy_unisolated" }} />);
  expect(english).toContain("no hard isolation"); expect(english).toContain("检修员");
});
it("saves explicit template choice with CAS/source pins and never synthesizes reader facts", () => {
  const value = emptyVisibility();
  expect(value.surface_plan.kind).toBe("current_scene_summary"); expect(value.reader_presented).toEqual([]); expect(value.expected_reader_inference).toBe("");
  const state = { project_policy:null, scene_policy:null, effective_policy:null, source_context_sha256:"a".repeat(64), required:true };
  expect(visibilitySaveBody(state,"scene",value)).toMatchObject({ expected_version:0, expected_source_context_sha256:"a".repeat(64), spec:value });
  expect(visibilitySaveBody(state,"project",value)).not.toHaveProperty("expected_source_context_sha256");
  expect(visibilitySaveBody(state,"scene",null)).toEqual({ expected_version:0, spec:null });
});

it("summarizes actual approved names, claims, phases and style while retaining exact advanced messages", () => {
  const preview: VisibilityPreview = {mode:"isolated",writer_view:{surface_plan:"只核对门锁。",characters:[{handle:"C1",public_name:"检修员"}],claims:[{text:"盒子仍在旧柜。",presentation:"belief",phase:"entry",character:"C1"},{text:"请看锁孔。",presentation:"character_statement",phase:"during_scene",character:"C1"}],style:{pov:"第三人称有限",tone:"克制"}},messages:[{role:"user",content:"EXACT_WIRE_KEEP"}]};
  const html=renderToStaticMarkup(<VisibilityActualPreview preview={preview} />);
  expect(html).toContain("只核对门锁"); expect(html).toContain("检修员"); expect(html).toContain("开场已有"); expect(html).toContain("本场发生"); expect(html).toContain("角色相信P"); expect(html).toContain("角色台词/声称"); expect(html).toContain("叙述视角");
  expect(html).toContain("高级：完整逐字模型消息"); expect(html).toContain("EXACT_WIRE_KEEP");
});
it("copies only six visible style fields and separates scene/scope draft identity", () => {
  const selected=visibleStyleFields({pov:"有限视角",tone:"FIELD_WITH_PLOT_REVIEW_ME",sentence_rhythm:"短句",diction:"精确",dialogue_style:"简短",tense:"过去时",rubric:["PRIVATE_RUBRIC_CANARY"],banned_patterns:["PRIVATE_BAN_CANARY"],profile_id:"SEMANTIC_SOURCE_ID"});
  expect(Object.keys(selected)).toHaveLength(6); expect(selected.tone).toBe("FIELD_WITH_PLOT_REVIEW_ME");
  expect(JSON.stringify(selected)).not.toContain("PRIVATE_"); expect(JSON.stringify(selected)).not.toContain("SEMANTIC_SOURCE_ID");
  expect(visibilityDraftKey("api","p","a","project")).toBe(visibilityDraftKey("api","p","b","project"));
  expect(visibilityDraftKey("api","p","a","scene")).not.toBe(visibilityDraftKey("api","p","b","scene"));
  expect(visibilityDraftKey("api","p","a","scene")).not.toBe(visibilityDraftKey("other","p","a","scene"));
});
