import { uiText } from "./localization";
export function ObservationNotice({ operation }: { operation: string }) {
  return operation === "none" ? <p className="proposal-inline-warning"><strong>{uiText.semanticReview.observation}</strong> · {uiText.semanticReview.observationHelp}</p> : null;
}
export function observationPreviews(body: string): Array<{ id: string; value: string }> {
  if (body.length > 2000000) return [];
  try { const parsed = JSON.parse(body); return Array.isArray(parsed.candidate_previews) ? parsed.candidate_previews.filter((item: unknown) => typeof item === "object" && item !== null && "proposed_graph_patch" in item && typeof item.proposed_graph_patch === "object" && item.proposed_graph_patch !== null && "operation" in item.proposed_graph_patch && item.proposed_graph_patch.operation === "none").map((item: { id?: unknown; value?: unknown }, i: number) => ({ id: typeof item.id === "string" ? item.id : String(i), value: typeof item.value === "string" ? item.value : "" })) : []; } catch { return []; }
}
export function FactProposalObservations({ body }: { body: string }) {
  const observations = observationPreviews(body);
  return observations.length ? <section><ObservationNotice operation="none" />{observations.map((item) => <p key={item.id}>{item.value}</p>)}</section> : null;
}
