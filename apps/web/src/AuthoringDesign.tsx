import { AuthoringWriterPolicy } from "./AuthoringWriterPolicy";
import { uiText } from "./localization";
import { authoringCanAdopt, authoringChanges, authoringPatchedWorkspace, type AuthoringEvidence, type AuthoringPatch, type AuthoringProposal, type AuthoringWorkspace } from "./authoring";

export function AuthoringProposalPreview({ before, patch, names = {} }: { before: AuthoringWorkspace; patch: AuthoringPatch; names?: Record<string, string> }) {
  const t = uiText.authoring, after = authoringPatchedWorkspace(before, patch), changes = authoringChanges(before, after);
  const currentCards = !changes.length && patch.upsert_scene_cards.length > 0;
  return <details open><summary>{currentCards ? t.reviewCurrent : `${t.changed} · ${changes.length}`}</summary>{currentCards ? <><p>{t.reviewCurrentHelp}</p><AuthoringDesign workspace={{ items: [], character_plans: [], scene_cards: patch.upsert_scene_cards, reader_records: [] }} names={names} /></> : <AuthoringChanges before={before} after={after} names={names} />}</details>;
}

export function AuthoringProposalOrigin({ proposal }: { proposal: Pick<AuthoringProposal, "supersedes_proposal_id"> }) {
  const t = uiText.authoring;
  return proposal.supersedes_proposal_id ? <aside><p>{t.proposalOrigin}: <code>{proposal.supersedes_proposal_id}</code></p><small>{t.proposalOriginHelp}</small></aside> : null;
}

export function AuthoringProposalActions({ proposal, locked, onDecide }: { proposal: AuthoringProposal; locked: boolean; onDecide: (decision: "adopt" | "reject") => void }) {
  const t = uiText.authoring;
  return <div className="authoring-actions"><button type="button" className="primary" disabled={locked || !authoringCanAdopt(proposal)} onClick={() => onDecide("adopt")}>{t.adopt}</button><button type="button" disabled={locked || proposal.status !== "pending"} onClick={() => onDecide("reject")}>{t.reject}</button></div>;
}

export function AuthoringChanges({ before, after, names = {} }: { before: AuthoringWorkspace; after: AuthoringWorkspace; names?: Record<string, string> }) {
  const t = uiText.authoring;
  function single(kind: keyof AuthoringWorkspace, value: unknown) {
    const workspace: AuthoringWorkspace = { items: [], character_plans: [], scene_cards: [], reader_records: [] };
    if (value !== undefined) Object.assign(workspace, { [kind]: [value] });
    return <AuthoringDesign workspace={workspace} names={names} />;
  }
  return <>{authoringChanges(before, after).map(change => <article className="authoring-card" key={`${change.kind}:${change.id}`}><h4>{change.before === undefined ? t.added : change.after === undefined ? t.removed : t.changed} · {names[change.id] ?? change.id}</h4>{change.before !== undefined && <details><summary>{t.before}</summary>{single(change.kind, change.before)}</details>}{change.after !== undefined && <><strong>{t.after}</strong>{single(change.kind, change.after)}</>}</article>)}</>;
}

export function AuthoringEvidenceList({ evidence }: { evidence: AuthoringEvidence[] }) {
  const t = uiText.authoring;
  return evidence.length ? <details><summary>{t.evidence} · {evidence.length}</summary>{evidence.map((item, index) => <blockquote key={index}><p>{item.expected_text}</p><small>{item.draft.scene_id} · {item.draft.draft_id} v{item.draft.version} · {item.start}–{item.end}</small></blockquote>)}</details> : null;
}

export function AuthoringDesign({ workspace, names = {} }: { workspace: AuthoringWorkspace; names?: Record<string, string> }) {
  const t = uiText.authoring, name = (id: string) => names[id] ?? workspace.scene_cards.flatMap(card => card.writer_policy.characters).find(actor => actor.character_id === id)?.public_name ?? id;
  return <div className="authoring-design">
    {!workspace.items.length && !workspace.character_plans.length && !workspace.scene_cards.length && <p className="authoring-empty">{t.empty}</p>}
    {workspace.items.map(item => <article className="authoring-card" key={item.id}><small>{t[item.kind]} · {item.status === "author_decided" ? t.decided : item.status === "alternative" ? t.alternative : t.open}{item.character_id ? ` · ${name(item.character_id)}` : ""}</small><p>{item.text}</p>{item.rationale && <p>{item.rationale}</p>}{item.depends_on.length > 0 && <small>{t.depends}: {item.depends_on.join("、")}</small>}<AuthoringEvidenceList evidence={item.evidence} /></article>)}
    {workspace.character_plans.map(character => <article className="authoring-card" key={character.character_id}><h4>{name(character.character_id)}</h4><dl><dt>{t.goal}</dt><dd>{character.goal}</dd>{character.belief_item_ids.length > 0 && <><dt>{t.beliefs}</dt><dd>{character.belief_item_ids.map(id => workspace.items.find(item => item.id === id)?.text ?? id).join("；")}</dd></>}{character.knowledge_assumptions.length > 0 && <><dt>{t.assumptions}</dt><dd>{character.knowledge_assumptions.join("；")}</dd></>}<dt>{t.actions}</dt><dd>{character.intended_actions.map(action => action.intention).join("；") || "—"}</dd></dl></article>)}
    {workspace.scene_cards.length > 0 && <h3>{t.sceneCards}</h3>}{workspace.scene_cards.map(card => <article className="authoring-card" key={card.id}><h4>{card.title} <small>v{card.version} · {t[card.status]}</small></h4>{card.pov_character_id && <p>{t.character}: {name(card.pov_character_id)}</p>}<dl><dt>{t.authorSummary}</dt><dd>{card.author_summary || "—"}</dd>{(["chapter_title", "location", "timeline_position", "goal", "conflict", "emotional_turn", "target_length"] as const).map(field => <div key={field}><dt>{t.structureFields[field]}</dt><dd>{card[field] || "—"}</dd></div>)}<dt>{t.entry}</dt><dd>{card.entry_knowledge.map(item => `${name(item.character_id)}: ${item.text}`).join("；") || "—"}</dd><dt>{t.actions}</dt><dd>{card.intended_actions.map(item => `${name(item.character_id)}: ${item.intention}`).join("；") || "—"}</dd><dt>{t.acquired}</dt><dd>{card.acquisitions.length ? <ul>{card.acquisitions.map((item, index) => <li key={index}><p>{name(item.character_id)}: {item.text}</p><small>{item.evidence.length ? t.quotedAcquisition : t.plannedAcquisition}</small><AuthoringEvidenceList evidence={item.evidence} /></li>)}</ul> : "—"}</dd><dt>{t.outcome}</dt><dd>{card.intended_outcome || "—"}</dd><dt>{t.withheld}</dt><dd>{card.withheld.join("；") || "—"}</dd></dl><AuthoringWriterPolicy policy={card.writer_policy} /><AuthoringEvidenceList evidence={card.entry_knowledge.flatMap(item => item.evidence)} /></article>)}
    {workspace.reader_records.length > 0 && <section><h4>{t.reader}</h4>{workspace.reader_records.map((record, index) => <blockquote key={index}><strong>{t.readerPresentation[record.presentation]}</strong><p>{record.expected_text}</p><small>{record.draft_id} v{record.version} · {record.start}–{record.end}</small></blockquote>)}</section>}
  </div>;
}
