import { useEffect, useState, type ReactNode } from "react";
import { ChevronDown, ChevronRight, FileText, Settings } from "lucide-react";
import type { ChapterOutline } from "./api";
import { uiText } from "./localization";

export function toggleChapterExpansion(expanded: Set<string>, chapterId: string): Set<string> {
  const next = new Set(expanded);
  if (next.has(chapterId)) next.delete(chapterId);
  else next.add(chapterId);
  return next;
}

export function sceneChapter(chapters: ChapterOutline[], sceneId: string): string | null {
  return chapters.find((chapter) => chapter.scenes.some((scene) => scene.id === sceneId))?.id ?? null;
}

export function ProjectTree({ projectId, chapters, sceneId, selectedChapterId, editingChapterId, onEditChapter, chapterEditor, busy, onSelectChapter, onSelectScene }: {
  projectId: string;
  chapters: ChapterOutline[];
  sceneId: string;
  selectedChapterId: string | null;
  chapterEditor?: ReactNode;
  editingChapterId?: string | null;
  onEditChapter?: (id: string) => void;
  busy: boolean;
  onSelectChapter: (id: string) => void;
  onSelectScene: (id: string) => void;
}) {
  const owner = sceneChapter(chapters, sceneId);
  const [expanded, setExpanded] = useState(() => new Set(owner ? [owner] : []));
  useEffect(() => { setExpanded(new Set(owner ? [owner] : [])); }, [projectId]);
  useEffect(() => {
    if (owner) setExpanded((current) => new Set(current).add(owner));
  }, [owner, sceneId]);
  return <div className="novel-tree">
    {chapters.map((chapter, chapterIndex) => {
      const open = expanded.has(chapter.id);
      const selected = selectedChapterId === chapter.id;
      const childrenId = `chapter-children-${encodeURIComponent(chapter.id)}`;
      const volumeTitle = typeof chapter.properties?.volume_title === "string" ? chapter.properties.volume_title : "";
      const previous = chapters[chapterIndex - 1];
      const startsVolume = Boolean(volumeTitle && (!previous || previous.volume_index !== chapter.volume_index || previous.properties?.volume_title !== volumeTitle));
      return <div key={chapter.id} className="chapter">
        {startsVolume && <div className="tree-volume-title">{volumeTitle}</div>}
        <div className={`chapter-row ${selected ? "selected" : ""}`}>
          <button className="chapter-toggle" type="button" aria-expanded={open} aria-controls={childrenId}
            aria-label={uiText.authorWorkspace.toggleChapter(chapter.title)}
            onClick={() => setExpanded((current) => toggleChapterExpansion(current, chapter.id))}>
            {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </button>
          <button className="chapter-title" type="button" disabled={busy} aria-pressed={selected}
            title={uiText.manuscript.chapterPreview} onClick={() => onSelectChapter(chapter.id)}>
            <span>{chapter.title}</span><small>{chapter.scenes.length}</small>
          </button>
          {onEditChapter && <button className="chapter-edit-button" type="button" disabled={busy} aria-label={uiText.manuscript.editChapter} title={uiText.manuscript.editChapter} onClick={() => onEditChapter(chapter.id)}><Settings size={13} /></button>}
        </div>
        {editingChapterId === chapter.id && chapterEditor}
        <div id={childrenId} hidden={!open} className="chapter-scenes">
          {chapter.scenes.length ? chapter.scenes.map((scene) => <button key={scene.id}
            className={`scene-row ${scene.id === sceneId ? "selected" : ""}`} disabled={busy}
            onClick={() => onSelectScene(scene.id)} type="button" aria-current={scene.id === sceneId ? "page" : undefined}
            title={uiText.authorWorkspace.openScene(scene.title)}>
            <FileText size={14} /><span>{scene.title}</span>
          </button>) : <p className="tree-empty">{uiText.sidebar.noChapterScenes}</p>}
        </div>
      </div>;
    })}
  </div>;
}
