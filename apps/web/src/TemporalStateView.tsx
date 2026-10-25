import type { TemporalStateField, TemporalStatePatch, TemporalStateProjection, TemporalStateValue } from "./api";
import { uiText } from "./localization";
export type EntityLabels = Record<string, string>;
const stateFields: TemporalStateField[] = ["life_status", "physical_state", "location_id", "owner_id"];
export function temporalValueLabel(field: TemporalStateField, value: string | null, status: TemporalStateValue["status"], labels: EntityLabels = {}): string {
  const t = uiText.temporalState;
  if (status !== "resolved") return t[status];
  if (value === null) return field === "owner_id" ? t.unowned : t.missingValue;
  if (field === "location_id" || field === "owner_id") return labels[value] ?? t.referenceValue;
  return t.values[value as keyof typeof t.values] ?? value;
}
export function parseTemporalPatch(operation: string, properties: Record<string, unknown>): TemporalStatePatch | null {
  if (operation !== "append_state" || properties.contract_version !== "temporal_state_v1" || !stateFields.includes(properties.field as TemporalStateField) || (properties.value !== null && typeof properties.value !== "string") || typeof properties.valid_from_scene !== "string" || typeof properties.expected_slot_fingerprint !== "string" || typeof properties.source_text_sha256 !== "string") return null;
  if (!properties.valid_from_scene || !/^[a-f0-9]{64}$/.test(properties.expected_slot_fingerprint) || !/^[a-f0-9]{64}$/.test(properties.source_text_sha256)) return null;
  if (properties.field === "life_status" && !["alive", "dead"].includes(properties.value as string)) return null;
  if (properties.field === "physical_state" && !["healthy", "injured", "healing"].includes(properties.value as string)) return null;
  if (properties.field === "location_id" && !properties.value) return null;
  if (properties.field === "owner_id" && properties.value === "") return null;
  return properties as TemporalStatePatch;
}
export function TemporalCandidateNotice({ operation, properties, subjectId, labels = {} }: { operation: string; properties: Record<string, unknown>; subjectId: string; labels?: EntityLabels }) {
  const patch = parseTemporalPatch(operation, properties);
  if (!patch) return null;
  const t = uiText.temporalState;
  return <section className="temporal-candidate"><strong>{patch.action === "correct" ? t.correctionCandidate : t.candidate}</strong><p>{labels[subjectId] ?? t.subject} · {t.fields[patch.field]}: {temporalValueLabel(patch.field, patch.value, "resolved", labels)}</p><p>{t.effectiveScene}: {labels[patch.valid_from_scene] ?? t.referenceValue}</p><small>{patch.action === "correct" ? t.correctionCandidateHelp : t.candidateHelp}</small><details><summary>{t.refs}</summary><p>{subjectId} · {patch.valid_from_scene}</p>{patch.supersedes_assertion_id && <p>{patch.supersedes_assertion_id}</p>}{(patch.field === "location_id" || patch.field === "owner_id") && patch.value && <p>{patch.value}</p>}<small>{patch.source_text_sha256} · {patch.expected_slot_fingerprint}</small></details></section>;
}
export function TemporalContext({ projections, projectId, sceneId, labels = {}, onOpenHistory }: { projections: TemporalStateProjection[]; projectId: string; sceneId: string; labels?: EntityLabels; onOpenHistory?: (subjectId: string) => void }) {
  const t = uiText.temporalState;
  const scoped = projections.filter((item) => item.project_id === projectId && item.scene_id === sceneId);
  if (!scoped.length) return null;
  return <section className="temporal-context"><h3>{t.title}</h3><p>{t.baselineHelp}</p>{scoped.map((projection) => <article key={projection.subject_id}><h4>{labels[projection.subject_id] ?? t.subject} · {projection.at_scene_start ? t.start : t.through}</h4>{onOpenHistory && <button type="button" onClick={() => onOpenHistory(projection.subject_id)}>{t.openHistory}</button>}{!projection.complete && <p className="proposal-inline-warning">{t.incomplete}</p>}<dl>{projection.states.map((state) => <div key={state.field}><dt>{t.fields[state.field]}</dt><dd>{temporalValueLabel(state.field, state.value, state.status, labels)} <small>· {t[state.status]}</small><details><summary>{t.refs}</summary>{(state.field === "location_id" || state.field === "owner_id") && state.value && <p>{state.value}</p>}<ul>{state.assertion_refs.map((ref) => <li key={ref}>{ref}</li>)}</ul>{state.reason && <code>{state.reason}</code>}</details></dd></div>)}</dl><details><summary>{t.refs}</summary><p>{projection.subject_id} · {projection.scene_id}</p></details></article>)}</section>;
}
export function TemporalProposalPreviews({ body, labels = {} }: { body: string; labels?: EntityLabels }) {
  if (body.length > 2000000) return null;
  try {
    const parsed = JSON.parse(body);
    if (!Array.isArray(parsed.candidate_previews)) return null;
    return <>{parsed.candidate_previews.map((item: { id?: unknown; subject_id?: unknown; proposed_graph_patch?: { operation?: unknown; properties?: unknown } }, index: number) => {
      const patch = item?.proposed_graph_patch;
      return item && typeof item.subject_id === "string" && patch && typeof patch.operation === "string" && typeof patch.properties === "object" && patch.properties !== null && !Array.isArray(patch.properties) ? <TemporalCandidateNotice key={typeof item.id === "string" ? item.id : index} subjectId={item.subject_id} operation={patch.operation} properties={patch.properties as Record<string, unknown>} labels={labels} /> : null;
    })}</>;
  } catch { return null; }
}
