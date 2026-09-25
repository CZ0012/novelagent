export type ChapterEditorScope = { apiBase: string; projectId: string; chapterId: string };
export type ChapterTitleEditor = ChapterEditorScope & { title: string; originalTitle: string };

export function chapterEditorMatches(scope: ChapterEditorScope | null, apiBase: string, projectId: string): boolean {
  return Boolean(scope && scope.apiBase === apiBase && scope.projectId === projectId && scope.chapterId);
}

export function chapterTitleIsDirty(editor: ChapterTitleEditor | null): boolean {
  return Boolean(editor && editor.title !== editor.originalTitle);
}

/** Title-only editing cannot overwrite a chapter's other metadata or retarget
 * itself when the author opens another scene. */
export function chapterTitleUpdate(editor: ChapterTitleEditor, apiBase: string, projectId: string) {
  if (!chapterEditorMatches(editor, apiBase, projectId) || !editor.title.trim()) throw new Error("Invalid chapter title editor scope");
  return {
    path: `/projects/${encodeURIComponent(editor.projectId)}/chapters/${encodeURIComponent(editor.chapterId)}`,
    body: { title: editor.title.trim(), reviewer: "author", rationale: "workbench.chapter.rename", source_ref: "author_seed:workbench_chapter_title" }
  };
}

export function changedMetadataFields<T extends Record<string, string>>(current: T, baseline: T): Partial<T> {
  return Object.fromEntries(Object.entries(current).filter(([key, value]) => value !== baseline[key])) as Partial<T>;
}
