import type { ContextPack } from "./api";
import { uiText } from "./localization";
import type { EntityLabels } from "./TemporalStateView";
type EvidencePack = Pick<ContextPack, "scene_plan" | "canon_entities" | "knowledge_boundaries" | "style_constraints" | "relevant_world_rules" | "retrieved_style_samples" | "provenance">;
const stringItems = (value: unknown): string[] => Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
export function ContextBuildAction({ hasPack, disabled, onBuild }: { hasPack: boolean; disabled: boolean; onBuild: () => void }) {
  return <button type="button" disabled={disabled} onClick={onBuild}>{hasPack ? uiText.contextEvidence.refreshContext : uiText.contextEvidence.buildContext}</button>;
}
export function ContextEvidence({ pack, labels = {} }: { pack: EvidencePack; labels?: EntityLabels }) {
  const t = uiText.contextEvidence;
  const names: EntityLabels = { ...labels };
  for (const entity of pack.canon_entities ?? []) {
    const name = entity.properties.name ?? entity.properties.title;
    if (typeof name === "string" && name.trim()) names[entity.id] = name;
  }
  const name = (id: string) => names[id] ?? t.unresolvedReference;
  const refs = (ids: string[]) => <details><summary>{t.sources}</summary><ul>{ids.map((id, index) => <li key={`${id}:${index}`}>{id}</li>)}</ul></details>;
  const plan = pack.scene_plan?.semantics === "approved_plan_not_realized_facts" ? pack.scene_plan : null;
  const style = pack.style_constraints;
  const hasProfile = typeof style.profile_id === "string" && Boolean(style.profile_id);
  return <section className="context-evidence">
    <details open={Boolean(plan)}><summary>{t.scenePlan}</summary><p>{t.planSemantics}</p>{plan ? <>
      <dl><dt>{t.plannedSummary}</dt><dd>{plan.planned_summary || t.notListed}</dd><dt>{uiText.planning.outcome}</dt><dd>{plan.planned_outcome || t.notListed}</dd><dt>{uiText.planning.emotion}</dt><dd>{plan.emotional_turn || t.notListed}</dd><dt>{uiText.planning.target}</dt><dd>{plan.target_length ?? t.notListed}</dd></dl>
      <h4>{t.causalPreconditions}</h4>{!plan.causal_preconditions.length && <p>{t.notListed}</p>}{plan.causal_preconditions.map((cause) => <article key={cause.relation_id}><strong>{name(cause.scene_id)}</strong><p>{cause.planned_summary || t.notListed}</p><p>{uiText.planning.outcome}: {cause.planned_outcome || t.notListed}</p>{refs([cause.scene_id, cause.relation_id])}</article>)}
      <h4>{t.foreshadowingActions}</h4>{!plan.foreshadowing_actions.length && <p>{t.notListed}</p>}{plan.foreshadowing_actions.map((action) => <article key={action.relation_id}><strong>{action.action === "seed" ? t.seed : t.payoff}: {name(action.id)}</strong><p>{action.clue_text || t.notListed}</p>{action.do_not_reveal_payoff ? <p className="proposal-inline-warning">{t.doNotRevealPayoff}</p> : action.action === "payoff" && <p>{action.planned_payoff || t.notListed}</p>}{action.seed_scene_ids.length > 0 && <p>{t.plannedSeedScenes}: {action.seed_scene_ids.map(name).join(' · ')}</p>}{refs([action.id, action.relation_id, ...action.seed_scene_ids])}</article>)}
    </> : <p>{t.noScenePlan}</p>}</details>
    <details><summary>{t.entryKnowledge}</summary><p>{t.knowledgeSemantics}</p>{!pack.knowledge_boundaries.length && <p>{t.notListed}</p>}{pack.knowledge_boundaries.map((boundary) => <article key={boundary.character_id}><h4>{name(boundary.character_id)}</h4><dl>{(["knows", "does_not_know", "falsely_believes", "suspects", "hides"] as const).map((field) => <div key={field}><dt>{t.knowledgeFields[field]}</dt><dd>{boundary[field].length ? boundary[field].map(name).join(' · ') : t.notListed}</dd></div>)}</dl>{refs([boundary.character_id, ...boundary.knows, ...boundary.does_not_know, ...boundary.falsely_believes, ...boundary.suspects, ...boundary.hides, ...boundary.source_refs])}</article>)}</details>
    <details><summary>{hasProfile ? t.approvedStyle : t.sceneStyle}</summary><dl>{([['pov', 'pov'], ['tense', 'tense'], ['tone', 'tone'], ['diction', 'diction'], ['sentence_rhythm', 'rhythm'], ['dialogue_style', 'dialogue']] as const).map(([field, label]) => <div key={field}><dt>{uiText.planning[label]}</dt><dd>{typeof style[field] === "string" && style[field] ? String(style[field]) : t.notListed}</dd></div>)}<dt>{uiText.planning.rubric}</dt><dd>{stringItems(style.rubric).join(' · ') || t.notListed}</dd><dt>{uiText.planning.banned}</dt><dd>{stringItems(style.banned_patterns).join(' · ') || t.notListed}</dd></dl>{hasProfile && refs([String(style.profile_id), String(style.profile_sha256 ?? "")])}</details>
    <details><summary>{t.worldRules}</summary>{pack.relevant_world_rules.length ? pack.relevant_world_rules.map((rule, index) => <p key={index}>{rule}</p>) : <p>{t.notListed}</p>}</details>
    {pack.retrieved_style_samples.length > 0 && <details><summary>{t.styleSamples}</summary><p>{t.softStyle}</p>{pack.retrieved_style_samples.map((sample, index) => <p key={index}>{sample}</p>)}{refs(pack.provenance.style_sample_refs)}</details>}
    <details><summary>{t.snapshot}</summary><p>{pack.provenance.built_at}</p>{refs([...pack.provenance.graph_query_ids, ...pack.provenance.draft_refs, ...pack.provenance.author_instruction_refs])}</details>
  </section>;
}
