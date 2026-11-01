import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, expect, it, vi } from "vitest";
import { activateLocale } from "./localization";
import { applyAuthoringStructure, authoringChanges, authoringPatchedWorkspace, authoringPath, authoringReconciliationCard, getAuthoringSession, postAuthoringSession, previewAuthoringStructure, reconcileAuthoringDraft, type AuthoringPatch, type AuthoringSceneCard, type AuthoringSession, type AuthoringStructurePreview, type AuthoringWorkspace } from "./authoring";
import type { Draft } from "./api";
import { AuthoringChanges, AuthoringDesign, AuthoringProposalPreview } from "./AuthoringDesign";
import { AuthoringStudio } from "./AuthoringStudio";
import { AuthoringStructure } from "./AuthoringStructure";
import { emptyVisibility } from "./WriterVisibilityPanel";

const empty = (): AuthoringWorkspace => ({ items: [], character_plans: [], scene_cards: [], reader_records: [] });
const patch = (): AuthoringPatch => ({ upsert_items: [], upsert_character_plans: [], upsert_scene_cards: [], remove_item_ids: [], remove_character_ids: [], remove_card_ids: [], add_reader_records: [], remove_reader_records: [] });
const decided = { id: "premise", kind: "world_fact" as const, status: "author_decided" as const, text: "锁没有被撬开。", rationale: "已有设计", depends_on: [], evidence: [] };
beforeEach(async () => { await activateLocale("zh-CN"); vi.restoreAllMocks(); });

it("projects typed changes while preserving unmentioned author decisions and showing removals", () => {
  const before = { ...empty(), items: [decided, { ...decided, id: "old", text: "旧备选" }] };
  const next = authoringPatchedWorkspace(before, { ...patch(), upsert_items: [{ ...decided, id: "belief", kind: "character_belief", character_id: "hero", text: "父亲没有说谎。" }], remove_item_ids: ["old"] });
  expect(next.items.find(item => item.id === "premise")).toEqual(decided);
  expect(before.items).toHaveLength(2);
  expect(authoringChanges(before, next).map(item => item.id)).toEqual(["old", "belief"]);
  const html = renderToStaticMarkup(<AuthoringChanges before={before} after={next} names={{ hero: "林舟" }} />);
  expect(html).toContain("移除"); expect(html).toContain("旧备选"); expect(html).toContain("新增"); expect(html).toContain("人物相信"); expect(html).toContain("林舟");
});

it("renders character goals and unresolved assumptions without claiming established canon", () => {
  const html = renderToStaticMarkup(<AuthoringDesign workspace={{ ...empty(), character_plans: [{ character_id: "hero", goal: "找到父亲", belief_item_ids: [], knowledge_assumptions: ["是否读过信仍未决定"], intended_actions: [{ character_id: "hero", intention: "先检查信封", depends_on: [] }] }] }} names={{ hero: "林舟" }} />);
  expect(html).toContain("找到父亲"); expect(html).toContain("待核实的知情前提"); expect(html).toContain("是否读过信仍未决定"); expect(html).toContain("先检查信封");
});

it("shows exact reader evidence with presentation and saved version during patch review", () => {
  const html = renderToStaticMarkup(<AuthoringDesign workspace={{ ...empty(), reader_records: [{ draft_id: "draft_exact", version: 7, text_sha256: "a".repeat(64), start: 3, end: 9, offset_unit: "utf16", expected_text: "他说父亲无辜", presentation: "character_statement" }] }} />);
  expect(html).toContain("他说父亲无辜"); expect(html).toContain("人物已经声称"); expect(html).toContain("draft_exact"); expect(html).toContain("v7"); expect(html).toContain("3–9");
});

it("labels the complete author plan separately from the Writer-visible surface plan", () => {
  const card: AuthoringSceneCard = { id: "card", version: 1, title: "来信", author_summary: "作者私留：父亲伪造了信件。", chapter_title: "开场", location: "邮局", timeline_position: "第一日", goal: "核对信封", conflict: "封蜡无法辨认", emotional_turn: "起疑", target_length: 1500, status: "approved", entry_knowledge: [], intended_actions: [], acquisitions: [], writer_policy: { ...emptyVisibility(), surface_plan: { kind: "literal", text: "只描写送信人核对封蜡。" } }, withheld: [], intended_outcome: "找到地址", depends_on: [] };
  const html = renderToStaticMarkup(<AuthoringDesign workspace={{ ...empty(), scene_cards: [card] }} />);
  expect(html).toContain("作者侧场景计划（不直接发送给写作模型）"); expect(html).toContain("父亲伪造了信件"); expect(html).toContain("允许表达的计划"); expect(html).toContain("只描写送信人核对封蜡");
  const structure = renderToStaticMarkup(<AuthoringStructure preview={{ source_sha256: "a".repeat(64), card_version: 1, scene_id: "scene", chapter_id: "chapter", character_mapping: {}, relationships: [], gaps: [], nodes: [{ id: "scene", type: "Scene", properties: { summary: card.author_summary } }] }} />);
  expect(structure).toContain("作者侧场景计划（不直接发送给写作模型）"); expect(structure).not.toContain("允许表达的计划");
});

it("exposes every proposed Writer policy field including a secret embedded in banned expressions before adoption", async () => {
  const policy = { ...emptyVisibility(), access_mode: "pov" as const, surface_plan: { kind: "literal" as const, text: "只写核对门锁。" }, characters: [{ character_id: "hero", public_name: "检修员", allow_offstage_name: true }], writer_style: { pov: "有限视角", tense: "过去时", tone: "克制", sentence_rhythm: "短句", diction: "具体", dialogue_style: "含蓄", rubric: ["避免直说隐藏答案"], banned_patterns: ["PRIVATE_SECRET_IN_STYLE：地下室的银钥匙"] }, expected_reader_inference: "读者可能怀疑检修员来过这里。", reader_presented: [{ draft_id: "exact_reader_draft", version: 4, text_sha256: "a".repeat(64), start: 2, end: 8, offset_unit: "utf16", expected_text: "门锁上有划痕", presentation: "clue" }] };
  const card: AuthoringSceneCard = { id: "card", version: 1, title: "门锁", chapter_title: "开场", location: "旧楼", timeline_position: "第一日", goal: "检查门锁", conflict: "无法辨认划痕", emotional_turn: "起疑", target_length: 1500, status: "proposed", entry_knowledge: [], intended_actions: [], acquisitions: [], writer_policy: policy, withheld: [], intended_outcome: "发现划痕", depends_on: [] };
  const html = renderToStaticMarkup(<AuthoringChanges before={empty()} after={{ ...empty(), scene_cards: [card] }} />);
  for (const text of ["PRIVATE_SECRET_IN_STYLE：地下室的银钥匙", "已明确授权的禁用表达", "已明确授权的评价标准", "避免直说隐藏答案", "读者可能怀疑检修员来过这里", "检修员", "门锁上有划痕", "exact_reader_draft", "v4", "作者侧核对信息", "<details open"]) expect(html).toContain(text);
  expect(html).not.toContain("<textarea");
  await activateLocale("en-US");
  const english = renderToStaticMarkup(<AuthoringDesign workspace={{ ...empty(), scene_cards: [card] }} />);
  expect(english).toContain("PRIVATE_SECRET_IN_STYLE：地下室的银钥匙"); expect(english).toContain("Author-side review context");
});

it("distinguishes planned acquisitions from quoted ones and keeps each quote beside its own acquisition", async () => {
  const card: AuthoringSceneCard = { id: "card", version: 1, title: "门锁", chapter_title: "开场", location: "旧楼", timeline_position: "第一日", goal: "检查门锁", conflict: "无法辨认划痕", emotional_turn: "起疑", target_length: 1500, status: "proposed", entry_knowledge: [], intended_actions: [], acquisitions: [{ character_id: "hero", text: "计划获知封条松动", evidence: [] }, { character_id: "hero", text: "带引文的获知建议", evidence: [{ draft: { scene_id: "scene", draft_id: "exact_saved", version: 3, text_sha256: "a".repeat(64) }, start: 2, end: 8, offset_unit: "utf16", expected_text: "独有原句：锁孔有泥" }] }], writer_policy: { ...emptyVisibility(), characters: [{ character_id: "hero", public_name: "检修员" }] }, withheld: [], intended_outcome: "发现划痕", depends_on: [] };
  const html = renderToStaticMarkup(<AuthoringDesign workspace={{ ...empty(), scene_cards: [card] }} />);
  expect(html).toMatch(/<li><p>检修员: 计划获知封条松动<\/p><small>计划获取，尚无正文引文<\/small><\/li>/);
  expect(html).toMatch(/<li><p>检修员: 带引文的获知建议<\/p><small>附正文引文<\/small><details>/);
  expect(html.split("独有原句：锁孔有泥")).toHaveLength(2); expect(html).toContain("exact_saved"); expect(html).toContain("v3");
  await activateLocale("en-US");
  const english = renderToStaticMarkup(<AuthoringDesign workspace={{ ...empty(), scene_cards: [card] }} />);
  expect(english).toContain("Planned acquisition; no prose quote yet"); expect(english).toContain("With prose quote");
});

it("shows the complete target card snapshot when review has zero differences", () => {
  const card: AuthoringSceneCard = { id: "card", version: 7, title: "待复核的门锁场景", chapter_title: "开场", location: "旧楼", timeline_position: "第一日", goal: "检查门锁", conflict: "无法辨认划痕", emotional_turn: "起疑", target_length: 1500, status: "proposed", entry_knowledge: [], intended_actions: [], acquisitions: [{ character_id: "hero", text: "门锁有泥", evidence: [{ draft: { scene_id: "scene", draft_id: "saved_review_target", version: 3, text_sha256: "a".repeat(64) }, start: 2, end: 8, offset_unit: "utf16", expected_text: "锁孔里有新泥" }] }], writer_policy: { ...emptyVisibility(), surface_plan: { kind: "literal", text: "仅描写检查门锁。" }, characters: [{ character_id: "hero", public_name: "检修员" }] }, withheld: [], intended_outcome: "发现划痕", depends_on: [] };
  const before = { ...empty(), scene_cards: [card] }, proposed = { ...patch(), upsert_scene_cards: [card] };
  expect(authoringChanges(before, authoringPatchedWorkspace(before, proposed))).toEqual([]);
  const html = renderToStaticMarkup(<AuthoringProposalPreview before={before} patch={proposed} />);
  for (const text of ["待复核现状", "本次提案没有修改内容", "待复核的门锁场景", "v7", "仅描写检查门锁", "检修员", "锁孔里有新泥", "saved_review_target", "v3"]) expect(html).toContain(text);
  expect(html).not.toContain("本次变化 · 0"); expect(card.status).toBe("proposed");
});

it("provides a project-level entry before scenes exist and localizes independently", async () => {
  const props = { apiBase: "http://localhost:8000", projectId: "", projectLanguage: "zh-CN", active: true, canGenerate: true, modelReady: true, modelLabel: "test", sources: [], proposals: [], scenes: [], draft: null, draftDirty: false, onHandoff: vi.fn() };
  expect(renderToStaticMarkup(<AuthoringStudio {...props} />)).toContain("无需先创建场景");
  await activateLocale("en-US");
  const html = renderToStaticMarkup(<AuthoringStudio {...props} />);
  expect(html).toContain("Creative collaboration"); expect(html).toContain("No scene is required");
});

it("uses scoped exact endpoints and preserves author decision/version payload", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(JSON.stringify({ session: { id: "session" } }), { status: 200, headers: { "content-type": "application/json" } }));
  expect(authoringPath("book/a", "session/b")).toBe("/projects/book%2Fa/authoring-sessions/session%2Fb");
  await getAuthoringSession("http://localhost:8000", "book", "session");
  await postAuthoringSession("http://localhost:8000", "book", "session", "/proposals/p/decision", { expected_version: 8, decision: "adopt" });
  expect(fetchMock.mock.calls[1][0]).toContain("/projects/book/authoring-sessions/session/proposals/p/decision");
  expect(JSON.parse(fetchMock.mock.calls[1][1]?.body as string)).toEqual({ expected_version: 8, decision: "adopt" });
});

it("renders reviewable structure and explains missing plans in ordinary language", () => {
  const preview: AuthoringStructurePreview = { source_sha256: "a".repeat(64), card_version: 2, scene_id: "scene", chapter_id: "chapter", character_mapping: { hero: "character" }, relationships: [], gaps: ["timeline_position", "emotional_turn"], nodes: [{ id: "character", type: "Character", properties: { name: "林舟" } }, { id: "scene", type: "Scene", properties: { title: "试写开场", goal: "打开信封", conflict: "封蜡无法辨认", outcome: "找到地址", style_constraints: { tone: "克制" } } }] };
  const html = renderToStaticMarkup(<AuthoringStructure preview={preview} />);
  expect(html).toContain("故事发生时间"); expect(html).toContain("情绪转折"); expect(html).toContain("请回到上方对话"); expect(html).toContain("林舟"); expect(html).toContain("封蜡无法辨认"); expect(html).toContain("克制"); expect(html).toContain("只有点击确认");
  expect(html).not.toContain("timeline_position"); expect(html).not.toContain("<textarea");
});

it("distinguishes bound scene plan updates and shows exact old/new values plus reused names", () => {
  const preview: AuthoringStructurePreview = { operation: "update", source_sha256: "a".repeat(64), card_version: 5, scene_id: "scene", chapter_id: "chapter", character_mapping: { hero: "character" }, relationships: [], gaps: [], current_scene: { id: "scene", type: "Scene", properties: { title: "旧开场", goal: "寻找父亲" } }, changes: [{ field: "goal", before: "寻找父亲", after: "先核对信封" }, { field: "location_id", before: "old_location", after: "location" }], nodes: [{ id: "scene", type: "Scene", properties: { goal: "先核对信封" } }], reuse: [{ id: "character", type: "Character", name: "林舟", public_name: "送信人" }, { id: "location", type: "Location", name: "旧邮局" }] };
  const html = renderToStaticMarkup(<AuthoringStructure preview={preview} names={{ old_location: "街角" }} />);
  expect(html).toContain("预览场景计划变更"); expect(html).toContain("寻找父亲"); expect(html).toContain("先核对信封"); expect(html).toContain("街角"); expect(html).toContain("旧邮局"); expect(html).toContain("林舟"); expect(html).toContain("送信人"); expect(html).toContain("复用项目中已有"); expect(html).toContain("不改正文"); expect(html).not.toContain("只有点击确认才创建");
});

it("separates read-only structure preview from exact explicit author application", async () => {
  const preview: AuthoringStructurePreview = { source_sha256: "a".repeat(64), card_version: 4, scene_id: "scene", chapter_id: "chapter", character_mapping: {}, nodes: [], relationships: [], gaps: [] };
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(JSON.stringify(preview), { status: 200 }));
  const session = { id: "conversation", version: 12 } as AuthoringSession;
  await previewAuthoringStructure("http://localhost:8000", "book", session, "card");
  expect(fetchMock.mock.calls).toHaveLength(1);
  expect(fetchMock.mock.calls[0][0]).toContain("/cards/card/structure-preview");
  expect(JSON.parse(fetchMock.mock.calls[0][1]?.body as string)).toEqual({ expected_version: 12 });
  await applyAuthoringStructure("http://localhost:8000", "book", session, "card", preview, "作者明确确认此试写场景结构");
  expect(fetchMock.mock.calls[1][0]).toContain("/cards/card/structure-apply");
  expect(JSON.parse(fetchMock.mock.calls[1][1]?.body as string)).toEqual({ expected_version: 12, card_version: 4, source_sha256: "a".repeat(64), reviewer: "author", rationale: "作者明确确认此试写场景结构" });
});

it("requires a same-scene card, leaves ambiguous matches unselected, and sends the exact card/Draft pair", async () => {
  const draft = { id: "draft_exact", project_id: "book", scene_id: "scene", version: 7, text: "他说父亲无辜。" } as Draft;
  const cardA = { id: "cardA", scene_id: "scene", title: "开场设计", version: 3 };
  const cardB = { id: "cardB", scene_id: "scene", title: "开场另案", version: 9 };
  const session = { id: "conversation", project_id: "book", version: 12, workspace: { ...empty(), scene_cards: [cardA] } } as AuthoringSession;
  expect(authoringReconciliationCard(session, draft)?.id).toBe("cardA");
  expect(authoringReconciliationCard(session, { ...draft, scene_id: "foreign" })).toBeNull();
  expect(authoringReconciliationCard(session, { ...draft, project_id: "foreign" })).toBeNull();
  session.workspace.scene_cards.push(cardB as typeof session.workspace.scene_cards[number]);
  expect(authoringReconciliationCard(session, draft)).toBeNull();
  expect(authoringReconciliationCard(session, draft, "cardB")?.version).toBe(9);
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(JSON.stringify({ session: { id: "conversation" } }), { status: 200 }));
  await expect(reconcileAuthoringDraft("http://localhost:8000", session, draft)).rejects.toThrow("exact same-scene");
  await expect(reconcileAuthoringDraft("http://localhost:8000", session, { ...draft, scene_id: "foreign" }, "cardB")).rejects.toThrow("exact same-scene");
  expect(fetchMock).not.toHaveBeenCalled();
  await reconcileAuthoringDraft("http://localhost:8000", session, draft, "cardB");
  expect(fetchMock.mock.calls[0][0]).toContain("/authoring-sessions/conversation/reconcile");
  expect(JSON.parse(fetchMock.mock.calls[0][1]?.body as string)).toEqual({ expected_version: 12, card_id: "cardB", card_version: 9, draft_id: "draft_exact", draft_version: 7, text_sha256: expect.stringMatching(/^[a-f0-9]{64}$/), max_steps: 6 });
});
