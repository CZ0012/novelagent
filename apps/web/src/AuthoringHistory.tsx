import { useEffect, useRef, useState } from "react";
import { readAuthoringHistory, readAuthoringProposal, type AuthoringHistoryKind, type AuthoringHistoryPage, type AuthoringProposal, type AuthoringSession } from "./authoring";
import { AuthoringDesign, AuthoringEvidenceList, AuthoringProposalOrigin } from "./AuthoringDesign";
import { uiText } from "./localization";

export function AuthoringHistoricalProposal({ proposal, names = {} }: { proposal: AuthoringProposal; names?: Record<string, string> }) {
  const t = uiText.authoring, patch = proposal.patch;
  const removed = [...patch.remove_item_ids, ...patch.remove_character_ids, ...patch.remove_card_ids];
  return <article className="authoring-proposal"><h4>{proposal.summary}</h4><AuthoringProposalOrigin proposal={proposal} /><p>{t.historyReadOnly}</p><small>{proposal.created_at} · {proposal.status === "adopted" ? t.decided : proposal.status === "rejected" ? t.reject : t.pending}</small><AuthoringEvidenceList evidence={proposal.evidence} /><AuthoringDesign workspace={{ items: patch.upsert_items, character_plans: patch.upsert_character_plans, scene_cards: patch.upsert_scene_cards, reader_records: patch.add_reader_records }} names={names} />{removed.length > 0 && <section><h5>{t.historyRemoved}</h5><ul>{removed.map(id => <li key={id}>{names[id] ?? id}</li>)}</ul></section>}{patch.remove_reader_records.length > 0 && <section><h5>{t.removed} · {t.reader}</h5>{patch.remove_reader_records.map((record, index) => <blockquote key={index}><p>{record.expected_text}</p><small>{record.draft_id} v{record.version} · {record.start}–{record.end}</small></blockquote>)}</section>}</article>;
}

export function AuthoringHistory({ apiBase, projectId, session, names = {} }: { apiBase: string; projectId: string; session: AuthoringSession; names?: Record<string, string> }) {
  const t = uiText.authoring;
  const [kind, setKind] = useState<AuthoringHistoryKind>("messages"), [query, setQuery] = useState(""), [searchedQuery, setSearchedQuery] = useState("");
  const [page, setPage] = useState<AuthoringHistoryPage | null>(null), [detail, setDetail] = useState<AuthoringProposal | null>(null), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const requestSequence = useRef(0), identity = `${apiBase}:${projectId}:${session.id}:${session.version}`, identityRef = useRef(identity); identityRef.current = identity;
  useEffect(() => { requestSequence.current += 1; setPage(null); setDetail(null); setError(""); setBusy(false); }, [identity]);
  async function search(selectedKind: AuthoringHistoryKind, selectedQuery: string, offset: number) {
    const sequence = ++requestSequence.current, scope = identity; setBusy(true); setError(""); setDetail(null);
    try { const value = await readAuthoringHistory(apiBase, projectId, session.id, selectedKind, selectedQuery, offset); if (sequence === requestSequence.current && scope === identityRef.current) { setPage(value); setKind(selectedKind); setSearchedQuery(selectedQuery); } }
    catch { if (sequence === requestSequence.current && scope === identityRef.current) { setPage(null); setError(t.historyFailed); } }
    finally { if (sequence === requestSequence.current && scope === identityRef.current) setBusy(false); }
  }
  async function open(id: string) {
    const sequence = ++requestSequence.current, scope = identity; setBusy(true); setError(""); setDetail(null);
    try { const value = await readAuthoringProposal(apiBase, projectId, session.id, id); if (sequence === requestSequence.current && scope === identityRef.current) setDetail(value); }
    catch { if (sequence === requestSequence.current && scope === identityRef.current) setError(t.historyFailed); }
    finally { if (sequence === requestSequence.current && scope === identityRef.current) setBusy(false); }
  }
  return <details className="authoring-card"><summary>{t.journal} · {t.historyMessages} {session.history_counts?.messages ?? session.messages.length} · {t.historyProposals} {session.history_counts?.proposals ?? session.proposals.length}</summary><p>{t.journalHelp}</p><p>{t.historyWindow}: {session.messages.length} / {session.history_counts?.messages ?? session.messages.length} · {t.historyProposals}: {session.proposals.length} / {session.history_counts?.proposals ?? session.proposals.length}</p>
    {session.history_has_more && <p>{session.history_has_more.messages || session.history_has_more.proposals ? t.historyMore : t.historyAll}</p>}
    <div className="authoring-toolbar"><label>{t.journal}<select value={kind} disabled={busy} onChange={event => { setKind(event.target.value as AuthoringHistoryKind); setPage(null); setDetail(null); }}><option value="messages">{t.historyMessages}</option><option value="proposals">{t.historyProposals}</option></select></label><label>{t.historyQuery}<input maxLength={500} value={query} disabled={busy} onChange={event => setQuery(event.target.value)} /></label><button type="button" disabled={busy} onClick={() => { void search(kind, query.trim(), 0); }}>{t.historySearch}</button></div>
    {error && <p role="alert">{error}</p>}{page && <><p>{t.historyNewest} · {t.historyCount}: {page.total_matches} · {page.returned_count ? page.offset + 1 : 0}–{page.offset + page.returned_count}</p>{!page.records.length && <p>{t.historyEmpty}</p>}{page.records.map(record => "role" in record ? <details key={record.id} className="authoring-message"><summary>{record.role === "author" ? t.author : record.role === "assistant" ? t.assistant : t.tools} · {record.created_at}</summary><p>{record.content}</p></details> : <article key={record.id} className="authoring-card"><p>{record.summary}</p><AuthoringProposalOrigin proposal={record} /><small>{record.created_at} · {record.status === "adopted" ? t.decided : record.status === "rejected" ? t.reject : t.pending}</small><button type="button" disabled={busy} onClick={() => { void open(record.id); }}>{t.historyDetails}</button></article>)}<div className="authoring-actions"><button type="button" disabled={busy || page.offset === 0} onClick={() => { void search(kind, searchedQuery, Math.max(0, page.offset - 40)); }}>{t.historyPrevious}</button><button type="button" disabled={busy || !page.more || page.next_offset === null} onClick={() => { if (page.next_offset !== null) void search(kind, searchedQuery, page.next_offset); }}>{t.historyNext}</button></div></>}
    {detail && <AuthoringHistoricalProposal proposal={detail} names={names} />}
  </details>;
}
