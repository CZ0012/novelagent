import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost, apiPut, type AgentSettings, type ConnectionProfileUpdate, type ModelProtocol } from "./api";
import { taskConnectionReady } from "./modelRouting";
import { connectionText } from "./connectionText";
import { ChatGPTPlanSettings, type ChatGPTStatus } from "./ChatGPTPlanSettings";
import { uiText } from "./localization";
import "./ModelConnectionSetup.css";
export type ConnectionCommit = { settings: AgentSettings; profile_id: string };
export function ModelConnectionSetup({ apiBase, settings, backendReady, backendReadGeneration, active, busy, onStatus, onCommitted, onGoToChat }: { apiBase: string; settings: AgentSettings | null; backendReady: boolean; backendReadGeneration: number; active: boolean; busy: boolean; onStatus: (status: ChatGPTStatus) => void; onCommitted: (result: ConnectionCommit) => void; onGoToChat?: () => void }) {
  const t = connectionText();
  const [method, setMethod] = useState("chatgpt_plan"), [working, setWorking] = useState(false), [error, setError] = useState(false), [saved, setSaved] = useState(false);
  const [profile, setProfile] = useState<ConnectionProfileUpdate>(() => ({ id: crypto.randomUUID(), name: "", auth_mode: "api_key", protocol: "chat_completions", base_url: "", model: "", json_mode: true }));
  const [apiConfigured, setApiConfigured] = useState(false);
  const [title, setTitle] = useState<{ enabled: boolean; model: string | null } | null>(null), [titleError, setTitleError] = useState(false);
  const mounted = useRef(true);
  const confirmation = useRef<HTMLDivElement>(null);
  const preferenceEdited = useRef(false);
  useEffect(() => {
    if (saved && active) {
      confirmation.current?.focus({preventScroll: true});
      confirmation.current?.scrollIntoView({block:"nearest"});
    }
  }, [saved, active]);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const wasActive = useRef(false);
  const gate = useRef(false), scope = useRef(apiBase); scope.current = apiBase;
  const locked = busy || working || !backendReady || !settings;
  const patch = (value: Partial<ConnectionProfileUpdate>) => {
    setSaved(false);
    if (apiConfigured) {
      setApiConfigured(false);
      setProfile(current => ({ ...current, id: crypto.randomUUID(), ...value }));
    } else setProfile(current => ({ ...current, ...value }));
  };
  async function loadTitle() { const base = apiBase; try { const value = await apiGet<{ enabled: boolean; model: string | null }>(base, "/settings/agent/title-preferences"); if (mounted.current && base === scope.current && !preferenceEdited.current) { setTitle(value); setTitleError(false); } } catch { if (mounted.current && base === scope.current) setTitleError(true); } }
  useEffect(() => { if (backendReady) void loadTitle(); }, [apiBase, backendReady, backendReadGeneration]);
  useEffect(() => { const opening = active && !wasActive.current; wasActive.current = active; if (opening && backendReady && titleError) void loadTitle(); }, [active, backendReady]);
  async function commit(candidate: ConnectionProfileUpdate, useForMain: boolean) {
    if (gate.current || locked) return;
    gate.current = true; setWorking(true); setError(false); setSaved(false); const base = apiBase;
    try { const result = await apiPost<ConnectionCommit>(base, "/settings/agent/connections", { profile: { ...candidate, api_key: candidate.api_key || undefined, name: candidate.name.trim() || candidate.model }, use_for_main_agent: useForMain }); if (!mounted.current || scope.current !== base) return; onCommitted(result); setSaved(true); if (candidate.auth_mode !== "chatgpt_plan") { setApiConfigured(true); setProfile(current => ({ ...current, id: result.profile_id, api_key: "" })); } }
    catch { if (mounted.current && scope.current === base) setError(true); }
    finally { gate.current = false; if (mounted.current && scope.current === base) setWorking(false); }
  }
  const actual = taskConnectionReady(settings,"discussion") ? settings?.resolved_tasks?.discussion?.model : null;
  return <section className="model-setup settings-block"><header><h2>{t.title}</h2><p>{t.help}</p></header>
    <div className="model-methods" role="group" aria-label={t.method}>{([['chatgpt_plan',t.plan],['api_key',t.api]] as const).map(([id,label]) => <button type="button" aria-pressed={method === id} disabled={working} key={id} onClick={() => setMethod(id)}>{label}</button>)}</div>
    {method === "chatgpt_plan" ? <ChatGPTPlanSettings apiBase={apiBase} backendReady={backendReady} backendReadGeneration={backendReadGeneration} active={active} busy={busy || working} canAdd={Boolean(settings)} onStatus={onStatus} onAdd={() => undefined} onSave={commit} /> : <div className="model-api-setup"><label><span>{t.name}</span><input disabled={locked} value={profile.name} onChange={e => patch({ name: e.target.value })} /></label><label><span>{uiText.modelRouting.protocol}</span><select disabled={locked} value={profile.protocol} onChange={e => patch({ protocol: e.target.value as ModelProtocol })}>{Object.entries(uiText.modelRouting.protocols).map(([key,label]) => <option key={key} value={key}>{label}</option>)}</select></label><label><span>{uiText.settings.baseUrl}</span><input disabled={locked} value={profile.base_url} placeholder="https://provider.example/v1" onChange={e => patch({ base_url: e.target.value })} /></label><label><span>{uiText.settings.model}</span><input disabled={locked} value={profile.model} onChange={e => patch({ model: e.target.value })} /></label><label><span>API Key</span><input type="password" autoComplete="off" disabled={locked} value={profile.api_key ?? ""} onChange={e => patch({ api_key: e.target.value })} /></label><div className="settings-actions"><button className="primary" type="button" disabled={locked || !profile.model.trim() || !profile.base_url.trim() || (!profile.api_key && !apiConfigured)} onClick={() => void commit(profile,true)}>{t.saveUse}</button><button type="button" disabled={locked || !profile.model.trim() || !profile.base_url.trim() || (!profile.api_key && !apiConfigured)} onClick={() => void commit(profile,false)}>{t.saveOnly}</button></div></div>}
    {working && <p role="status">{t.saving}</p>}{error && <p role="alert">{t.error}</p>}<div ref={confirmation} tabIndex={-1} className="connection-receipt">
      {saved && <p role="status">{t.saved}</p>}
      {actual && <div className="model-confirmation"><span>{t.actual}</span><strong>{actual}</strong><button type="button" onClick={onGoToChat}>{t.chat}</button></div>}
    </div>
    <details><summary>{t.titleAuto}</summary>{title ? <><label className="checkbox-row"><input type="checkbox" checked={title.enabled} disabled={locked} onChange={e => {preferenceEdited.current=true; setTitle({ ...title, enabled: e.target.checked });}} />{t.titleAuto}</label><label><span>{t.titleModel}</span><input disabled={locked} value={title.model ?? ""} onChange={e => {preferenceEdited.current=true; setTitle({ ...title, model: e.target.value || null });}} /></label><button type="button" disabled={locked} onClick={async () => { setWorking(true); try { await apiPut(apiBase,"/settings/agent/title-preferences",title); preferenceEdited.current=false; setTitleError(false); } catch { setTitleError(true); } finally { setWorking(false); } }}>{t.titleSave}</button></> : null}{titleError && <p role="alert">{t.error} <button type="button" disabled={!backendReady || working} onClick={() => void loadTitle()}>{t.retry}</button></p>}</details>
  </section>;
}
