import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost, type ConnectionProfileUpdate, type AgentSettings } from "./api";
import { connectionText } from "./connectionText";
import { uiText } from "./localization";

export const CHATGPT_USAGE_URL = "https://chatgpt.com/settings/usage";
export type ChatGPTAccount = { account_id: string; label: string; email?: string | null; connected: boolean; plan_enabled: boolean; welcome_pending: boolean };
export type ChatGPTStatus = { supported: boolean; active_account_id: string | null; accounts: ChatGPTAccount[] };
export type ChatGPTAttempt = { attempt_id: string; status: "pending" | "completed" | "failed" | "cancelled" | "expired"; error?: string | null };
export function eligibleChatGPTAccount(status: ChatGPTStatus | null, id: string): boolean { return Boolean(status?.supported && status.accounts.some(a => a.account_id === id && a.connected && a.plan_enabled)); }
/** Account status can arrive before settings. Update only complete, existing profiles. */
export function withPlanReadiness(settings: AgentSettings | null, status: ChatGPTStatus): AgentSettings | null {
  if (!settings?.connection_profiles?.length) return settings;
  let changed = false;
  const profiles = settings.connection_profiles.map(profile => {
    if (profile.auth_mode !== "chatgpt_plan") return profile;
    const ready = eligibleChatGPTAccount(status, profile.chatgpt_account_id ?? "");
    if (ready === profile.account_ready) return profile;
    changed = true;
    return { ...profile, account_ready: ready };
  });
  return changed ? { ...settings, connection_profiles: profiles } : settings;
}
export function ChatGPTUsage({ active }: { active: boolean }) { return active ? <span className="chatgpt-usage">{uiText.chatgpt.using} · <a href={CHATGPT_USAGE_URL} target="_blank" rel="noreferrer">{uiText.chatgpt.usage}</a></span> : null; }

export function ChatGPTPlanSettings({ apiBase, busy, onAdd, onStatus, backendReady = true, backendReadGeneration = 0, active = true, canAdd = true, onSave }: { backendReady?: boolean; backendReadGeneration?: number; active?: boolean; canAdd?: boolean; onSave?: (profile: ConnectionProfileUpdate, useForMain: boolean) => Promise<void>; apiBase: string; busy: boolean; onAdd: (profile: ConnectionProfileUpdate) => void; onStatus: (status: ChatGPTStatus) => void }) {
  const t = uiText.chatgpt;
  const [status, setStatus] = useState<ChatGPTStatus | null>(null), [attempt, setAttempt] = useState<ChatGPTAttempt | null>(null);
  const [accountId, setAccountId] = useState(""), [models, setModels] = useState<Array<{ id: string; display_name?: string }>>([]), [model, setModel] = useState("");
  const [working, setWorking] = useState(false), [error, setError] = useState(false), [discovered, setDiscovered] = useState(false);
  const generation = useRef(0), selected = useRef(accountId); selected.current = accountId;
  const statusHandler = useRef(onStatus); statusHandler.current = onStatus;
  const locked = busy || working || !backendReady;
  const wasActive = useRef(false);
  const saveIdentity = useRef({ key: "", id: "" });
  function accept(next: ChatGPTStatus) { setStatus(next); statusHandler.current(next); setAccountId(current => next.accounts.some(a => a.account_id === current) ? current : next.active_account_id ?? next.accounts[0]?.account_id ?? ""); }
  async function refresh() { const seq = generation.current; const next = await apiGet<ChatGPTStatus>(apiBase, "/settings/chatgpt"); if (seq === generation.current) { accept(next); setError(false); } }
  useEffect(() => { generation.current++; setStatus(null); setAttempt(null); setModels([]); setModel(""); setAccountId(""); setWorking(false); setDiscovered(false); setError(false); return () => { generation.current++; }; }, [apiBase]);
  useEffect(() => {
    if (!backendReady) return;
    let alive = true; const seq = generation.current;
    apiGet<ChatGPTStatus>(apiBase, "/settings/chatgpt").then(next => { if (alive && seq === generation.current) { accept(next); setError(false); } }).catch(() => { if (alive && seq === generation.current) setError(true); });
    return () => { alive = false; };
  }, [apiBase, backendReady, backendReadGeneration]);
  useEffect(() => { const opening = active && !wasActive.current; wasActive.current = active; if (opening && backendReady && error) void refresh().then(() => setError(false)).catch(() => setError(true)); }, [active, backendReady]);
  async function save(useForMain: boolean) {
    if (locked || !canAdd || !model) return;
    const key = JSON.stringify([apiBase, accountId, model]);
    if (saveIdentity.current.key !== key) saveIdentity.current = { key, id: crypto.randomUUID() };
    const profile: ConnectionProfileUpdate = { id: saveIdentity.current.id, name: `${t.plan} · ${model}`, auth_mode: "chatgpt_plan", chatgpt_account_id: accountId, protocol: "responses", base_url: "", model, json_mode: true, thinking_mode: "provider_default", reasoning_effort: null };
    if (!onSave) { onAdd(profile); setModel(""); return; }
    setWorking(true); setError(false); const seq = generation.current;
    try { await onSave(profile, useForMain); } catch { if (seq === generation.current) setError(true); } finally { if (seq === generation.current) setWorking(false); }
  }

  useEffect(() => {
    if (attempt?.status !== "pending") return;
    let stopped = false; const seq = generation.current; let timer: ReturnType<typeof setTimeout>;
    const poll = async () => { try { const next = await apiGet<ChatGPTAttempt>(apiBase, `/settings/chatgpt/login/${encodeURIComponent(attempt.attempt_id)}`); if (stopped || seq !== generation.current) return; setAttempt(next); if (next.status === "pending") timer = setTimeout(poll, 1500); else { if (next.status === "failed" || next.status === "expired") setError(true); await refresh(); } } catch { if (!stopped && seq === generation.current) { setError(true); setAttempt(null); } } };
    timer = setTimeout(poll, 1500); return () => { stopped = true; clearTimeout(timer); };
  }, [apiBase, attempt?.attempt_id, attempt?.status]);
  async function action(kind: "login" | "cancel" | "logout" | "welcome") {
    if (locked) return; const seq = generation.current; setWorking(true); setError(false);
    try { const body = kind === "cancel" ? { attempt_id: attempt?.attempt_id } : { account_id: accountId || null };
      if (kind === "login" || kind === "cancel") { const next = await apiPost<ChatGPTAttempt>(apiBase, `/settings/chatgpt/${kind}`, body); if (seq !== generation.current) return; setAttempt(next); if (next.status === "failed" || next.status === "expired") setError(true); }
      else { const next = await apiPost<ChatGPTStatus>(apiBase, `/settings/chatgpt/${kind}`, body); if (seq !== generation.current) return; accept(next); }
      if (seq === generation.current) await refresh();
    } catch { if (seq === generation.current) setError(true); } finally { if (seq === generation.current) setWorking(false); }
  }
  async function discover() { if (!eligibleChatGPTAccount(status, accountId) || locked) return; const seq = generation.current, id = accountId; setWorking(true); setError(false); setModels([]); setModel(""); setDiscovered(false); try { const result = await apiGet<{ models: Array<{ id: string; display_name?: string }>; status: string }>(apiBase, `/settings/chatgpt/models?account_id=${encodeURIComponent(id)}`); if (seq !== generation.current || id !== selected.current) return; setModels(result.models); setDiscovered(true); if (result.status !== "ok") setError(true); } catch { if (seq === generation.current) setError(true); } finally { if (seq === generation.current) setWorking(false); } }
  const account = status?.accounts.find(a => a.account_id === accountId);
  return <section className="settings-block chatgpt-settings"><h3>{t.title}</h3><p>{t.help}</p><p>{t.notice}</p>
    {status && !status.supported && <p role="status">{t.unavailable}</p>}
    <label><span>{t.account}</span><select disabled={locked || attempt?.status === "pending"} value={accountId} onChange={e => { setAccountId(e.target.value); setModels([]); setModel(""); setDiscovered(false); }}><option value="">{status?.accounts.length ? t.another : t.none}</option>{status?.accounts.map(a => <option key={a.account_id} value={a.account_id}>{a.label || a.email || a.account_id}</option>)}</select></label>
    {account && <p>{account.connected ? t.connected : t.none} · {account.plan_enabled ? t.consent : t.noConsent}</p>}
    <div className="settings-actions compact"><button type="button" data-oai-siwc-button="" className="chatgpt-signin" disabled={locked || !status?.supported || attempt?.status === "pending"} onClick={() => { void action("login"); }}>Continue with ChatGPT</button>
    <button type="button" disabled={locked} onClick={() => { const seq = generation.current; setWorking(true); refresh().catch(() => { if (seq === generation.current) setError(true); }).finally(() => { if (seq === generation.current) setWorking(false); }); }}>{t.refresh}</button>
    {account?.connected && <button type="button" disabled={locked || attempt?.status === "pending"} onClick={() => { void action("logout"); }}>{t.disconnect}</button>}</div>
    {attempt?.status === "pending" && <p role="status">{t.pending} <button type="button" disabled={locked} onClick={() => { void action("cancel"); }}>{t.cancel}</button></p>}
    {account?.welcome_pending && account.connected && account.plan_enabled && <div className="chatgpt-welcome" role="dialog" aria-modal="false" aria-label={t.welcome}><h4>{t.welcome}</h4><p>{t.welcomeHelp}</p><button type="button" disabled={locked} onClick={() => { void action("welcome"); }}>{t.gotIt}</button></div>}
    <a href={CHATGPT_USAGE_URL} target="_blank" rel="noreferrer">{t.usage}</a>
    <button type="button" disabled={locked || !eligibleChatGPTAccount(status, accountId)} onClick={() => { void discover(); }}>{t.discover}</button>
    <label><span>{t.model}</span><select disabled={locked || !models.length} value={model} onChange={e => setModel(e.target.value)}><option value="">{t.choose}</option>{models.map(m => <option key={m.id} value={m.id}>{m.display_name || m.id}</option>)}</select></label>
    {discovered && !models.length && <p>{t.modelsEmpty}</p>}
    <div className="settings-actions"><button type="button" className="primary" disabled={locked || !canAdd || !model || !models.some(m => m.id === model) || !eligibleChatGPTAccount(status, accountId)} onClick={() => { void save(true); }}>{connectionText().saveUse}</button><button type="button" disabled={locked || !canAdd || !model || !eligibleChatGPTAccount(status, accountId)} onClick={() => { void save(false); }}>{connectionText().saveOnly}</button></div>

    {error && <p className="preset-error" role="alert">{t.error} <a href={CHATGPT_USAGE_URL} target="_blank" rel="noreferrer">{t.usage}</a></p>}
  </section>;
}
