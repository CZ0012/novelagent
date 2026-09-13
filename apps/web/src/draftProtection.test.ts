import { describe, expect, it } from "vitest";
import {
  canHydrateDraftLoad,
  draftRequestIsCurrent,
  draftSaveCompletionPolicy,
  type DraftRequestSnapshot,
  type DraftScope
} from "./draftProtection";

const scope: DraftScope = {
  apiBase: "http://127.0.0.1:8000",
  projectId: "project_a",
  sceneId: "scene_a"
};

const request = (overrides: Partial<DraftRequestSnapshot> = {}): DraftRequestSnapshot => ({
  scope,
  sequence: 1,
  editorRevision: 0,
  ...overrides
});

describe("draft request scope", () => {
  it.each([
    { apiBase: "http://127.0.0.1:9000" },
    { projectId: "project_b" },
    { sceneId: "scene_b" }
  ])("ignores a response after changing workspace/project/scene: %o", (changed) => {
    const current = request({ scope: { ...scope, ...changed } });
    expect(draftRequestIsCurrent(request(), current)).toBe(false);
    expect(draftSaveCompletionPolicy(request(), current)).toEqual({
      applySavedDraft: false,
      replaceEditor: false,
      continueNavigation: false
    });
  });

  it("ignores an older request even after navigating away and back", () => {
    const current = request({ sequence: 3 });
    expect(canHydrateDraftLoad(request(), current, scope, false)).toBe(false);
    expect(draftSaveCompletionPolicy(request(), current).applySavedDraft).toBe(false);
  });
});

describe("draft loading preserves author edits", () => {
  it("allows initial loading and clean refreshes", () => {
    expect(canHydrateDraftLoad(request(), request(), null, false)).toBe(true);
    expect(canHydrateDraftLoad(request(), request(), scope, false)).toBe(true);
  });

  it("preserves unsaved edits that existed before a same-scene refresh", () => {
    expect(canHydrateDraftLoad(request(), request(), scope, true)).toBe(false);
  });

  it("hydrates a confirmed scene switch despite the old scene's dirty buffer", () => {
    const previousScope = { ...scope, sceneId: "scene_previous" };
    expect(canHydrateDraftLoad(request(), request(), previousScope, true)).toBe(true);
  });

  it("preserves typing during loading, including a load after a scene switch", () => {
    const typed = request({ editorRevision: 1 });
    expect(canHydrateDraftLoad(request(), typed, scope, true)).toBe(false);
    expect(canHydrateDraftLoad(request(), typed, null, true)).toBe(false);
    expect(canHydrateDraftLoad(request(), typed, { ...scope, sceneId: "old" }, true)).toBe(false);
  });
});

describe("save-and-navigate preserves typing during a save", () => {
  it("updates the saved baseline without replacing newer typing or navigating away", () => {
    const typedDuringSave = request({ editorRevision: 1 });
    expect(draftSaveCompletionPolicy(request(), typedDuringSave)).toEqual({
      applySavedDraft: true,
      replaceEditor: false,
      continueNavigation: false
    });
  });

  it("allows navigation only after saving the unchanged active editor", () => {
    expect(draftSaveCompletionPolicy(request(), request())).toEqual({
      applySavedDraft: true,
      replaceEditor: true,
      continueNavigation: true
    });
  });

  it("treats edit-then-undo as a new revision and keeps the navigation guard", () => {
    expect(draftSaveCompletionPolicy(request(), request({ editorRevision: 2 }))
      .continueNavigation).toBe(false);
  });
});
