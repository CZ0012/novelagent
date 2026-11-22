import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, MessageSquare, Pencil, Plus, Search } from "lucide-react";
import { conversations, findConversationMessages, renameConversation, type ConversationTarget } from "./projectContext";
import { uiText } from "./localization";
import "./projectContext.css";

type Props = {
  apiBase: string; projectId: string; activeSessionId?: string | null; sessionVersion?: number;
  onOpen: (target: ConversationTarget) => void; onNew: () => void; canEdit?: boolean;
};
type Sessions = Awaited<ReturnType<typeof conversations>>;
type Hits = Awaited<ReturnType<typeof findConversationMessages>>;

export function ProjectConversations(props: Props) {
  return <ConversationList key={JSON.stringify([props.apiBase, props.projectId])} {...props}/>;
}

function ConversationList({ apiBase, projectId, activeSessionId, sessionVersion, onOpen, onNew, canEdit = true }: Props) {
  const t = uiText.authorDesk;
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const [revision, refresh] = useState(0);
  const [sessions, setSessions] = useState<Sessions | null>(null);
  const [hits, setHits] = useState<Hits | null>(null);
  const [error, setError] = useState(false);
  const [editing, setEditing] = useState<{ row: Sessions["sessions"][number]; title: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [renameError, setRenameError] = useState(false);
  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const start = Date.now();
    async function load() {
      try {
        const [rows, messages] = await Promise.all([
          conversations(apiBase, projectId, query.trim(), page),
          query.trim() ? findConversationMessages(apiBase, projectId, query.trim(), page) : null,
        ]);
        if (cancelled) return;
        setSessions(rows); setHits(messages); setError(false);
        if (Date.now() - start < 60000 && rows.sessions.some(s => ["pending","started"].includes(s.title_metadata?.state ?? ""))) {
          timer = setTimeout(load, 1800);
        }
      } catch { if (!cancelled) setError(true); }
    }
    if (projectId) timer = setTimeout(load, query ? 180 : 0);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [apiBase, projectId, query, page, revision, activeSessionId, sessionVersion]);
  async function saveTitle() {
    if (!editing || saving || !editing.title.trim()) return;
    setSaving(true); setRenameError(false);
    try {
      const changed = await renameConversation(apiBase, projectId, editing.row, editing.title.trim());
      setEditing(null); refresh(v => v+1);
      window.dispatchEvent(new CustomEvent("storygraph-conversation-title", {detail:{
        apiBase, projectId, sessionId:editing.row.id, title:changed.title_metadata.title,
      }}));
    } catch {
      setRenameError(true); refresh(v => v+1);
    } finally { setSaving(false); }
  }
  if (!projectId) return null;
  return <section className="desk-conversations" aria-label={t.chats}>
    <div className="desk-chat-tools">
      <label className="desk-search"><Search size={15}/><input type="search" value={query} placeholder={t.search} aria-label={t.search} onChange={e=>{ setQuery(e.target.value); setPage(0); }}/></label>
      <button type="button" onClick={onNew} disabled={!canEdit} title={t.newChat} aria-label={t.newChat}><Plus size={17}/>{t.newChat}</button>
    </div>
    {error && <p role="alert">{t.loadError} <button type="button" onClick={()=>refresh(v=>v+1)}>{t.retry}</button></p>}
    {renameError && <div role="alert">{t.saveError} <button type="button" onClick={()=>{
      const row=sessions?.sessions.find(item=>item.id===editing?.row.id);
      if (row && editing) { setEditing({...editing,row:row}); setRenameError(false); }
    }}>{t.retry}</button></div>}
    <ul className="desk-chat-list">{sessions?.sessions.map(row=><li key={row.id} data-current={row.id===activeSessionId}>
      {editing?.row.id===row.id ? <form onSubmit={e=>{e.preventDefault();void saveTitle();}}>
        <input aria-label={t.rename} autoFocus maxLength={500} value={editing.title} onChange={e=>setEditing({...editing,title:e.target.value})}/>
        <button type="submit" disabled={saving || !editing.title.trim()}>{t.save}</button>
        <button type="button" disabled={saving} onClick={()=>setEditing(null)}>{t.cancel}</button>
      </form> : <>
        <button type="button" className="desk-chat-link" aria-current={row.id===activeSessionId?"page":undefined} onClick={()=>onOpen({sessionId:row.id})}>
          <MessageSquare size={15}/><span>{row.title}</span>
        </button>
        {canEdit && <button className="desk-rename" type="button" title={t.rename} aria-label={t.rename+" · "+row.title} onClick={()=>{setRenameError(false);setEditing({row,title:row.title});}}><Pencil size={13}/></button>}
      </>}
    </li>)}</ul>
    {hits && hits.records.length>0 && <><h4>{t.messages}</h4><ul className="desk-chat-list search-hits">{hits.records.map(hit=><li key={hit.message_id}><button type="button" onClick={()=>onOpen({sessionId:hit.session_id,messageId:hit.message_id})}><span>{hit.content}</span></button></li>)}</ul></>}
    {sessions && !sessions.sessions.length && !hits?.records.length && !error && <p>{query?t.noMatches:t.noChats}</p>}
    {(page>0 || sessions?.more || hits?.more) && <nav className="desk-paging">
      <button type="button" disabled={!page} aria-label={t.previous} onClick={()=>setPage(Math.max(0,page-25))}><ChevronLeft size={16}/></button>
      <button type="button" disabled={!sessions?.more && !hits?.more} aria-label={t.next} onClick={()=>setPage(page+25)}><ChevronRight size={16}/></button>
    </nav>}
  </section>;
}
