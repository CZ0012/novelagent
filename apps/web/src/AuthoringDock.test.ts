import { describe, expect, it } from "vitest";
import { authoringCanPinDraft, authoringValidPassage, authoringToolNavigation } from "./authoring";
import type { Draft } from "./api";

describe("Main Agent navigation and exact prose input", () => {
  it.each(["writer", "continuity"])("opens a chapter to select a scene for %s", requested => {
    const trace = { tool: "open_workflow", args: { target: requested }, result: {
      executed: false, status: "requires_scene_selection", navigation: { target: "manuscript", chapter_id: "c" },
    } };
    expect(authoringToolNavigation(JSON.stringify(trace))).toEqual(trace.result.navigation);
    expect(authoringToolNavigation(JSON.stringify({ ...trace, args: { target: "settings" } }))).toBeNull();
  });
  it("accepts only the persisted open_workflow trace wire with an explicit unexecuted result", () => {
    const trace = { tool: "open_workflow", args: { target: "manuscript" }, result: { navigation: { target: "manuscript", scene_id: "scene_exact", chapter_id: "chapter" }, status: "requires_author_action", executed: false } };
    expect(authoringToolNavigation(JSON.stringify(trace))).toEqual(trace.result.navigation);
    expect(authoringToolNavigation(JSON.stringify(trace.result))).toBeNull();
    expect(authoringToolNavigation(JSON.stringify({ ...trace, tool: "inspect_project" }))).toBeNull();
    expect(authoringToolNavigation(JSON.stringify({ ...trace, op: "delete_project" }))).toBeNull();
    expect(authoringToolNavigation(JSON.stringify({ ...trace, args: { target: "settings" } }))).toBeNull();
    expect(authoringToolNavigation(JSON.stringify({ ...trace, result: { ...trace.result, executed: true } }))).toBeNull();
    expect(authoringToolNavigation(JSON.stringify({ ...trace, result: { ...trace.result, executed: undefined } }))).toBeNull();
    expect(authoringToolNavigation(JSON.stringify({ ...trace, args: { target: "delete_project" }, result: { ...trace.result, navigation: { target: "delete_project" } } }))).toBeNull();
    expect(authoringToolNavigation(JSON.stringify({ ...trace, result: { ...trace.result, navigation: { target: "manuscript", scene_id: ["invalid"] } } }))).toBeNull();
    expect(authoringToolNavigation("open settings now")).toBeNull();
  });
  it("permits only explicit saved same-project and same-scene Draft selection", () => {
    const draft = { id: "saved_exact", project_id: "project", scene_id: "scene", version: 4, text: "saved prose" } as Draft;
    expect(authoringCanPinDraft("project", "scene", draft, false)).toBe(true);
    expect(authoringCanPinDraft("project", "scene", draft, true)).toBe(false);
    expect(authoringCanPinDraft("other", "scene", draft, false)).toBe(false);
    expect(authoringCanPinDraft("project", "other", draft, false)).toBe(false);
    expect(authoringCanPinDraft("project", "scene", null, false)).toBe(false);
  });
});

it("rejects stale prose, mismatched Draft IDs and split UTF16 characters for segment-only input", () => {
  const draft = { id: "saved", project_id: "p", scene_id: "s", text: "A😀B" } as Draft;
  const selection = { draftId: "saved", start: 1, end: 3, text: "😀" };
  expect(authoringValidPassage("p", "s", draft, false, selection)).toBe(true);
  expect(authoringValidPassage("p", "s", draft, true, selection)).toBe(false);
  expect(authoringValidPassage("p", "other", draft, false, selection)).toBe(false);
  expect(authoringValidPassage("p", "s", draft, false, { ...selection, draftId: "old" })).toBe(false);
  expect(authoringValidPassage("p", "s", draft, false, { ...selection, text: "stale" })).toBe(false);
  expect(authoringValidPassage("p", "s", draft, false, { draftId: "saved", start: 1, end: 2, text: draft.text.slice(1, 2) })).toBe(false);
});

it("bounds selected prose to 8000 UTF16 units without requiring prose for ordinary chat", () => {
  const draft = { id: "saved", project_id: "p", scene_id: "s", text: "A".repeat(8001) } as Draft;
  expect(authoringCanPinDraft("p", undefined, draft, false)).toBe(false);
  expect(authoringCanPinDraft("p", "s", null, false)).toBe(false);
  expect(authoringValidPassage("p", "s", draft, false, { draftId: "saved", start: 0, end: 8000, text: draft.text.slice(0, 8000) })).toBe(true);
  expect(authoringValidPassage("p", "s", draft, false, { draftId: "saved", start: 0, end: 8001, text: draft.text })).toBe(false);
});
