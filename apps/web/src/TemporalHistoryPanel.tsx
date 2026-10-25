import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost, type CandidateFact, type GraphNodePayload, type TemporalStateField } from "./api";
import { uiText } from "./localization";
import { temporalValueLabel, type EntityLabels } from "./TemporalStateView";
import { correctionValueAllowed, exactCorrectionSpan, prepareTemporalCorrection, readonlyCorrectionSelection, type ExactCorrectionSelection, type TemporalCorrectionOptions, type TemporalHistory } from "./temporalCorrection";
export function TemporalHistoryPanel({ apiBase, projectId, subjectId, labels, options }: { apiBase: string; projectId: string; subjectId: string; labels: EntityLabels; options: TemporalCorrectionOptions }) {
  const t = uiText.temporalState;
  const [history, setHistory] = useState<TemporalHistory | null>(null);
  const [failed, setFailed] = useState(false);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [target, setTarget] = useState<{ assertion: GraphNodePayload; fingerprint: string } | null>(null);
  const [value, setValue] = useState<string | null>(null);
  const [rationale, setRationale] = useState("");
  const [evidence, setEvidence] = useState<{ draftId: string; version: number; text: string; selection: ExactCorrectionSelection } | null>(null);
  const selectedEvidence = options.draft && evidence?.draftId === options.draft.id && evidence.version === options.draft.version && evidence.text === options.draft.text ? evidence.selection : null;
  const scope = JSON.stringify([apiBase, projectId, subjectId, options.draft?.id, options.draft?.version, options.draftDirty, selectedEvidence?.start, selectedEvidence?.end, selectedEvidence?.text]);
  const activeScope = useRef(scope); activeScope.current = scope;
  useEffect(() => {
    let active = true; setHistory(null); setFailed(false); setTarget(null);
    apiGet<TemporalHistory>(apiBase, `/projects/${encodeURIComponent(projectId)}/temporal-state/history?subject_id=${encodeURIComponent(subjectId)}`).then((result) => { if (active && result.project_id === projectId && result.subject_id === subjectId) setHistory(result); }).catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, [apiBase, projectId, subjectId, refreshVersion]);
  const field = target?.assertion.properties.field as TemporalStateField | undefined;
  const sourceScene = typeof target?.assertion.properties.valid_from_scene === "string" ? target.assertion.properties.valid_from_scene : "";
  const sourceReady = Boolean(target && options.draft && !options.draftDirty && options.sceneId === sourceScene && options.draft.project_id === projectId && options.draft.scene_id === sourceScene);
  const selectionReady = Boolean(sourceReady && options.draft && exactCorrectionSpan(options.draft.text, selectedEvidence));
  const allowed = Boolean(field && correctionValueAllowed(field, value, options.references) && value !== target?.assertion.properties.value);
  async function submit() {
    if (!target || options.busy || !options.canPropose) return;
    const requestScope = scope;
    await options.execute("temporal-correction", async () => {
      const body = await prepareTemporalCorrection({ projectId, assertion: target.assertion, fingerprint: target.fingerprint, draft: options.draft, dirty: options.draftDirty, selection: selectedEvidence, value, rationale, references: options.references });
      if (!body || activeScope.current !== requestScope) return;
      const result = await apiPost<{ candidate: CandidateFact }>(apiBase, `/projects/${encodeURIComponent(projectId)}/temporal-state/corrections`, body);
      if (activeScope.current === requestScope && result.candidate.project_id === projectId) { setTarget(null); await options.onSubmitted(result.candidate); }
    });
  }
  function captureEvidence(event: React.SyntheticEvent<HTMLPreElement>) {
    if (!options.draft || !sourceReady || options.busy) return;
    const selection = readonlyCorrectionSelection(event.currentTarget, options.draft.text, window.getSelection());
    setEvidence(selection ? { draftId: options.draft.id, version: options.draft.version, text: options.draft.text, selection } : null);
  }
  return <section className="temporal-history"><h3>{t.history}: {labels[subjectId] ?? t.subject}</h3><p>{t.correctionHelp}</p><button type="button" disabled={options.busy} onClick={() => setRefreshVersion((n) => n + 1)}>{t.refreshHistory}</button>{failed ? <p role="alert">{t.historyFailed}</p> : !history ? <p>{uiText.common.loading}</p> : history.slots.map((slot) => <section key={slot.field}><h4>{t.fields[slot.field]} · {slot.total_assertions}</h4>{slot.truncated && <p>{t.historyTruncated}</p>}{!slot.assertions.length && <p>{t.noAssertions}</p>}{slot.assertions.map((entry) => { const props = entry.assertion.properties; const scene = typeof props.valid_from_scene === "string" ? props.valid_from_scene : ""; return <article key={entry.assertion.id}><strong>{temporalValueLabel(slot.field, typeof props.value === "string" ? props.value : null, "resolved", labels)} · {entry.active ? t.activeAssertion : t.superseded}</strong><p>{t.effectiveScene}: {labels[scene] ?? t.referenceValue}</p>{entry.active && <button type="button" disabled={options.busy || !options.canPropose} onClick={() => { setTarget({ assertion: entry.assertion, fingerprint: slot.slot_fingerprint }); setValue(typeof props.value === "string" ? props.value : null); setRationale(""); setEvidence(null); }}>{t.correct}</button>}<details><summary>{t.refs}</summary><p>{entry.assertion.id} · {scene}</p><small>{String(props.source_draft_id ?? "")}</small></details></article>; })}</section>)}
    {target && field && <section className="temporal-correction-form"><h4>{t.correct}: {t.fields[field]}</h4><p>{t.oldValue}: {temporalValueLabel(field, typeof target.assertion.properties.value === "string" ? target.assertion.properties.value : null, "resolved", labels)} → {t.newValue}: {temporalValueLabel(field, value, "resolved", labels)}</p>
      {!sourceReady && <p className="proposal-inline-warning">{t.sourceRequired}{options.canOpenSourceScene(sourceScene) && <button type="button" disabled={options.busy} onClick={() => options.onOpenSourceScene(sourceScene)}>{t.openSourceScene}</button>}</p>}
      <label>{t.newValue}<select value={value ?? "__unowned__"} disabled={options.busy} onChange={(e) => setValue(e.target.value === "__unowned__" ? null : e.target.value)}>{field === "life_status" ? ["alive", "dead"].map((item) => <option value={item} key={item}>{t.values[item as "alive" | "dead"]}</option>) : field === "physical_state" ? ["healthy", "injured", "healing"].map((item) => <option value={item} key={item}>{t.values[item as "healthy" | "injured" | "healing"]}</option>) : <>{field === "owner_id" && <option value="__unowned__">{t.unowned}</option>}{value && !options.references.some((ref) => ref.id === value) && <option value={value} disabled>{t.referenceValue}</option>}{options.references.filter((ref) => field === "location_id" ? ref.type === "Location" : ref.type === "Character" || ref.type === "Organization").map((ref) => <option value={ref.id} key={ref.id}>{ref.label}</option>)}</>}</select></label>
      <label>{t.correctionRationale}<textarea rows={3} maxLength={1000} disabled={options.busy} value={rationale} onChange={(e) => setRationale(e.target.value)} /></label><p>{t.exactSelection}</p>{sourceReady && options.draft && <details open><summary>{t.savedEvidence}</summary><pre tabIndex={0} className="temporal-evidence-source" onMouseUp={captureEvidence} onKeyUp={captureEvidence}>{options.draft.text}</pre></details>}{selectionReady ? <blockquote>{selectedEvidence?.text}</blockquote> : <p className="proposal-inline-warning">{t.selectionRequired}</p>}<button type="button" className="primary" disabled={options.busy || !options.canPropose || !sourceReady || !selectionReady || !allowed || !rationale.trim()} onClick={() => { void submit(); }}>{t.submitCorrection}</button><button type="button" disabled={options.busy} onClick={() => setTarget(null)}>{uiText.common.cancel}</button><p>{t.pendingCorrection}</p></section>}
  </section>;
}
