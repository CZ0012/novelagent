import { useEffect, useRef, useState } from "react";
import { ShieldCheck, RefreshCw } from "lucide-react";
import { apiGet, apiPost, type ModelExecution, type ProposalArtifact } from "./api";
import { uiText, formatDimension } from "./localization";
import { modelExecutionLabel } from "./ModelRoutingSettings";

export type GenerationReviewTarget = { target_type: "draft" | "proposal"; target_id: string; expected_version: number; scene_id?: string };
export type ReviewFinding = "contradiction" | "required_gap" | "advice";
export function reviewFindingLabel(finding: ReviewFinding = "contradiction"): string { return uiText.semanticReview.findings[finding]; }
export function ReviewFindingBadge({ finding = "contradiction" }: { finding?: ReviewFinding }) { return <small className="unsaved-badge" data-finding={finding}>{reviewFindingLabel(finding)}</small>; }
export type GenerationReviewReport = {
  contract_version: "generation_review_v1"; id: string; project_id: string; target_type: "draft" | "proposal"; target_id: string; target_version: number; purpose?: "scene" | "plan"; scene_id?: string | null; canon_evidence_fingerprint: string; output_language: string; target_text_sha256: string; canon_fingerprint: string; style_fingerprint: string;
  status: "pass" | "needs_revision" | "blocked" | "inconclusive"; summary: string;
  issues: Array<{ id: string; finding?: ReviewFinding; dimension: string; severity: "low" | "medium" | "high" | "critical"; description: string; suggestion: string; evidence: Array<{ kind: "target" | "canon" | "style"; ref: string; quote: string }> }>;
  dimensions_checked: string[]; coverage: { method: "semantic_model" | "deterministic_only"; canon_complete: boolean; target_complete: boolean; scope: "scene" | "project" | "plan"; omitted_unrelated_facts: number; missing_context: string[]; limitations: string[] }; model_execution?: ModelExecution | null; created_at: string;
};
export type GenerationReviewResult = { report: GenerationReviewReport; current: boolean };
export function reviewMatchesTarget(result: GenerationReviewResult, projectId: string, target: GenerationReviewTarget | null): boolean {
  return Boolean(target && result.current && result.report.project_id === projectId && result.report.target_type === target.target_type && result.report.target_id === target.target_id && result.report.target_version === target.expected_version);
}
export function reviewAllowsAdoption(result: GenerationReviewResult | null, projectId: string, target: GenerationReviewTarget): boolean {
  return Boolean(result && reviewMatchesTarget(result, projectId, target) && result.report.status === "pass" && result.report.coverage.canon_complete && result.report.coverage.target_complete);
}
export function reviewAllowsPlanApplication(result: GenerationReviewResult | null, projectId: string, target: GenerationReviewTarget): boolean {
  return reviewAllowsAdoption(result, projectId, target) && result?.report.purpose === "plan" && result.report.coverage.scope === "plan";
}
/** Acceptance and author edits can change provenance; review policy belongs to the Project. */
export function proposalSemanticReviewBlocked(proposal: ProposalArtifact | null, result: GenerationReviewResult | null, projectId: string, required: boolean): boolean {
  if (!proposal || proposal.artifact_type !== "scene_draft") return false;
  const attached = result?.report.project_id === projectId && result.report.target_type === "proposal" && result.report.target_id === proposal.id;
  return (required || attached) && !reviewAllowsAdoption(result, projectId, { target_type: "proposal", target_id: proposal.id, expected_version: proposal.version });
}
export function GenerationReviewPanel({ apiBase, projectId, target, dirty, busy, canGenerate, modelReady, modelLabel, execute, onReport, onExtract, extractionReady = false, extractionModelLabel }: {
  apiBase: string; projectId: string; target: GenerationReviewTarget | null; dirty: boolean; busy: boolean; canGenerate: boolean; modelReady: boolean; modelLabel: string;
  onExtract?: () => void; extractionReady?: boolean; extractionModelLabel?: string;
  execute: (label: string, action: () => Promise<unknown>) => Promise<void>; onReport: (result: GenerationReviewResult | null) => void;
}) {
  const t = uiText.semanticReview;
  const [reports, setReports] = useState<GenerationReviewResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const sequence = useRef(0);
  const scope = JSON.stringify([apiBase, projectId, target?.target_type, target?.target_id, target?.expected_version, target?.scene_id]);
  const activeScope = useRef(scope); activeScope.current = scope;
  const callback = useRef(onReport); callback.current = onReport;
  useEffect(() => {
    const requestSequence = ++sequence.current;
    setReports([]); callback.current(null); setFailed(false); setLoading(false);
    if (!target || !projectId) return;
    setLoading(true);
    const url = `/projects/${encodeURIComponent(projectId)}/generation-reviews?target_type=${target.target_type}&target_id=${encodeURIComponent(target.target_id)}`;
    apiGet<{ reports: GenerationReviewResult[] }>(apiBase, url).then((result) => {
      if (sequence.current !== requestSequence || activeScope.current !== scope) return;
      const items = result.reports.filter((item) => item.report.project_id === projectId && item.report.target_type === target.target_type && item.report.target_id === target.target_id);
      setReports(items); callback.current(items.find((item) => reviewMatchesTarget(item, projectId, target)) ?? items[0] ?? null);
    }).catch(() => { if (sequence.current === requestSequence) setFailed(true); }).finally(() => { if (sequence.current === requestSequence) setLoading(false); });
    return () => { sequence.current++; };
  }, [apiBase, projectId, scope]);
  async function refresh() {
    if (!target || !projectId) return;
    const requestScope = scope; const requestSequence = ++sequence.current;
    setLoading(true); setFailed(false);
    try {
      const result = await apiGet<{ reports: GenerationReviewResult[] }>(apiBase, `/projects/${encodeURIComponent(projectId)}/generation-reviews?target_type=${target.target_type}&target_id=${encodeURIComponent(target.target_id)}`);
      if (activeScope.current !== requestScope || sequence.current !== requestSequence) return;
      const items = result.reports.filter((item) => item.report.project_id === projectId && item.report.target_type === target.target_type && item.report.target_id === target.target_id);
      setReports(items); callback.current(items.find((item) => reviewMatchesTarget(item, projectId, target)) ?? items[0] ?? null);
    } catch { if (activeScope.current === requestScope) setFailed(true); }
    finally { if (activeScope.current === requestScope && sequence.current === requestSequence) setLoading(false); }
  }
  async function generate() {
    if (!target || dirty || !projectId || !canGenerate || !modelReady) return;
    const requestScope = scope; const requestSequence = ++sequence.current;
    const result = await apiPost<GenerationReviewResult>(apiBase, `/projects/${encodeURIComponent(projectId)}/generation-reviews`, target);
    if (activeScope.current !== requestScope || sequence.current !== requestSequence) return;
    if (result.report.project_id !== projectId || result.report.target_type !== target.target_type || result.report.target_id !== target.target_id || result.report.target_version !== target.expected_version) return;
    setReports((items) => [result, ...items.filter((item) => item.report.id !== result.report.id)]); callback.current(result);
  }

  return <section className="semantic-review-panel" aria-label={t.title}>
    <h3><ShieldCheck size={18} /> {t.title}</h3><p>{t.help}</p><p>{t.independent}</p>
    <small>{modelLabel}</small>
    {!target ? <p role="status">{t.noTarget}</p> : <p>{target.target_id} · {t.version} {target.expected_version}</p>}
    {dirty && <p className="proposal-inline-warning" role="status">{t.dirty}</p>}
    {!modelReady && <p className="proposal-inline-warning">{t.modelMissing}</p>}
    <div className="semantic-review-actions"><button type="button" className="primary" disabled={busy || loading || dirty || !target || !canGenerate || !modelReady} onClick={() => { void execute("semantic-review", generate); }}><ShieldCheck size={15} />{t.generate}</button><button type="button" disabled={busy || loading || !target} onClick={() => { void refresh(); }}><RefreshCw size={15} />{t.refresh}</button></div>
    {loading && <p role="status">{uiText.common.loading}</p>}{failed && <p role="alert">{t.failed}</p>}
    {!reports.length && !loading && <p>{t.empty}</p>}
    {target?.target_type === "draft" && onExtract && <section className="natural-state-extraction"><h4>{t.extract}</h4><p>{t.extractionHelp}</p><small>{t.extractionModel}: {extractionModelLabel}</small><button type="button" disabled={busy || loading || dirty || !canGenerate || !extractionReady} onClick={onExtract}>{t.extract}</button></section>}
    {reports.map((item) => { const report = item.report; const current = !dirty && reviewMatchesTarget(item, projectId, target); return <article className={`semantic-report ${report.status}`} key={report.id}>
      <h4>{t[report.status]}</h4><strong>{current ? t.current : t.stale}</strong><p>{report.summary}</p><small>{t.version} {report.target_version} · {report.created_at}</small>
      <p>{t.dimensions}: {report.dimensions_checked.map((d) => formatDimension(d)).join(' · ')}</p>
      <details open><summary>{t.coverage}</summary><p>{report.coverage.method === "semantic_model" ? t.semantic : t.deterministic}</p><p>{report.coverage.scope === "plan" ? t.planScope : report.coverage.scope === "scene" ? t.sceneScope : t.projectScope} · {t.omitted}: {report.coverage.omitted_unrelated_facts}</p><p>{t.canonComplete}: {report.coverage.canon_complete ? t.yes : t.no} · {t.targetComplete}: {report.coverage.target_complete ? t.yes : t.no}</p>{[...report.coverage.missing_context, ...report.coverage.limitations].length > 0 && <><h5>{t.limitations}</h5><ul>{[...report.coverage.missing_context, ...report.coverage.limitations].map((line, i) => <li key={i}>{line}</li>)}</ul></>}</details>
      {report.issues.map((issue) => <section className="semantic-issue" key={issue.id}><h5><ReviewFindingBadge finding={issue.finding} /> {formatDimension(issue.dimension)} · {t[issue.severity]}</h5><p>{issue.description}</p><strong>{t.suggestion}</strong><p>{issue.suggestion}</p><details><summary>{t.evidence}</summary>{issue.evidence.map((evidence, i) => <blockquote key={i}><small>{t[evidence.kind]} · {evidence.ref}</small><p>{evidence.quote}</p></blockquote>)}</details></section>)}
      {report.model_execution && <small>{modelExecutionLabel(report.model_execution)}</small>}
    </article>; })}
  </section>;
}
