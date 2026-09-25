import { useEffect, useRef, useState } from "react";
import { KeyRound, Plus, RefreshCw, Trash2, Wand2 } from "lucide-react";
import { apiGet, type AgentModels, type AgentSettings, type AgentSettingsUpdate, type ConnectionProfileUpdate, type ModelExecution, type ModelProtocol } from "./api";
import { uiText } from "./localization";
import { MODEL_TASKS, removeConnection, resolvedTask } from "./modelRouting";

export function modelExecutionLabel(execution: ModelExecution | null | undefined): string {
  if (!execution) return uiText.modelRouting.missingAssignment;
  return `${uiText.modelRouting.roles[execution.task]} · ${execution.profile_name || uiText.modelRouting.inherited} · ${execution.model || uiText.common.notConfigured} · ${uiText.modelRouting.protocols[execution.protocol] ?? execution.protocol}`;
}

function ConnectionFields({ apiBase, profile, saved, busy, onChange, defaultConnection = false }: {
  apiBase: string; profile: ConnectionProfileUpdate; saved: (ConnectionProfileUpdate & { api_key_configured: boolean; api_key_preview?: string | null }) | null;
  busy: boolean; onChange: (patch: Partial<ConnectionProfileUpdate>) => void; defaultConnection?: boolean;
}) {
  const [models, setModels] = useState<AgentModels | null>(null);
  const [loading, setLoading] = useState(false);
  const sequence = useRef(0);
  const scope = JSON.stringify([apiBase, profile.id, saved?.protocol, saved?.base_url, saved?.model, saved?.json_mode, saved?.api_key_configured, saved?.api_key_preview]);
  const activeScope = useRef(scope); activeScope.current = scope;
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; sequence.current += 1; }; }, []);
  useEffect(() => { sequence.current += 1; setModels(null); setLoading(false); }, [scope]);
  const dirty = !saved || Boolean(profile.api_key) || Boolean(profile.clear_api_key) || ["name", "protocol", "base_url", "model", "json_mode"].some((key) => profile[key as keyof ConnectionProfileUpdate] !== saved[key as keyof ConnectionProfileUpdate]);
  const locked = busy || loading;
  const listId = `connection-models-${profile.id}`;
  async function discover() {
    if (dirty || !saved?.api_key_configured || locked) return;
    const request = { scope, sequence: ++sequence.current };
    const current = () => alive.current && request.scope === activeScope.current && request.sequence === sequence.current;
    setLoading(true); setModels(null);
    try {
      const result = await apiGet<AgentModels>(apiBase, `/settings/agent/models${defaultConnection ? "" : `?profile_id=${encodeURIComponent(profile.id)}`}`);
      if (current()) setModels(result);
    } catch { if (current()) setModels({ models: [], current_model: profile.model, current_model_available: null, status: "unavailable", error: null }); }
    finally { if (current()) setLoading(false); }
  }
  return <div className="model-connection-fields">
    <label><span>{uiText.modelRouting.connectionName}</span><input disabled={locked} maxLength={80} value={profile.name} onChange={(event) => onChange({ name: event.target.value })} /></label>
    <label><span>{uiText.modelRouting.protocol}</span><select disabled={locked} value={profile.protocol} onChange={(event) => onChange({ protocol: event.target.value as ModelProtocol })}>{Object.entries(uiText.modelRouting.protocols).map(([protocol, label]) => <option value={protocol} key={protocol}>{label}</option>)}</select></label>
    <small>{uiText.modelRouting.protocolHelp}</small>
    <label><span>{uiText.settings.baseUrl}</span><input disabled={locked} placeholder="https://provider.example/v1" autoComplete="off" value={profile.base_url} onChange={(event) => onChange({ base_url: event.target.value })} /></label>
    <label><span>{uiText.settings.model}</span><input disabled={locked} list={listId} autoComplete="off" value={profile.model} onChange={(event) => onChange({ model: event.target.value })} /></label>
    <datalist id={listId}>{models?.models.map((model) => <option key={model.id} value={model.id} />)}</datalist>
    <button type="button" disabled={locked || dirty || !saved?.api_key_configured} onClick={() => { void discover(); }}><RefreshCw size={14} />{loading ? uiText.common.loading : uiText.navigation.modelDiscovery}</button>
    <small>{dirty ? uiText.modelRouting.saveFirst : uiText.modelRouting.discoveryHelp}</small>
    {models?.status === "unavailable" && <p className="preset-error">{uiText.modelRouting.discoveryUnavailable}</p>}
    {models?.current_model_available === false && <p className="preset-error">{uiText.navigation.currentModelUnavailable}</p>}
    {models?.model_execution && <small>{modelExecutionLabel(models.model_execution)}</small>}
    <label className="checkbox-row"><input type="checkbox" disabled={locked} checked={profile.json_mode} onChange={(event) => onChange({ json_mode: event.target.checked })} /><span>{uiText.modelRouting.jsonPreference}</span></label>
    <small>{uiText.modelRouting.jsonHelp}</small>
    <div className="connection-key-status"><KeyRound size={13} /><span>{saved?.api_key_configured ? uiText.modelRouting.keyConfigured : uiText.modelRouting.keyMissing}</span>{saved?.api_key_preview && <code>{saved.api_key_preview}</code>}</div>
    <label><span>{uiText.settings.replaceKey}</span><input disabled={locked || Boolean(profile.clear_api_key)} type="password" autoComplete="off" value={profile.api_key ?? ""} placeholder={uiText.settings.keyPlaceholder} onChange={(event) => onChange({ api_key: event.target.value })} /></label>
    <small>{uiText.modelRouting.keyKeep}</small>
    <label className="checkbox-row"><input type="checkbox" disabled={locked} checked={Boolean(profile.clear_api_key)} onChange={(event) => onChange({ clear_api_key: event.target.checked, ...(event.target.checked ? { api_key: "" } : {}) })} /><span>{uiText.modelRouting.keyClear}</span></label>
  </div>;
}

export function ModelRoutingSettings({ apiBase, settings, form, onFormChange, apiKeyInput, onApiKeyChange, clearApiKey, onClearApiKeyChange, busy }: {
  apiBase: string; settings: AgentSettings | null; form: AgentSettingsUpdate; onFormChange: React.Dispatch<React.SetStateAction<AgentSettingsUpdate>>;
  apiKeyInput: string; onApiKeyChange: (key: string) => void; clearApiKey: boolean; onClearApiKeyChange: (clear: boolean) => void; busy: boolean;
}) {
  const profiles = form.connection_profiles ?? [];
  const defaultProfile: ConnectionProfileUpdate = { id: "default", name: form.provider_label, protocol: form.llm_protocol ?? "chat_completions", base_url: form.llm_base_url, model: form.llm_model, json_mode: form.llm_json_mode, api_key: apiKeyInput, clear_api_key: clearApiKey };
  const savedDefault = settings ? { id: "default", name: settings.provider_label, protocol: settings.llm_protocol ?? "chat_completions", base_url: settings.llm_base_url, model: settings.llm_model, json_mode: settings.llm_json_mode, api_key_configured: settings.api_key_configured, api_key_preview: settings.api_key_preview } : null;
  return <>
    <section className="settings-block">
      <div className="settings-title"><Wand2 size={15} />{uiText.modelRouting.defaultConnection}</div><small>{uiText.modelRouting.defaultHelp}</small>
      <label><span>{uiText.settings.writerMode}</span><select disabled={busy} value={form.scene_writer} onChange={(event) => onFormChange((current) => ({ ...current, scene_writer: event.target.value as AgentSettingsUpdate["scene_writer"] }))}><option value="rule_based">{uiText.settings.ruleBasedMode}</option><option value="llm">{uiText.settings.llmMode}</option></select></label>
      <ConnectionFields apiBase={apiBase} profile={defaultProfile} saved={savedDefault} busy={busy} defaultConnection onChange={(patch) => {
        onFormChange((current) => ({ ...current, ...(patch.name !== undefined ? { provider_label: patch.name } : {}), ...(patch.protocol !== undefined ? { llm_protocol: patch.protocol } : {}), ...(patch.base_url !== undefined ? { llm_base_url: patch.base_url } : {}), ...(patch.model !== undefined ? { llm_model: patch.model } : {}), ...(patch.json_mode !== undefined ? { llm_json_mode: patch.json_mode } : {}) }));
        if (patch.api_key !== undefined) onApiKeyChange(patch.api_key ?? "");
        if (patch.clear_api_key !== undefined) onClearApiKeyChange(patch.clear_api_key);
      }} />
    </section>
    <details className="settings-block settings-disclosure model-connections"><summary>{uiText.modelRouting.connections} · {profiles.length}</summary><small>{uiText.modelRouting.connectionsHelp}</small>
      {profiles.map((profile) => <details key={profile.id} className="connection-profile"><summary>{profile.name || uiText.modelRouting.newConnection}<small>{profile.model || uiText.common.notConfigured}</small></summary>
        <ConnectionFields apiBase={apiBase} profile={profile} saved={settings?.connection_profiles?.find((item) => item.id === profile.id) ?? null} busy={busy} onChange={(patch) => onFormChange((current) => ({ ...current, connection_profiles: current.connection_profiles?.map((item) => item.id === profile.id ? { ...item, ...patch } : item) }))} />
        <button type="button" disabled={busy} onClick={() => onFormChange((current) => removeConnection(current, profile.id))}><Trash2 size={14} />{uiText.modelRouting.removeConnection}</button><small>{uiText.modelRouting.removeHelp}</small>
      </details>)}
      <button type="button" disabled={busy || profiles.length >= 20} onClick={() => onFormChange((current) => ({ ...current, connection_profiles: [...(current.connection_profiles ?? []), { id: crypto.randomUUID(), name: uiText.modelRouting.newConnection, protocol: "chat_completions", base_url: "", model: "", json_mode: true }] }))}><Plus size={14} />{uiText.modelRouting.addConnection}</button>
    </details>
    <details className="settings-block settings-disclosure task-model-settings"><summary>{uiText.modelRouting.taskSection}</summary><small>{uiText.modelRouting.taskHelp}</small>
      {MODEL_TASKS.map((task) => <label key={task}><span>{uiText.modelRouting.roles[task]}</span><select disabled={busy} value={form.task_assignments?.[task] ?? ""} onChange={(event) => onFormChange((current) => ({ ...current, task_assignments: { ...current.task_assignments, [task]: event.target.value || null } }))}><option value="">{uiText.modelRouting.defaultOption}</option>{profiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.name || profile.id} · {profile.model || uiText.common.notConfigured}</option>)}</select><small>{modelExecutionLabel(resolvedTask(settings, task))}</small></label>)}
      <p className="model-qa-note">{uiText.modelRouting.qaRuleBased}</p>
    </details>
  </>;
}
