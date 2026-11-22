import { useEffect, useRef, useState } from "react";
import { ArrowUpRight, ChevronLeft, ChevronRight, Pencil, RotateCcw, Search, Undo2 } from "lucide-react";
import { uiText } from "./localization";
import { editMemory, instructions, memories, saveInstructions, type AuthorMemory, type ConversationTarget, type Instructions } from "./projectContext";
import "./projectContext.css";

type Props = { apiBase: string; projectId: string; canEdit: boolean; onOpenSource: (target: ConversationTarget) => void };
type Draft = { text: string; version: number };
type MemoryDraft = {entry:AuthorMemory;text:string};
const pendingMemories = new Map<string,MemoryDraft>();
const pendingInstructions = new Map<string,Draft>();

export function ProjectNotebook(props: Props) {
  return <Notebook key={JSON.stringify([props.apiBase,props.projectId])} {...props}/>;
}

function Notebook({apiBase, projectId, canEdit, onOpenSource}: Props) {
  const t=uiText.authorDesk, scope=JSON.stringify([apiBase, projectId]);
  const [settings,setSettings]=useState<Instructions|null>(null);
  const [draft,setDraft]=useState<Draft|null>(()=>pendingInstructions.get(scope) ?? null);
  const [records,setRecords]=useState<Awaited<ReturnType<typeof memories>>|null>(null);
  const [query,setQuery]=useState(""), [withdrawn,setWithdrawn]=useState(false);
  const [offset,setOffset]=useState(0), [generation,reload]=useState(0);
  const [notice,setNotice]=useState(""), [failure,setFailure]=useState(false);
  const [busy,setBusy]=useState(false);
  const [editor,updateEditor]=useState<MemoryDraft|null>(()=>pendingMemories.get(scope) ?? null);
  function setEditor(next:MemoryDraft|null) {
    if (next) pendingMemories.set(scope,next); else pendingMemories.delete(scope);
    updateEditor(next);
  }
  const alive=useRef(true);
  useEffect(()=>{ alive.current=true; return ()=>{ alive.current=false; }; },[]);
  useEffect(()=>{
    let current=true;
    if (projectId) instructions(apiBase,projectId).then(value=>{ if(current)setSettings(value); })
      .catch(()=>{ if(current)setFailure(true); });
    return ()=>{ current=false; };
  },[apiBase,projectId,generation]);
  useEffect(()=>{
    let current=true;
    const timer=setTimeout(()=>{ if(projectId) memories(apiBase,projectId,query.trim(),withdrawn,offset)
      .then(value=>{if(current)setRecords(value);}).catch(()=>{if(current)setFailure(true);}); },query?180:0);
    return ()=>{current=false;clearTimeout(timer);};
  },[apiBase,projectId,query,withdrawn,offset,generation]);
  useEffect(()=>{
    if (!draft && !editor) return;
    const warn=(e:BeforeUnloadEvent)=>{e.preventDefault();e.returnValue="";};
    window.addEventListener("beforeunload",warn);
    return ()=>window.removeEventListener("beforeunload",warn);
  },[draft,editor]);
  useEffect(()=>{
    const changed=(e:Event)=>{
      const payload=(e as CustomEvent).detail;
      if(payload?.apiBase===apiBase && payload.projectId===projectId)reload(n=>n+1);
    };
    window.addEventListener("storygraph-notebook-changed",changed);
    return ()=>window.removeEventListener("storygraph-notebook-changed",changed);
  },[apiBase,projectId]);
  function change(text:string) {
    if (!settings) return;
    const value={text,version:draft?.version ?? settings.version};
    pendingInstructions.set(scope,value);setDraft(value);setNotice("");
  }
  function refresh(){setFailure(false);reload(n=>n+1);}
  async function save() {
    if (!draft || busy) return;
    setBusy(true);
    try {
      const saved=await saveInstructions(apiBase,projectId,draft.text,draft.version);
      pendingInstructions.delete(scope);
      if(alive.current){setSettings(saved);setDraft(null);setNotice(t.saved);setFailure(false);}
    } catch {if(alive.current){setNotice(t.saveError);refresh();}}
    finally {if(alive.current)setBusy(false);}
  }
  async function mutate(entry:AuthorMemory,text:string,status:AuthorMemory["status"]) {
    if(busy)return;
    setBusy(true);
    try {
      await editMemory(apiBase,projectId,entry,text,status);
      if(alive.current){setEditor(null);setNotice(t.saved);refresh();}
    } catch {if(alive.current){setNotice(t.saveError);refresh();}}
    finally {if(alive.current)setBusy(false);}
  }
  if(!projectId)return null;
  return <section className="project-notebook" aria-label={t.notebook}>
    <h2>{t.notebook}</h2>
    <section className="project-guidelines"><label><h3>{t.guidelines}</h3>
      <textarea value={draft?.text ?? settings?.instructions ?? ""} maxLength={16000} rows={3}
        placeholder={t.guidancePlaceholder} disabled={!canEdit || busy || !settings} onChange={e=>change(e.target.value)}/>
    </label>{draft && <div className="notebook-actions">
      <button type="button" className="primary" disabled={busy || !settings || draft.version!==settings.version} onClick={()=>{void save();}}>{t.save}</button>
      <button type="button" disabled={busy} onClick={()=>{pendingInstructions.delete(scope);setDraft(null);setNotice("");}}>{t.cancel}</button>
      {settings && draft.version!==settings.version && <span role="alert">{t.saveError}</span>}
    </div>}</section>
    <div className="memory-heading"><h3>{t.remembered}</h3><label><input type="checkbox" checked={withdrawn} onChange={e=>{setWithdrawn(e.target.checked);setOffset(0);}}/>{t.showWithdrawn}</label></div>
    <label className="desk-search"><Search size={15}/><input type="search" value={query} aria-label={t.searchMemory} placeholder={t.searchMemory} onChange={e=>{setQuery(e.target.value);setOffset(0);}}/></label>
    {failure && <p role="alert">{t.loadError} <button onClick={refresh}>{t.retry}</button></p>}
    {notice && <small role="status">{notice}</small>}
    {records && !records.records.length && <p className="notebook-empty">{t.noneRemembered}</p>}
    {records?.records.map(entry=><article key={entry.id} className="project-memory" data-state={entry.status}>
      <small>{entry.status==="withdrawn"?t.withdrawn:entry.status==="tentative"?t.tentative:t[entry.kind]}</small>
      {editor?.entry.id===entry.id ? <form onSubmit={e=>{e.preventDefault();void mutate(editor.entry,editor.text.trim(),editor.entry.status);}}>
        <textarea aria-label={t.edit} rows={3} maxLength={2000} value={editor.text} onChange={e=>setEditor({...editor,text:e.target.value})}/>
        <button type="submit" disabled={busy || !editor.text.trim()}>{t.save}</button>
        <button type="button" disabled={busy} onClick={()=>setEditor(null)}>{t.cancel}</button>
      </form> : <p>{entry.text}</p>}
      <div className="notebook-actions">
        <button type="button" onClick={()=>onOpenSource({sessionId:entry.source_session_id,messageId:entry.source_message_id})}><ArrowUpRight size={13}/>{t.source}</button>
        {canEdit && entry.status!=="withdrawn" && <>
          <button type="button" disabled={busy} onClick={()=>setEditor({entry,text:entry.text})}><Pencil size={13}/>{t.edit}</button>
          <button type="button" disabled={busy} onClick={()=>{void mutate(entry,entry.text,"withdrawn");}}><Undo2 size={13}/>{t.withdraw}</button>
        </>}
        {canEdit && entry.status==="withdrawn" && <button type="button" disabled={busy} onClick={()=>{void mutate(entry,entry.text,entry.kind==="tentative"?"tentative":"active");}}><RotateCcw size={13}/>{t.restore}</button>}
      </div>
    </article>)}
    {(offset>0 || records?.more) && <nav className="desk-paging"><button disabled={!offset} aria-label={t.previous} onClick={()=>setOffset(Math.max(0,offset-25))}><ChevronLeft size={16}/></button>
      <button disabled={!records?.more} aria-label={t.next} onClick={()=>setOffset(offset+25)}><ChevronRight size={16}/></button></nav>}
  </section>;
}
