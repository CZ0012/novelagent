import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, expect, it, vi } from "vitest";
import { activateLocale, uiText } from "./localization";
import { readAuthoringHistory, readAuthoringProposal, updateAuthoringSources, type AuthoringProposal } from "./authoring";
import { AuthoringProposalActions, AuthoringProposalOrigin } from "./AuthoringDesign";
import { AuthoringHistoricalProposal } from "./AuthoringHistory";
import { AuthoringStructure } from "./AuthoringStructure";

const proposal: AuthoringProposal = { id: "old/proposal", base_workspace_sha256: "a".repeat(64), summary: "旧设计原稿", status: "pending", stale: true, created_at: "2026-11-01", affected_card_ids: [], affected_scene_ids: [], evidence: [], patch: { upsert_items: [{ id: "old_item", kind: "world_fact", status: "open", text: "当时尚未决定的设定。", rationale: "", depends_on: [], evidence: [] }], upsert_character_plans: [], upsert_scene_cards: [], remove_item_ids: ["removed_item"], remove_character_ids: [], remove_card_ids: [], add_reader_records: [], remove_reader_records: [] } };
beforeEach(async () => { await activateLocale("zh-CN"); vi.restoreAllMocks(); });

it("disables adoption for stale or unverified proposals while keeping rejection available", () => {
  for (const stale of [true, undefined]) {
    const html = renderToStaticMarkup(<AuthoringProposalActions proposal={{ ...proposal, stale }} locked={false} onDecide={vi.fn()} />);
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>采用这组设计/);
    expect(html).toMatch(/<button type="button">保留原设计/);
  }
  const fresh = renderToStaticMarkup(<AuthoringProposalActions proposal={{ ...proposal, stale: false }} locked={false} onDecide={vi.fn()} />);
  expect(fresh).not.toContain("disabled=");
});

it("shows historical patch contents and removals read-only instead of fabricating a current comparison", () => {
  const html = renderToStaticMarkup(<AuthoringHistoricalProposal proposal={proposal} names={{ removed_item: "旧备选" }} />);
  expect(html).toContain("当时尚未决定的设定"); expect(html).toContain("旧备选"); expect(html).toContain("不与当前设计合并"); expect(html).not.toContain("<button");
});

it("labels a pending revision's exact original without implying adoption and localizes its tool trace", async () => {
  const revised = { ...proposal, supersedes_proposal_id: "original-pending-17" };
  const html = renderToStaticMarkup(<AuthoringHistoricalProposal proposal={revised} />);
  expect(html).toContain("修订自待审方案"); expect(html).toContain("original-pending-17"); expect(html).toContain("原方案不会因此被采用或改写"); expect(html).toContain("历史提案中搜索此标识");
  expect(revised.status).toBe("pending"); expect(proposal.status).toBe("pending");
  expect(uiText.authoring.toolsLabels.revise_proposal).toBe("修订待审方案");
  expect(renderToStaticMarkup(<AuthoringProposalOrigin proposal={{}} />)).toBe("");
  await activateLocale("en-US");
  expect(uiText.authoring.toolsLabels.revise_proposal).toBe("Revise pending proposal");
  expect(renderToStaticMarkup(<AuthoringProposalOrigin proposal={revised} />)).toContain("neither adopted nor edited");
});

it("explains the six-call format-correction bound and gives unbound scenes both paths with generic location names", async () => {
  expect(uiText.authoring.turnBudget).toContain("最多6次模型调用"); expect(uiText.authoring.turnBudget).toContain("一次格式修正"); expect(uiText.authoring.turnBudget).toContain("不确定的失败会停止");
  expect(uiText.authoring.toolsLabels.format_diagnostic).toBe("回复格式检查");
  expect(uiText.authoring.toolsLabels.propose_card_review).toBe("提请复核场景卡现状");
  expect(uiText.authoring.toolsLabels.format_correction).toBe("有限回复格式修正"); expect(uiText.authoring.toolsLabels.search_draft_quotes).toBe("核对草稿引文"); expect(uiText.authoring.toolsLabels.propose_draft_evidence).toBe("提出草稿证据");
  expect(uiText.authoring.noScene).toContain("可预览新建试写场景，或通过对话关联已有场景");
  const html = renderToStaticMarkup(<AuthoringStructure preview={{ source_sha256: "a".repeat(64), card_version: 1, scene_id: "scene", chapter_id: "chapter", character_mapping: {}, relationships: [], gaps: [], nodes: [{ id: "location", type: "Location", properties: { name: "旧邮局" } }] }} />);
  expect(html).toContain("<dt>名称</dt><dd>旧邮局</dd>");
  await activateLocale("en-US");
  expect(uiText.authoring.turnBudget).toContain("up to 6 model calls"); expect(uiText.authoring.toolsLabels.format_diagnostic).toBe("Response format check"); expect(uiText.authoring.generalName).toBe("Name");
  expect(uiText.authoring.toolsLabels.propose_card_review).toBe("Submit current scene cards for review");
});

it("uses scoped newest-first history offsets and exact old proposal detail without sending a model request", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(JSON.stringify({ records: [], total_matches: 81, returned_count: 0, offset: 40, more: true, next_offset: 80, order: "newest_first", proposal }), { status: 200 }));
  const page = await readAuthoringHistory("http://localhost:8000", "book/a", "session/b", "proposals", "信 & clue", 40);
  const url = new URL(fetchMock.mock.calls[0][0] as string);
  expect(url.pathname).toBe("/projects/book%2Fa/authoring-sessions/session%2Fb/history");
  expect(Object.fromEntries(url.searchParams)).toEqual({ kind: "proposals", query: "信 & clue", offset: "40", limit: "40" });
  expect(page.next_offset).toBe(80); expect(page.order).toBe("newest_first");
  const detail = await readAuthoringProposal("http://localhost:8000", "book/a", "session/b", "old/proposal");
  expect(fetchMock.mock.calls[1][0]).toContain("/session%2Fb/proposals/old%2Fproposal"); expect(detail.patch).toEqual(proposal.patch);
  expect(fetchMock.mock.calls.every(([, options]) => !options?.method || options.method === "GET")).toBe(true);
});

it("updates only explicit Source/outline IDs at the editor's pinned CAS version and preserves Draft authority server-side", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(JSON.stringify({ session: { id: "session" } }), { status: 200 }));
  await updateAuthoringSources("http://localhost:8000", "book", "session", 17, ["source-current"], ["outline-current"]);
  expect(fetchMock.mock.calls[0][0]).toContain("/projects/book/authoring-sessions/session/sources");
  expect(JSON.parse(fetchMock.mock.calls[0][1]?.body as string)).toEqual({ expected_version: 17, source_document_ids: ["source-current"], outline_proposal_ids: ["outline-current"] });
  expect(fetchMock.mock.calls).toHaveLength(1);
});
