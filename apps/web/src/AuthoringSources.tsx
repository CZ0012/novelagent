import { useState } from "react";
import type { ProposalArtifact, SourceDocumentSummary } from "./api";
import type { AuthoringSession } from "./authoring";
import { uiText } from "./localization";

export function AuthoringSources({ session, sources, proposals, busy, canEdit, onSave }: { session: AuthoringSession; sources: SourceDocumentSummary[]; proposals: ProposalArtifact[]; busy: boolean; canEdit: boolean; onSave: (expectedVersion: number, sourceIds: string[], outlineIds: string[]) => Promise<boolean> }) {
  const t = uiText.authoring;
  const [selection, setSelection] = useState<{ version: number; sourceIds: string[]; outlineIds: string[] } | null>(null);
  const outlines = proposals.filter(item => item.project_id === session.project_id && item.artifact_type === "outline_draft");
  const scopedSources = sources.filter(source => source.project_id === session.project_id);
  function begin() { setSelection({ version: session.version, sourceIds: session.source_pins.filter(pin => pin.kind === "source_document").map(pin => pin.id), outlineIds: session.source_pins.filter(pin => pin.kind === "outline").map(pin => pin.id) }); }
  function toggle(kind: "sourceIds" | "outlineIds", id: string) { setSelection(value => value ? { ...value, [kind]: value[kind].includes(id) ? value[kind].filter(item => item !== id) : [...value[kind], id] } : value); }
  const stale = Boolean(selection && selection.version !== session.version), locked = busy || !canEdit;
  async function save() { if (!selection || stale || locked) return; if (await onSave(selection.version, selection.sourceIds, selection.outlineIds)) setSelection(null); }
  return <details className="authoring-card authoring-source-summary"><summary>{t.sourcesCurrent} · {session.source_pins.length}</summary><ul>{session.source_pins.map(pin => <li key={`${pin.kind}:${pin.id}`}>{pin.kind === "source_document" ? scopedSources.find(source => source.id === pin.id)?.title ?? pin.id : outlines.find(item => item.id === pin.id)?.title ?? pin.id}{pin.version ? ` · v${pin.version}` : ""}</li>)}</ul><p>{t.sourcesEditHelp}</p>{!selection ? <button type="button" disabled={locked} onClick={begin}>{t.sourcesEdit}</button> : <>
    {stale && <p role="status">{t.sourcesVersionChanged}</p>}<div className="authoring-sources">{scopedSources.map(source => { const selected = selection.sourceIds.includes(source.id), available = source.extraction_status === "ready" && source.language === session.content_language; return <label key={source.id}><input type="checkbox" disabled={locked || stale || (!available && !selected)} checked={selected} onChange={() => toggle("sourceIds", source.id)} /><span>{source.title} · {source.language}{!available && ` · ${t.sourceUnavailable}`}</span></label>; })}{outlines.map(outline => { const selected = selection.outlineIds.includes(outline.id), available = outline.content_language === session.content_language; return <label key={outline.id}><input type="checkbox" disabled={locked || stale || (!available && !selected)} checked={selected} onChange={() => toggle("outlineIds", outline.id)} /><span>{t.outline}: {outline.title} · v{outline.version}{!available && ` · ${t.sourceUnavailable}`}</span></label>; })}{(["sourceIds", "outlineIds"] as const).flatMap(kind => selection[kind].filter(id => !(kind === "sourceIds" ? scopedSources : outlines).some(item => item.id === id)).map(id => <label key={`${kind}:${id}`}><input type="checkbox" checked disabled={locked || stale} onChange={() => toggle(kind, id)} /><span>{id} · {t.sourcesPinnedMissing}</span></label>))}</div>
    <div className="authoring-actions"><button type="button" className="primary" disabled={locked || stale} onClick={() => { void save(); }}>{t.sourcesSave}</button><button type="button" disabled={busy} onClick={() => setSelection(null)}>{t.sourcesCancel}</button>{stale && <button type="button" disabled={busy} onClick={begin}>{t.sourcesReload}</button>}</div>
    </>}
  </details>;
}
