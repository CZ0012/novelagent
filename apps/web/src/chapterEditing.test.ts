import { describe, expect, it } from "vitest";
import { chapterEditorMatches, chapterTitleIsDirty, chapterTitleUpdate, changedMetadataFields } from "./chapterEditing";

const editor = { apiBase: "http://local-a", projectId: "project-a", chapterId: "chapter-a", title: "New title", originalTitle: "Original" };

describe("pinned chapter edits", () => {
  it("writes the loaded chapter ID and title only, independently of scene selection", () => {
    const update = chapterTitleUpdate(editor, "http://local-a", "project-a");
    expect(update.path).toBe("/projects/project-a/chapters/chapter-a");
    expect(Object.keys(update.body).sort()).toEqual(["rationale", "reviewer", "source_ref", "title"]);
    expect(update.body.title).toBe("New title");
  });
  it("rejects stale backend/project scope and preserves unsaved edit detection", () => {
    expect(chapterEditorMatches(editor, "http://local-a", "project-a")).toBe(true);
    expect(chapterEditorMatches(editor, "http://local-b", "project-a")).toBe(false);
    expect(() => chapterTitleUpdate(editor, "http://local-a", "project-b")).toThrow();
    expect(chapterTitleIsDirty(editor)).toBe(true);
    expect(chapterTitleIsDirty({ ...editor, title: editor.originalTitle })).toBe(false);
  });
  it("sends only edited metadata so an unchanged old title cannot undo a rename", () => {
    const loaded = { title: "Old title", summary: "Old summary", purpose: "Old purpose" };
    expect(changedMetadataFields({ ...loaded, summary: "New summary" }, loaded)).toEqual({ summary: "New summary" });
    expect(changedMetadataFields({ ...loaded, purpose: "" }, loaded)).toEqual({ purpose: "" });
  });
});
