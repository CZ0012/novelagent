import { useEffect, useState, type ReactNode } from "react";
import { ChevronDown, ChevronRight, FileText } from "lucide-react";
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

export function ProjectTree({ projectId, chapters, sceneId, selectedChapterId, chapterEditor, busy, onSelectChapter, onSelectScene }: {
  projectId: string;
  chapters: ChapterOutline[];
  sceneId: string;
  selectedChapterId: string | null;
  chapterEditor?: ReactNode;
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
    {chapters.map((chapter) => {
      const open = expanded.has(chapter.id);
      const selected = selectedChapterId === chapter.id;
      const childrenId = `chapter-children-${encodeURIComponent(chapter.id)}`;
      return <div key={chapter.id} className="chapter">
        <div className={`chapter-row ${selected ? "selected" : ""}`}>
          <button className="chapter-toggle" type="button" aria-expanded={open} aria-controls={childrenId}
            aria-label={uiText.authorWorkspace.toggleChapter(chapter.title)}
            onClick={() => setExpanded((current) => toggleChapterExpansion(current, chapter.id))}>
            {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </button>
          <button className="chapter-title" type="button" disabled={busy} aria-pressed={selected}
            title={uiText.authorWorkspace.editChapterTitle} onClick={() => onSelectChapter(chapter.id)}>
            <span>{chapter.title}</span><small>{chapter.scenes.length}</small>
          </button>
        </div>
        {selected && chapterEditor}
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
