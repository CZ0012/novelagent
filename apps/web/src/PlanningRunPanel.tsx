import { useCallback, useEffect, useRef, useState } from "react";
import { apiGet, apiPost, type ProposalArtifact } from "./api";
import { parseLongformPlan, longformApplied, type BlueprintRequest } from "./longformPlanning";
import { APP_LOCALE, uiText } from "./localization";
import { MAX_PLANNING_RUN_CALLS, planningRunCanResume, planningRunCopyBlueprintBody, copyPlanningRunBlueprint, planningRunCreateRequest, planningRunResumeBody, planningRunRecheckBody, mergePlanningRunRecords, planningRunInputValid, planningRunNeedsUncertainRetry, planningRunReady, type PlanningRun, type PlanningRunRequest, type PlanningRevisionMode } from "./planningRuns";
import type { GenerationReviewResult } from "./GenerationReviewPanel";
import { PlanningRunReview } from "./PlanningRunReview";
export function planningRunOptionLabel(run: PlanningRun, ordinal: number): string {
  const date = new Date(run.updated_at);
  const updated = Number.isNaN(date.getTime()) ? uiText.common.notSet : new Intl.DateTimeFormat(APP_LOCALE, { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(date);
  return `${uiText.planningRun.runName} ${ordinal} · ${uiText.planningRun.statuses[run.status]} · ${updated}`;
}
export function PlanningRestartControls({ busy, mode, preserveLater, instruction, onMode, onPreserve, onInstruction }: {
  busy: boolean; mode: PlanningRevisionMode; preserveLater: boolean; instruction: string;
  onMode: (mode: PlanningRevisionMode) => void; onPreserve: (preserve: boolean) => void; onInstruction: (instruction: string) => void;
}) {
  const t = uiText.planningRun;
  return <><label>{t.currentRevisionMode}<select disabled={busy} value={mode} onChange={(event) => onMode(event.target.value as PlanningRevisionMode)}><option value="targeted">{uiText.planning.targetedRevision}</option><option value="full">{t.fullStageRevision}</option></select></label><label>{t.laterOutputs}<select disabled={busy} value={preserveLater ? "retain" : "regenerate"} onChange={(event) => onPreserve(event.target.value === "retain")}><option value="regenerate">{t.regenerateLater}</option><option value="retain">{t.preserveLater}</option></select></label><p>{preserveLater ? t.preserveLaterHelp : t.regenerateLaterHelp}</p><label>{mode === "full" ? t.fullStageInstruction : t.restartInstruction}<textarea rows={3} maxLength={12000} disabled={busy} value={instruction} onChange={(event) => onInstruction(event.target.value)} /></label>{mode === "full" && !instruction.trim() && <p className="proposal-inline-warning">{t.fullStageRequired}</p>}</>;
}
export function PlanningRunProgress({ run, onOpenBundle, finalReviewReady = false }: { run: PlanningRun; finalReviewReady?: boolean; onOpenBundle?: (id: string) => void }) {
  const t = uiText.planningRun;
  const passed = run.steps.filter((step) => step.status === "passed").length;
  const ready = planningRunReady(run) && (run.status === "completed" || finalReviewReady);
  return <section className="planning-run-progress"><h3>{t.statuses[run.status]}</h3><p>{run.status === "completed" && ready ? t.applied : t.staged}</p><dl><div><dt>{t.stage}</dt><dd>{t.stages[run.stage]}</dd></div><div><dt>{t.calls}</dt><dd>{run.calls_reserved} / {run.max_calls}</dd></div><div><dt>{t.steps}</dt><dd>{passed} / {run.steps.length}</dd></div></dl>{run.stop_requested && <p role="status">{t.stopping}</p>}{run.pause_reason && <p className="proposal-inline-warning">{t.paused}: {t.pauseReasons[run.pause_reason as keyof typeof t.pauseReasons] ?? run.pause_reason}</p>}<p role="status">{ready ? run.status === "completed" ? t.applied : t.ready : t.gaps}</p>{ready && run.bundle_proposal_id && onOpenBundle && <button type="button" onClick={() => onOpenBundle(run.bundle_proposal_id!)}>{t.review}</button>}<details><summary>{t.steps}</summary><ol>{run.steps.map((step) => <li key={step.index}><strong>{step.phase === "blueprint" ? uiText.planning.blueprint : `${uiText.planning.volume} ${step.volume_index} · ${uiText.planning.chapterStart} ${step.chapter_start} · ${step.chapter_count}`}</strong> · {t.stepStatuses[step.status]} · {uiText.planningRun.repairs}: {step.repairs}{step.retained_output_ref && step.status !== "passed" && <small className="unsaved-badge">{t.retainedPending}</small>}{(step.proposal_ref || step.review_id || step.retained_output_ref) && <details><summary>{t.refs}</summary>{step.proposal_ref && <><p>{t.currentArtifact}: {step.proposal_ref.id} · v{step.proposal_ref.version}</p><small>{step.proposal_ref.body_sha256} · {step.review_id}</small></>}{step.retained_output_ref && <><p>{t.retainedSource}: {step.retained_output_ref.id} · v{step.retained_output_ref.version}</p><small>{step.retained_output_ref.body_sha256}</small></>}</details>}</li>)}</ol></details><details><summary>{t.refs}</summary><p>{run.id} · v{run.version}</p><small>{run.canon_fingerprint}</small>{run.pending_call && <p>{run.pending_call.id} · {run.pending_call.operation}</p>}</details></section>;
}
export function PlanningRunPanel({ apiBase, projectId, blueprintRequest, active, canGenerate, modelReady, busy, execute, onOpenBundle, reviewModelLabel, seedBlueprints = [], onSeedRequest, onBlueprintCopied }: {
  apiBase: string; projectId: string; blueprintRequest: BlueprintRequest; active: boolean; canGenerate: boolean; modelReady: boolean; busy: boolean;
  onBlueprintCopied?: (proposal: ProposalArtifact) => Promise<void>;
  reviewModelLabel?: string; seedBlueprints?: ProposalArtifact[]; onSeedRequest?: (request: BlueprintRequest, locked: boolean) => void;
  execute: (label: string, action: () => Promise<unknown>) => Promise<void>; onOpenBundle: (id: string) => void;
}) {
  const t = uiText.planningRun;
  const [batchSize, setBatchSize] = useState(5);
  const [maxCalls, setMaxCalls] = useState(80);
  const [maxRepairs, setMaxRepairs] = useState(2);
  const [resumeBudget, setResumeBudget] = useState<number | null>(null);
  const [restartStep, setRestartStep] = useState<number | null>(null);
  const [revisionInstruction, setRevisionInstruction] = useState("");
  const [restartMode, setRestartMode] = useState<PlanningRevisionMode>("targeted");
  const [preserveLater, setPreserveLater] = useState(false);
  const [seed, setSeed] = useState<{ id: string; version: number; request: BlueprintRequest; title: string } | null>(null);
  const unseededRequest = useRef(blueprintRequest);
  const seeds = seedBlueprints.filter((proposal) => proposal.project_id === projectId && !longformApplied(proposal) && parseLongformPlan(proposal)?.phase === "blueprint");
  const seedAvailable = !seed || seeds.some((proposal) => proposal.id === seed.id && proposal.version === seed.version);
  function chooseSeed(key: string) {
    if (!key) { setSeed(null); onSeedRequest?.(unseededRequest.current, false); return; }
    const proposal = seeds.find((item) => `${item.id}:${item.version}` === key); const plan = proposal ? parseLongformPlan(proposal) : null;
    if (!proposal || !plan || plan.phase !== "blueprint") return;
    if (!seed) unseededRequest.current = blueprintRequest;
    const request = plan.request as BlueprintRequest;
    setSeed({ id: proposal.id, version: proposal.version, request, title: proposal.title }); onSeedRequest?.(request, true);
  }
  const [runs, setRuns] = useState<PlanningRun[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [loading, setLoading] = useState(false);
  const [mutating, setMutating] = useState(false);
  const [failed, setFailed] = useState(false);
  const [finalReview, setFinalReview] = useState<GenerationReviewResult | null>(null);
  const scope = JSON.stringify([apiBase, projectId]);
  const activeScope = useRef(scope); activeScope.current = scope;
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const run = runs.find((item) => item.id === selectedId) ?? runs[0] ?? null;
  const merge = useCallback((incoming: PlanningRun) => {
    if (incoming.project_id !== projectId) return;
    setRuns((items) => mergePlanningRunRecords(items, incoming, projectId));
  }, [projectId]);
  const refresh = useCallback(async () => {
    if (!projectId) return;
    const requestScope = scope; setLoading(true); setFailed(false);
    try { const response = await apiGet<{ runs: PlanningRun[] }>(apiBase, `/projects/${encodeURIComponent(projectId)}/planning-runs`); if (alive.current && activeScope.current === requestScope) { const scoped = response.runs.filter((item) => item.project_id === projectId).sort((a, b) => b.updated_at.localeCompare(a.updated_at)); scoped.forEach(merge); setSelectedId((current) => current || scoped[0]?.id || ""); } }
    catch { if (alive.current && activeScope.current === requestScope) setFailed(true); }
    finally { if (alive.current && activeScope.current === requestScope) setLoading(false); }
  }, [apiBase, projectId, scope, merge]);
  useEffect(() => { setRuns([]); setSelectedId(""); setResumeBudget(null); }, [scope]);
  useEffect(() => { if (active) void refresh(); }, [active, refresh]);
  useEffect(() => { setResumeBudget(null); setRestartStep(null); setRevisionInstruction(""); setRestartMode("targeted"); setPreserveLater(false); }, [run?.id]);
  // Polls are reads only. Reloading or selecting a paused run never resumes a paid operation.
  useEffect(() => {
    if (!active || !run || !["running", "queued"].includes(run.status)) return;
    const runId = run.id; const requestScope = scope;
    let disposed = false; let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try { const response = await apiGet<{ run: PlanningRun }>(apiBase, `/projects/${encodeURIComponent(projectId)}/planning-runs/${encodeURIComponent(runId)}`); if (!disposed && alive.current && activeScope.current === requestScope && response.run.id === runId) merge(response.run); }
      catch { if (!disposed && activeScope.current === requestScope) setFailed(true); }
      if (!disposed) timer = setTimeout(poll, 3000);
    };
    timer = setTimeout(poll, 1500);
    return () => { disposed = true; clearTimeout(timer); };
  }, [active, apiBase, projectId, run?.id, run?.status, scope, merge]);
  const request: PlanningRunRequest = planningRunCreateRequest(blueprintRequest, batchSize, maxCalls, maxRepairs, seed);
  const locked = busy || mutating || !projectId || !canGenerate || !modelReady;
  async function mutate(path: string, body: unknown) {
    const requestScope = scope;
    setMutating(true);
    try { await execute("planning-run", async () => { const response = await apiPost<{ run: PlanningRun }>(apiBase, `/projects/${encodeURIComponent(projectId)}/planning-runs${path}`, body); if (alive.current && activeScope.current === requestScope && response.run.project_id === projectId) { merge(response.run); setSelectedId(response.run.id); setResumeBudget(null); setRestartStep(null); setRevisionInstruction(""); setRestartMode("targeted"); setPreserveLater(false); } }); }
    finally { if (alive.current && activeScope.current === requestScope) setMutating(false); }
  }
  const nextBudget = resumeBudget ?? run?.max_calls ?? 80;
  const uncertain = run ? planningRunNeedsUncertainRetry(run) : false;
  const canResume = run ? planningRunCanResume(run, nextBudget) && Boolean(planningRunResumeBody(run, true, nextBudget, restartStep, revisionInstruction, restartStep === null ? undefined : { preserve_later_outputs: preserveLater, revision_mode: restartMode })) : false;
  function resume(explicitUncertainConsent: boolean) {
    if (!run || locked) return;
    const body = planningRunResumeBody(run, explicitUncertainConsent, nextBudget, restartStep, revisionInstruction, restartStep === null ? undefined : { preserve_later_outputs: preserveLater, revision_mode: restartMode });
    if (body) void mutate(`/${encodeURIComponent(run.id)}/resume`, body);
  }
  async function copyPassedBlueprint() {
    if (!run || busy || mutating || !canGenerate || !planningRunCopyBlueprintBody(run)) return;
    const requestScope = scope; setMutating(true);
    try { await execute("planning-blueprint-copy", async () => {
      const proposal = await copyPlanningRunBlueprint(apiBase, projectId, run);
      const plan = parseLongformPlan(proposal);
      if (!alive.current || activeScope.current !== requestScope || proposal.project_id !== projectId || !plan || plan.phase !== "blueprint" || longformApplied(proposal)) return;
      await onBlueprintCopied?.(proposal);
      if (!alive.current || activeScope.current !== requestScope) return;
      if (!seed) unseededRequest.current = blueprintRequest;
      const request = plan.request as BlueprintRequest;
      setSeed({ id: proposal.id, version: proposal.version, request, title: proposal.title }); onSeedRequest?.(request, true);
    }); } finally { if (alive.current && activeScope.current === requestScope) setMutating(false); }
  }
  function recheckCurrentResult() {
    if (!run || locked) return;
    const body = planningRunRecheckBody(run);
    if (body) void mutate(`/${encodeURIComponent(run.id)}/resume`, body);
  }
  return <section className="planning-run-panel" aria-label={t.title}><h2>{t.title}</h2><p>{t.help}</p><label>{t.startFrom}<select disabled={busy || mutating} value={seed ? `${seed.id}:${seed.version}` : ""} onChange={(event) => chooseSeed(event.target.value)}><option value="">{t.startConcept}</option>{seed && !seedAvailable && <option value={`${seed.id}:${seed.version}`} disabled>{seed.title} · v{seed.version} · {t.seedStale}</option>}{seeds.map((proposal) => <option key={`${proposal.id}:${proposal.version}`} value={`${proposal.id}:${proposal.version}`}>{t.useBlueprint}: {proposal.title} · v{proposal.version}</option>)}</select></label>{seed && <p>{t.seedHelp}</p>}{!seedAvailable && <p className="proposal-inline-warning">{t.seedStale}</p>}{reviewModelLabel && <small>{reviewModelLabel}</small>}{!modelReady && <p className="proposal-inline-warning">{uiText.semanticReview.modelMissing}</p>}<div className="planning-run-budgets"><label>{t.batch}<input type="number" min={1} max={5} value={batchSize} disabled={busy || mutating} onChange={(e) => setBatchSize(Number(e.target.value))} /></label><label>{t.maxCalls}<input type="number" min={1} max={MAX_PLANNING_RUN_CALLS} value={maxCalls} disabled={busy || mutating} onChange={(e) => setMaxCalls(Number(e.target.value))} /></label><label>{t.repairs}<input type="number" min={0} max={2} value={maxRepairs} disabled={busy || mutating} onChange={(e) => setMaxRepairs(Number(e.target.value))} /></label></div><p>{t.budgetHelp}</p>{!planningRunInputValid(request) && <p>{t.inputRequired}</p>}<button type="button" className="primary" disabled={locked || !seedAvailable || !planningRunInputValid(request)} onClick={() => { void mutate("", request); }}>{t.create}</button><div className="planning-run-list"><h3>{t.history}</h3><button type="button" disabled={loading || mutating} onClick={() => { void refresh(); }}>{t.refresh}</button>{loading && <p>{uiText.common.loading}</p>}{failed && <p role="alert">{t.failed}</p>}{!runs.length && !loading && <p>{t.empty}</p>}{runs.length > 0 && <label>{t.select}<select disabled={mutating} value={run?.id ?? ""} onChange={(e) => { setSelectedId(e.target.value); setResumeBudget(null); setRestartStep(null); setRevisionInstruction(""); setRestartMode("targeted"); setPreserveLater(false); }}>{runs.map((item, index) => <option value={item.id} key={item.id}>{planningRunOptionLabel(item, index + 1)}</option>)}</select></label>}</div>{run && <><PlanningRunProgress run={run} finalReviewReady={Boolean(finalReview?.current && finalReview.report.id === run.final_review_id && finalReview.report.project_id === projectId && finalReview.report.status === "pass" && finalReview.report.coverage.canon_complete && finalReview.report.coverage.target_complete)} onOpenBundle={onOpenBundle} /><div className="planning-run-actions">{planningRunCopyBlueprintBody(run) && <><button type="button" disabled={busy || mutating || !canGenerate} onClick={() => { void copyPassedBlueprint(); }}>{t.copyBlueprint}</button><small>{t.copyBlueprintHelp}</small></>}{["queued", "running"].includes(run.status) && <button type="button" disabled={busy || mutating || run.stop_requested || !canGenerate} onClick={() => { void mutate(`/${encodeURIComponent(run.id)}/stop`, { expected_version: run.version }); }}>{t.stop}</button>}{run.status === "paused" && <><details className="planning-run-restart"><summary>{t.restartAdvanced}</summary><p>{t.restartHelp}</p><label>{t.restartStage}<select disabled={busy || mutating} value={restartStep === null ? "" : String(restartStep)} onChange={(event) => { setRestartStep(event.target.value === "" ? null : Number(event.target.value)); setRevisionInstruction(""); setRestartMode("targeted"); setPreserveLater(false); }}><option value="">{t.resumeExisting}</option>{run.steps.map((step) => <option key={step.index} value={step.index}>{step.index + 1}. {step.phase === "blueprint" ? uiText.planning.blueprint : `${uiText.planning.volume} ${step.volume_index} · ${uiText.planning.chapterStart} ${step.chapter_start}`}</option>)}</select></label>{restartStep !== null && <PlanningRestartControls busy={busy || mutating} mode={restartMode} preserveLater={preserveLater} instruction={revisionInstruction} onMode={setRestartMode} onPreserve={setPreserveLater} onInstruction={setRevisionInstruction} />}</details><label>{t.resumeBudget}<input type="number" min={run.max_calls} max={MAX_PLANNING_RUN_CALLS} value={nextBudget} disabled={busy || mutating} onChange={(e) => setResumeBudget(Number(e.target.value))} /></label>{uncertain ? <><p className="proposal-inline-warning">{t.uncertain}</p><button type="button" disabled={locked || !canResume} onClick={() => resume(true)}>{t.retryUncertain}</button></> : <button type="button" disabled={locked || !canResume} onClick={() => resume(false)}>{t.resume}</button>}{!uncertain && planningRunRecheckBody(run) && <button type="button" disabled={locked} title={t.recheckHelp} onClick={recheckCurrentResult}>{t.recheck}</button>}</>}</div>{run.final_review_id && <PlanningRunReview apiBase={apiBase} projectId={projectId} runId={run.id} reviewId={run.final_review_id} onResult={setFinalReview} />}</>}</section>;
}
