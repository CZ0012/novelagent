import { useMemo, useState } from "react";
import { Wand2 } from "lucide-react";
import type { ProposalArtifact } from "./api";
import { PlanningRunPanel } from "./PlanningRunPanel";
import { blueprintInputValid } from "./planningRuns";
import { temporalValueLabel } from "./TemporalStateView";
import type { TemporalStateField } from "./api";
import { uiText, proposalStatusLabels } from "./localization";
import { longformApplied, nextPlanningBatch, parseLongformPlan, type BlueprintRequest, type ExpansionRequest, type LongformPlan } from "./longformPlanning";

export function LongformPreview({ plan }: { plan: Pick<LongformPlan, "blueprint" | "expansion"> }) {
  const t = uiText.planning;
  const b = plan.blueprint;
  return <section className="longform-preview">
    <p className="planning-boundary">{t.noProse}</p>
    {b && <>
      <h3>{t.synopsis}</h3><p className="planning-prose">{b.synopsis}</p>
      <h3>{t.volumes}</h3>{b.volumes.map((v) => <article key={v.index}><h4>{v.index}. {v.title} <small>{v.target_length.toLocaleString()}</small></h4><p>{v.summary}</p><dl><dt>{t.conflict}</dt><dd>{v.central_conflict}</dd><dt>{t.climax}</dt><dd>{v.climax}</dd><dt>{t.hook}</dt><dd>{v.ending_hook}</dd></dl></article>)}
      <details open><summary>{t.world} · {b.world_rules.length}</summary>{b.world_rules.map((r) => <p key={r.id}><strong>{r.domain}</strong> — {r.rule} <small>{r.id}</small></p>)}</details>
      <details><summary>{t.entities} · {b.entities.length}</summary>{b.entities.map((e) => <article key={e.id}><strong>{e.name}</strong><p>{e.description}</p>{e.initial_state && <dl>{Object.entries(e.initial_state).map(([field, value]) => <div key={field}><dt>{uiText.temporalState.fields[field as TemporalStateField] ?? field}</dt><dd>{temporalValueLabel(field as TemporalStateField, value ?? null, "resolved", Object.fromEntries(b.entities.map((entity) => [entity.id, entity.name])))}</dd></div>)}</dl>}<small>{e.id}</small></article>)}</details>
      <details><summary>{t.arcs}</summary>{b.character_arcs.map((a) => <article key={a.character_id}><h4>{b.entities.find((e) => e.id === a.character_id)?.name ?? a.character_id}</h4><p>{a.initial_state} → {a.final_state}</p><p>{a.desire} · {a.conflict}</p><ol>{a.turning_points.map((point, i) => <li key={i}>{t.volume} {point.volume_index}: {point.change}</li>)}</ol></article>)}</details>
      <details open><summary>{t.style}</summary><dl>{([['name', 'name'], ['pov', 'pov'], ['tense', 'tense'], ['tone', 'tone'], ['diction', 'diction'], ['sentence_rhythm', 'rhythm'], ['dialogue_style', 'dialogue']] as const).map(([field, label]) => <div key={field}><dt>{t[label]}</dt><dd>{b.style_brief[field]}</dd></div>)}<dt>{t.rubric}</dt><dd>{b.style_brief.rubric.join(" · ")}</dd><dt>{t.banned}</dt><dd>{b.style_brief.banned_patterns.join(' · ')}</dd></dl></details>
      <details><summary>{t.causes}</summary>{b.causal_links.map((link) => <p key={link.id}>{link.from_volume} → {link.to_volume}: {link.cause} → {link.effect}</p>)}</details>
      <details><summary>{t.foreshadowing}</summary>{b.foreshadowing.map((f) => <p key={f.id}>{f.seed_volume} → {f.payoff_volume}: {f.clue} → {f.payoff}</p>)}</details>
    </>}
    {plan.expansion && <><h3>{t.volume} {plan.expansion.volume_index}</h3>{plan.expansion.chapters.map((chapter) => <article key={chapter.index}><h4>{chapter.index}. {chapter.title} <small>{chapter.target_length.toLocaleString()}</small></h4><p>{chapter.summary}</p><p>{chapter.purpose}</p>{chapter.scenes.map((scene) => <details key={scene.id} open><summary>{scene.title} · {scene.target_length.toLocaleString()}</summary><p>{scene.summary}</p><dl><dt>{t.goal}</dt><dd>{scene.goal}</dd><dt>{t.conflict}</dt><dd>{scene.conflict}</dd><dt>{t.outcome}</dt><dd>{scene.outcome}</dd><dt>{t.emotion}</dt><dd>{scene.emotional_turn}</dd><dt>{t.timeline}</dt><dd>{scene.timeline_position}</dd></dl><small>{scene.id}</small></details>)}</article>)}</>}
  </section>;
}

export function PlanningWorkspace({ projectId, proposals, busy, canGenerate, modelReady, modelLabel, onGenerate, onExpand, onOpen, onReviewPlan, apiBase, active = true, execute, onOpenRunBundle, runModelReady, reviewModelLabel }: {
  projectId: string; proposals: ProposalArtifact[]; busy: boolean; canGenerate: boolean; modelReady: boolean; modelLabel: string;
  onGenerate: (request: BlueprintRequest) => void; onExpand: (request: ExpansionRequest) => void; onOpen: (id: string) => void; onReviewPlan?: (id: string) => void;
  apiBase?: string; active?: boolean; execute?: (label: string, action: () => Promise<unknown>) => Promise<void>; onOpenRunBundle?: (id: string) => void; runModelReady?: boolean; reviewModelLabel?: string;
}) {
  const t = uiText.planning;
  const [request, setRequest] = useState<BlueprintRequest>({ instruction: "", target_length: 500000, volume_count: 5, chapters_per_volume: 20, scenes_per_chapter: 2 });
  const [blueprintId, setBlueprintId] = useState("");
  const [seedLocked, setSeedLocked] = useState(false);
  const [expansionInstruction, setExpansionInstruction] = useState("");
  const [batchSize, setBatchSize] = useState(5);
  const plans = useMemo(() => proposals.filter((p) => p.project_id === projectId && parseLongformPlan(p)).sort((a, b) => b.updated_at.localeCompare(a.updated_at)), [proposals, projectId]);
  const blueprints = useMemo(() => plans.filter((p) => parseLongformPlan(p)?.phase === "blueprint" && longformApplied(p)), [plans]);
  const blueprint = blueprints.find((p) => p.id === blueprintId) ?? blueprints[0];
  const next = useMemo(() => blueprint ? nextPlanningBatch(blueprint, plans) : null, [blueprint, plans]);
  const locked = busy || seedLocked || !projectId || !canGenerate || !modelReady;
  const setNumber = (field: keyof Omit<BlueprintRequest, "instruction">, value: string) => setRequest((r) => ({ ...r, [field]: Number(value) }));
  return <section className="planning-workspace" aria-label={t.title}>
    <header><p>{t.help}</p><small>{uiText.modelRouting.effective}: {modelLabel}</small></header>
    {(!projectId || !canGenerate || !modelReady) && <p role="status" className="proposal-inline-warning">{!projectId ? t.needsProject : !canGenerate ? t.readonly : t.needsModel}</p>}
    <section className="planning-concept"><h3>{uiText.planningRun.concept}</h3><label>{t.instruction}<textarea required maxLength={12000} rows={4} disabled={busy || seedLocked} value={request.instruction} placeholder={t.instructionPlaceholder} onChange={(e) => setRequest((r) => ({ ...r, instruction: e.target.value }))} /></label>
      <div className="planning-counts">{([
        ['target_length', 'target', 10000, 2000000], ['volume_count', 'volumes', 1, 12], ['chapters_per_volume', 'chapters', 1, 60], ['scenes_per_chapter', 'scenes', 1, 6]
      ] as const).map(([field, label, min, max]) => <label key={field}>{t[label]}<input type="number" required min={min} max={max} value={request[field]} disabled={busy || seedLocked} onChange={(e) => setNumber(field, e.target.value)} /></label>)}</div><p>{t.budget}</p>
    </section>
    {apiBase && execute && <PlanningRunPanel apiBase={apiBase} projectId={projectId} blueprintRequest={request} active={active} canGenerate={canGenerate} modelReady={runModelReady ?? modelReady} reviewModelLabel={reviewModelLabel} seedBlueprints={plans} onSeedRequest={(seedRequest, locked) => { setRequest(seedRequest); setSeedLocked(locked); }} busy={busy} execute={execute} onOpenBundle={onOpenRunBundle ?? onOpen} />}
    <details className="manual-planning"><summary>{uiText.planningRun.manual}</summary><p>{uiText.planningRun.manualHelp}</p><div className="planning-grid"><section><h3>{t.blueprint}</h3><p>{t.budget}</p><button type="button" className="primary" disabled={locked || !blueprintInputValid(request)} onClick={() => onGenerate(request)}><Wand2 size={15} /> {t.generate}</button></section>
    <section><h3>{t.expansion}</h3><label>{t.selectBlueprint}<select value={blueprint?.id ?? ""} disabled={busy || !blueprints.length} onChange={(e) => setBlueprintId(e.target.value)}>{!blueprints.length && <option value="">{t.noBlueprint}</option>}{blueprints.map((p) => <option key={p.id} value={p.id}>{p.title} · v{p.version}</option>)}</select></label>
      {next && <><p>{t.progress}: {next.completedBatches}</p>{next.finished ? <p role="status">{t.finished}</p> : <><p>{t.volume} {next.volume_index} · {t.chapterStart} {next.chapter_start}</p><label>{t.batch}<input type="number" min={1} max={next.chapter_count} value={Math.min(batchSize, next.chapter_count)} disabled={busy} onChange={(e) => setBatchSize(Math.max(1, Math.min(5, Number(e.target.value) || 1)))} /></label><label>{t.instruction}<textarea rows={3} maxLength={12000} value={expansionInstruction} disabled={busy} onChange={(e) => setExpansionInstruction(e.target.value)} /></label><button type="button" className="primary" disabled={locked} onClick={() => blueprint && onExpand({ parent_proposal_id: blueprint.id, parent_version: blueprint.version, volume_index: next.volume_index, chapter_start: next.chapter_start, chapter_count: Math.min(batchSize, next.chapter_count), instruction: expansionInstruction })}><Wand2 size={15} /> {t.expand}</button></>}</>}
      <p>{t.continueHint}</p>
    </section></div><section className="planning-history"><h3>{t.history}</h3>{!plans.length && <p>{t.empty}</p>}{plans.map((p) => { const plan = parseLongformPlan(p)!; return <article key={p.id}><div><strong>{p.title}</strong><small>{plan.phase === "blueprint" ? t.blueprint : `${t.expansion} · ${t.volume} ${plan.expansion?.volume_index}`} · {proposalStatusLabels[p.status]} · v{p.version} · {longformApplied(p) ? t.applied : t.pending}</small></div><div className="planning-history-actions"><button type="button" disabled={busy} onClick={() => onOpen(p.id)}>{t.review}</button>{!longformApplied(p) && onReviewPlan && <button type="button" disabled={busy} onClick={() => onReviewPlan(p.id)}>{uiText.semanticReview.title}</button>}</div></article>; })}</section></details>
  </section>;
}
