import { useEffect, useRef, useState } from "react";
import { apiGet } from "./api";
import type { GenerationReviewResult } from "./GenerationReviewPanel";
import { formatDimension, uiText } from "./localization";
export function PlanningRunReview({ apiBase, projectId, runId, reviewId, onResult }: { apiBase: string; projectId: string; runId: string; reviewId: string; onResult?: (result: GenerationReviewResult | null) => void }) {
  const [result, setResult] = useState<GenerationReviewResult | null>(null);
  const [failed, setFailed] = useState(false);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const callback = useRef(onResult); callback.current = onResult;
  useEffect(() => {
    let active = true; setResult(null); setFailed(false); callback.current?.(null);
    apiGet<GenerationReviewResult>(apiBase, `/projects/${encodeURIComponent(projectId)}/planning-runs/${encodeURIComponent(runId)}/reviews/${encodeURIComponent(reviewId)}`).then((value) => { if (active) { if (value.report.id === reviewId && value.report.project_id === projectId) { setResult(value); callback.current?.(value); } else setFailed(true); } }).catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, [apiBase, projectId, runId, reviewId, refreshVersion]);
  const t = uiText.planningRun;
  const r = result?.report;
  return <section className="planning-run-review"><h3>{t.finalReview}</h3><p>{t.finalReviewHelp}</p><button type="button" onClick={() => setRefreshVersion((version) => version + 1)}>{uiText.semanticReview.refresh}</button>{failed ? <p className="proposal-inline-warning">{t.finalReviewFailed}</p> : !r ? <p>{uiText.common.loading}</p> : <><strong>{uiText.semanticReview[r.status]} · {result?.current ? uiText.semanticReview.current : uiText.semanticReview.stale}</strong><p>{r.summary}</p><p>{uiText.semanticReview.dimensions}: {r.dimensions_checked.map(formatDimension).join(' · ')}</p><p>{uiText.semanticReview.canonComplete}: {r.coverage.canon_complete ? uiText.semanticReview.yes : uiText.semanticReview.no} · {uiText.semanticReview.targetComplete}: {r.coverage.target_complete ? uiText.semanticReview.yes : uiText.semanticReview.no}</p>{[...r.coverage.missing_context, ...r.coverage.limitations].length > 0 && <ul>{[...r.coverage.missing_context, ...r.coverage.limitations].map((text, i) => <li key={i}>{text}</li>)}</ul>}{r.issues.map((issue) => <article key={issue.id}><strong>{formatDimension(issue.dimension)} · {uiText.semanticReview[issue.severity]}</strong><p>{issue.description}</p><p>{issue.suggestion}</p><details><summary>{uiText.semanticReview.evidence}</summary>{issue.evidence.map((e, i) => <blockquote key={i}><small>{e.ref}</small><p>{e.quote}</p></blockquote>)}</details></article>)}<details><summary>{t.refs}</summary><p>{r.id} · {r.target_id} · v{r.target_version}</p></details></>}</section>;
}
