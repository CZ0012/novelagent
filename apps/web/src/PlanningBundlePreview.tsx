import { useEffect, useRef, useState } from "react";
import { apiGet, type ProposalArtifact } from "./api";
import { LongformPreview } from "./PlanningWorkspace";
import { uiText } from "./localization";
import { parsePlanningBranch, pinnedPlanningArtifactMatches, type PlanningBookBundle, type PlanningBranch } from "./planningRuns";
import type { GenerationReviewResult } from "./GenerationReviewPanel";
import { PlanningRunReview } from "./PlanningRunReview";
type LoadedBranch = { id: string; state: "loading" | "ready" | "failed"; branch?: PlanningBranch };
export function PlanningBundlePreview({ apiBase, bundle, onReady }: { apiBase: string; bundle: PlanningBookBundle; onReady?: (ready: boolean) => void }) {
  const t = uiText.planningRun;
  const [branches, setBranches] = useState<LoadedBranch[]>([]);
  const [loadedIdentity, setLoadedIdentity] = useState("");
  const [finalReview, setFinalReview] = useState<GenerationReviewResult | null>(null);
  const callback = useRef(onReady); callback.current = onReady;
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const identity = JSON.stringify(bundle);
  useEffect(() => {
    let active = true; callback.current?.(false);
    const refs = [bundle.blueprint_ref, ...bundle.expansion_refs];
    setLoadedIdentity(identity);
    setBranches(refs.map((ref) => ({ id: ref.id, state: "loading" })));
    setExpanded(new Set([bundle.blueprint_ref.id]));
    let next = 0;
    async function worker() {
      while (active && next < refs.length) {
        const ref = refs[next++];
        let item: LoadedBranch = { id: ref.id, state: "failed" };
        try {
          const proposal = await apiGet<ProposalArtifact>(apiBase, `/projects/${encodeURIComponent(bundle.project_id)}/proposals/${encodeURIComponent(ref.id)}?version=${ref.version}`);
          const branch = parsePlanningBranch(proposal, bundle.run_id);
          if (branch && await pinnedPlanningArtifactMatches(proposal, ref, bundle.project_id)) item = { id: ref.id, state: "ready", branch };
        } catch { /* An unavailable pinned version is not replaced with latest. */ }
        if (active) setBranches((current) => current.map((entry) => entry.id === ref.id ? item : entry));
      }
    }
    void Promise.all([worker(), worker(), worker()]);
    return () => { active = false; };
  }, [apiBase, identity]);
  const verified = loadedIdentity === identity && branches.length === bundle.expansion_refs.length + 1 && branches.every((item) => item.state === "ready") && Boolean(finalReview?.current && finalReview.report.id === bundle.final_review_id && finalReview.report.project_id === bundle.project_id && finalReview.report.status === "pass" && finalReview.report.coverage.canon_complete && finalReview.report.coverage.target_complete);
  useEffect(() => { callback.current?.(verified); }, [verified, identity]);
  return <section className="planning-bundle-preview"><h3>{t.bundle}</h3><p>{t.bundleHelp}</p><PlanningRunReview apiBase={apiBase} projectId={bundle.project_id} runId={bundle.run_id} reviewId={bundle.final_review_id} onResult={setFinalReview} />{branches.map((item, index) => <details key={item.id} open={expanded.has(item.id)} onToggle={(event) => { const open = event.currentTarget.open; setExpanded((current) => { const next = new Set(current); if (open) next.add(item.id); else next.delete(item.id); return next; }); }}><summary>{index === 0 ? uiText.planning.blueprint : `${uiText.planning.expansion} ${index}${item.branch?.expansion ? ` · ${uiText.planning.volume} ${item.branch.expansion.volume_index} · ${uiText.planning.chapterStart} ${item.branch.expansion.chapter_start}` : ""}`}</summary>{item.state === "failed" ? <p className="proposal-inline-warning">{t.childFailed}</p> : item.state === "loading" ? <p>{t.childLoading}</p> : expanded.has(item.id) && item.branch ? <LongformPreview plan={item.branch} /> : null}</details>)}<details><summary>{t.manifest}</summary><p>{bundle.run_id} · {bundle.final_review_id}</p><ul>{[bundle.blueprint_ref, ...bundle.expansion_refs].map((ref) => <li key={ref.id}>{ref.id} · v{ref.version}<small>{ref.body_sha256}</small></li>)}</ul></details></section>;
}
