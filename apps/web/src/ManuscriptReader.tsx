import { BookOpen, FileText, MessageSquare, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { apiGet, type ChapterOutline, type Draft, type SceneOutline } from "./api";
import { uiText } from "./localization";

/** Read exact rendered text only when both selection ends belong to this prose. */
export type ManuscriptSelection = { text: string; start: number; end: number };
export function selectedManuscriptRange(root: HTMLElement, selection: Selection | null): ManuscriptSelection | null {
  if (!selection || selection.isCollapsed || !selection.anchorNode || !selection.focusNode || !selection.rangeCount ||
      !root.contains(selection.anchorNode) || !root.contains(selection.focusNode)) return null;
  const range = selection.getRangeAt(0);
  const prefix = range.cloneRange(); prefix.selectNodeContents(root); prefix.setEnd(range.startContainer, range.startOffset);
  const start = prefix.toString().length;
  const text = range.toString();
  const end = start + text.length;
  return text.trim() && (root.textContent ?? "").slice(start, end) === text ? { text, start, end } : null;
}
export function ManuscriptProse({ text, onSelection, className = "" }: { text: string; onSelection?: (selection: ManuscriptSelection | null) => void; className?: string }) {
  return <div className={`manuscript-prose ${className}`} onMouseUp={(event) => onSelection?.(selectedManuscriptRange(event.currentTarget, window.getSelection()))}
    onKeyUp={(event) => onSelection?.(selectedManuscriptRange(event.currentTarget, window.getSelection()))}>{text}</div>;
}

type ChapterPage = { scene: SceneOutline; draft: Draft | null; error: boolean };
export function ChapterManuscript({ apiBase, projectId, chapter, refreshKey, busy, onOpenScene, onAskSelection, onNewChapter }: {
  apiBase: string; projectId: string; chapter: ChapterOutline; refreshKey: string; busy: boolean;
  onOpenScene: (id: string) => void; onAskSelection: (draft: Draft, selection: ManuscriptSelection) => void; onNewChapter: () => void;
}) {
  const [pages, setPages] = useState<ChapterPage[]>([]);
  const [loading, setLoading] = useState(true);
  const [selection, setSelection] = useState<{ draft: Draft; range: ManuscriptSelection } | null>(null);
  const chapterScope = `${apiBase}|${projectId}|${chapter.id}|${refreshKey}`;
  const [loadedScope, setLoadedScope] = useState("");
  useEffect(() => {
    let current = true;
    setLoading(true); setSelection(null);
    Promise.all(chapter.scenes.map(async (scene): Promise<ChapterPage> => {
      try {
        const result = await apiGet<{ draft: Draft | null }>(apiBase, `/projects/${encodeURIComponent(projectId)}/scenes/${encodeURIComponent(scene.id)}/draft`);
        return { scene, draft: result.draft, error: false };
      } catch { return { scene, draft: null, error: true }; }
    })).then((value) => { if (current) { setPages(value); setLoadedScope(chapterScope); setLoading(false); } });
    return () => { current = false; };
  }, [apiBase, projectId, chapter, refreshKey, chapterScope]);
  return <section className="chapter-manuscript">
    <div className="manuscript-reader-tools"><span><BookOpen size={16} /> {uiText.manuscript.chapterPreview}</span>
      {selection && <button type="button" disabled={busy} onClick={() => onAskSelection(selection.draft, selection.range)}><MessageSquare size={14} />{uiText.manuscript.selectionAction}</button>}
    </div>
    <p className="manuscript-reading-hint">{uiText.manuscript.chapterHelp}</p>
    {loading || loadedScope !== chapterScope ? <p className="manuscript-empty"><RefreshCw className="spin" size={18} />{uiText.manuscript.loading}</p> :
      pages.length ? pages.map(({ scene, draft, error }) => <article className="chapter-scene-page" key={scene.id}>
        <header><h2>{scene.title}</h2><button type="button" disabled={busy} onClick={() => onOpenScene(scene.id)}><FileText size={14} />{uiText.manuscript.openScene}</button></header>
        {error ? <p className="manuscript-reading-hint" role="alert">{uiText.manuscript.loadFailed}</p> : draft?.text ?
          <><small>{uiText.manuscript.readingDraft} · v{draft.version}</small><ManuscriptProse text={draft.text} onSelection={(range) => setSelection(range ? { draft, range } : null)} /></> :
          <div className="chapter-scene-empty"><p>{uiText.manuscript.sceneEmpty}</p>{typeof scene.properties?.summary === "string" && <p>{scene.properties.summary}</p>}<button type="button" disabled={busy} onClick={() => onOpenScene(scene.id)}>{uiText.manuscript.startWriting}</button></div>}
      </article>) : <div className="manuscript-empty"><p>{uiText.manuscript.chapterEmpty}</p><button type="button" onClick={onNewChapter}>{uiText.manuscript.newWork}</button></div>}
  </section>;
}
