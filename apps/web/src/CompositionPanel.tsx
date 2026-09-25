import { useEffect, useState } from "react";
import { BookOpen, Wand2 } from "lucide-react";
import type { ProposalArtifact } from "./api";
import { uiText } from "./localization";
import { ManuscriptProse } from "./ManuscriptReader";

export type CompositionInput = { instruction: string; scope: "chapter" | "volume"; chapter_count: number; scenes_per_chapter: number; include_current_draft?: boolean; include_selected_sources?: boolean };
export type CompositionBody = { schema: "manuscript_composition_v1"; project_id: string; output_language: string; scope: "chapter" | "volume"; volume_title: string | null; volume_index: number; base_chapter_index: number; chapters: Array<{ title: string; summary: string; purpose: string; scenes: Array<{ title: string; summary: string; goal: string; conflict: string; prose: string }> }> };
function keysOnly(value: unknown, keys: string[]): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value) && Object.keys(value).every((key) => keys.includes(key));
}
function textWithin(value: unknown, length: number): value is string { return typeof value === "string" && Boolean(value.trim()) && [...value].length <= length; }
export function parseComposition(proposal: ProposalArtifact | null): CompositionBody | null {
  if (!proposal || proposal.artifact_type !== "outline_draft" || proposal.body_format !== "structured_json" || proposal.body.length > 600000) return null;
  try {
    const body = JSON.parse(proposal.body);
    if (!keysOnly(body, ["schema", "project_id", "output_language", "scope", "volume_title", "volume_index", "base_chapter_index", "chapters"]) || body.schema !== "manuscript_composition_v1" || body.project_id !== proposal.project_id || !textWithin(body.project_id, 200) || !["zh-CN", "en-US"].includes(body.output_language as string) || body.output_language !== proposal.content_language || !["chapter", "volume"].includes(body.scope as string)) return null;
    if (!Number.isSafeInteger(body.volume_index) || (body.volume_index as number) < 1 || !Number.isSafeInteger(body.base_chapter_index) || (body.base_chapter_index as number) < 0 || !Array.isArray(body.chapters) || !body.chapters.length || body.chapters.length > 4 || (body.scope === "chapter" && body.chapters.length !== 1)) return null;
    if (body.scope === "volume" ? !textWithin(body.volume_title, 120) : body.volume_title !== null && !textWithin(body.volume_title, 120)) return null;
    let totalProse = 0;
    for (const chapter of body.chapters) {
      if (!keysOnly(chapter, ["title", "summary", "purpose", "scenes"]) || !textWithin(chapter.title, 120) || !textWithin(chapter.summary, 1000) || !textWithin(chapter.purpose, 500) || !Array.isArray(chapter.scenes) || !chapter.scenes.length || chapter.scenes.length > 4) return null;
      for (const scene of chapter.scenes) {
        if (!keysOnly(scene, ["title", "summary", "goal", "conflict", "prose"]) || !textWithin(scene.title, 120) || !textWithin(scene.summary, 1000) || !textWithin(scene.goal, 500) || !textWithin(scene.conflict, 500) || !textWithin(scene.prose, 8000)) return null;
        totalProse += [...scene.prose].length;
      }
    }
    return totalProse <= 60000 ? body as CompositionBody : null;
  } catch { return null; }
}
/** Partial receipts remain retryable; the server verifies complete persisted evidence. */
export function compositionApplicationRecorded(proposal: ProposalArtifact | null): boolean {
  const body = parseComposition(proposal);
  if (!body || proposal?.status !== "accepted") return false;
  const refs = proposal.derived_refs;
  const prefix = refs.find((ref) => ref.kind === "graph_node" && /^chapter_cmp_[a-f0-9]{20}_1$/.test(ref.ref))?.ref.match(/^chapter_cmp_([a-f0-9]{20})_1$/)?.[1];
  if (!prefix) return false;
  const expected = new Set<string>(); let draftIndex = 0;
  body.chapters.forEach((chapter, i) => {
    expected.add(`graph_node:chapter_cmp_${prefix}_${i + 1}`);
    chapter.scenes.forEach((_, j) => { expected.add(`graph_node:scene_cmp_${prefix}_${i + 1}_${j + 1}`); expected.add(`draft:draft_cmp_${prefix}_${++draftIndex}`); });
  });
  return refs.length === expected.size && new Set(refs.map((ref) => `${ref.kind}:${ref.ref}`)).size === expected.size && refs.every((ref) => expected.has(`${ref.kind}:${ref.ref}`));
}
/** This reviewed schema has its own application path; generic outline drafts do not. */
export function canApplyComposition(proposal: ProposalArtifact | null, dirty: boolean, projectId: string): boolean {
  return Boolean(proposal && proposal.project_id === projectId && proposal.status === "accepted" && !dirty && parseComposition(proposal) && !compositionApplicationRecorded(proposal));
}
export function CompositionComposer({ busy, canGenerate, draftLabel, sourceLabels, sourcePolicy, modelLabel, onGenerate }: { busy: boolean; canGenerate: boolean; draftLabel: string | null; sourceLabels: string[]; sourcePolicy: string; modelLabel?: string; onGenerate: (input: CompositionInput) => void }) {
  const [input, setInput] = useState<CompositionInput>({ instruction: "", scope: "chapter", chapter_count: 1, scenes_per_chapter: 2, include_selected_sources: true });
  useEffect(() => { if (!draftLabel) setInput((current) => ({ ...current, include_current_draft: false })); }, [draftLabel]);
  return <section className="composition-composer">
    <h3><BookOpen size={16} />{uiText.manuscript.newWork}</h3><p>{uiText.manuscript.generationHelp}</p>
    <label>{uiText.manuscript.scope}<select value={input.scope} disabled={busy} onChange={(event) => setInput((current) => ({ ...current, scope: event.target.value as CompositionInput["scope"], chapter_count: event.target.value === "chapter" ? 1 : 3 }))}><option value="chapter">{uiText.manuscript.chapter}</option><option value="volume">{uiText.manuscript.volume}</option></select></label>
    <div className="composition-counts"><label>{uiText.manuscript.chapterCount}<input type="number" min={1} max={4} value={input.chapter_count} disabled={busy || input.scope === "chapter"} onChange={(event) => setInput((current) => ({ ...current, chapter_count: Math.max(1, Math.min(4, Number(event.target.value) || 1)) }))} /></label><label>{uiText.manuscript.sceneCount}<input type="number" min={1} max={4} value={input.scenes_per_chapter} disabled={busy} onChange={(event) => setInput((current) => ({ ...current, scenes_per_chapter: Math.max(1, Math.min(4, Number(event.target.value) || 1)) }))} /></label></div>
    <label>{uiText.manuscript.instruction}<textarea maxLength={12000} value={input.instruction} disabled={busy} placeholder={uiText.manuscript.instructionPlaceholder} onChange={(event) => setInput((current) => ({ ...current, instruction: event.target.value }))} /></label>
    {modelLabel && <p className="model-execution-summary">{uiText.modelRouting.effective}: {modelLabel}</p>}
    <p className="composition-inputs">{uiText.manuscript.compositionInputs}</p>
    {sourceLabels.length > 0 && <><label className="composition-draft-choice"><input type="checkbox" checked={Boolean(input.include_selected_sources)} disabled={busy} onChange={(event) => setInput((current) => ({ ...current, include_selected_sources: event.target.checked }))} /><span>{uiText.manuscript.includeSelectedSources}</span></label>{input.include_selected_sources && <div className="composition-source-manifest"><small>{sourcePolicy}</small><ul>{sourceLabels.map((source, index) => <li key={index}>{source}</li>)}</ul></div>}</>}
    <label className="composition-draft-choice"><input type="checkbox" checked={Boolean(input.include_current_draft)} disabled={busy || !draftLabel} onChange={(event) => setInput((current) => ({ ...current, include_current_draft: event.target.checked }))} /><span>{uiText.manuscript.includeCurrentDraft}</span></label>
    {input.include_current_draft && <small>{draftLabel}</small>}
    <button type="button" className="primary" disabled={busy || !canGenerate || !input.instruction.trim()} onClick={() => onGenerate(input)}><Wand2 size={15} />{uiText.manuscript.generate}</button>
  </section>;
}
export function CompositionPreview({ body }: { body: CompositionBody }) {
  return <section className="composition-review"><h3>{uiText.manuscript.compositionTitle}</h3><p>{uiText.manuscript.compositionHelp}</p>
    {body.volume_title && <h3>{uiText.manuscript.volumeLabel}: {body.volume_title}</h3>}
    {body.chapters.map((chapter, index) => <article key={index}><h3>{chapter.title}</h3><p>{chapter.summary}</p><p>{chapter.purpose}</p>{chapter.scenes.map((scene, sceneIndex) => <details open key={sceneIndex}><summary>{scene.title}</summary><p>{scene.goal}</p><p>{scene.conflict}</p><small>{uiText.manuscript.plannedProse}</small><ManuscriptProse text={scene.prose} /></details>)}</article>)}
  </section>;
}
