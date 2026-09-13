import { useEffect, useState } from "react";
import { Check, Copy, Plus, Save, Trash2, Wand2, X } from "lucide-react";
import { apiDelete, apiPost, apiPut, type AgentPreset, type AgentPresetInput, type AgentSettings } from "./api";
import { uiText } from "./localization";

const emptyPreset: AgentPresetInput = { name: "", description: "", system_prompt: "" };

export function presetDisplay(preset: AgentPreset): { name: string; description: string } {
  if (preset.builtin && ["builtin_zh_concise", "builtin_balanced", "builtin_en_precise"].includes(preset.id)) {
    return uiText.presets[preset.id as "builtin_zh_concise" | "builtin_balanced" | "builtin_en_precise"];
  }
  return preset;
}

export function AgentPresets({ apiBase, settings, busy, onChange, onManage, compact = false }: {
  apiBase: string;
  settings: AgentSettings | null;
  busy: boolean;
  onChange: (settings: AgentSettings) => void;
  compact?: boolean;
  onManage?: () => void;
}) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<AgentPresetInput>(emptyPreset);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(false);
  const [notice, setNotice] = useState<"saved" | "selected" | "deleted" | null>(null);
  const presets = settings?.agent_presets ?? [];
  const selected = presets.find((preset) => preset.id === settings?.selected_preset_id);
  const locked = saving || busy || !settings || settings.permission_level === "read_only";
  useEffect(() => { setEditingId(null); setError(false); setNotice(null); }, [apiBase]);
  useEffect(() => {
    if (editingId === null) return;
    const preventUnload = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", preventUnload);
    return () => window.removeEventListener("beforeunload", preventUnload);
  }, [editingId]);
  async function mutate(action: () => Promise<AgentSettings>, success: "saved" | "selected" | "deleted") {
    if (locked) return;
    setSaving(true); setError(false); setNotice(null);
    try { onChange(await action()); setNotice(success); if (success !== "selected") setEditingId(null); }
    catch { setError(true); }
    finally { setSaving(false); }
  }
  function edit(preset?: AgentPreset) {
    setNotice(null);
    setEditingId(preset && !preset.builtin ? preset.id : "new");
    setForm(preset ? { name: presetDisplay(preset).name, description: presetDisplay(preset).description, system_prompt: preset.system_prompt } : { ...emptyPreset });
  }
  return <section className={`preset-panel ${compact ? "compact" : ""}`} aria-label={uiText.presets.title}>
    <label><span><Wand2 size={14} /> {uiText.presets.select}</span>
      <select value={settings?.selected_preset_id ?? ""} disabled={locked || editingId !== null}
        onChange={(event) => { const id = event.target.value; void mutate(() => apiPut(apiBase, "/settings/agent", { selected_preset_id: id }), "selected"); }}>
        {!selected && <option value="">{uiText.common.loading}</option>}
        {presets.map((preset) => <option value={preset.id} key={preset.id}>{presetDisplay(preset).name} · {preset.builtin ? uiText.presets.builtin : uiText.presets.custom}</option>)}
      </select>
    </label>
    {selected && <p>{presetDisplay(selected).description}</p>}
    {!compact && <small>{uiText.presets.help}</small>}
    {selected && <details className="preset-prompt"><summary>{uiText.presets.preview}</summary><pre>{selected.system_prompt}</pre></details>}
    {compact ? <button type="button" onClick={onManage}>{uiText.presets.manage}</button> : <details className="preset-management" open={editingId !== null || undefined}>
      <summary>{uiText.presets.manage}</summary>
      <div className="preset-actions">
        <button type="button" disabled={locked || editingId !== null} onClick={() => edit()}><Plus size={14} /> {uiText.presets.create}</button>
        {selected && <button type="button" disabled={locked || editingId !== null} onClick={() => edit(selected)}><Copy size={14} /> {selected.builtin ? uiText.presets.duplicate : uiText.presets.edit}</button>}
        {selected && !selected.builtin && <button type="button" disabled={locked || editingId !== null} onClick={() => {
          if (window.confirm(uiText.presets.deleteConfirm(selected.name))) void mutate(() => apiDelete(apiBase, `/settings/agent/presets/${encodeURIComponent(selected.id)}`), "deleted");
        }}><Trash2 size={14} /> {uiText.presets.delete}</button>}
      </div>
      {editingId !== null && <form className="preset-editor" onSubmit={(event) => {
        event.preventDefault();
        void mutate(() => editingId === "new" ? apiPost(apiBase, "/settings/agent/presets", form) : apiPut(apiBase, `/settings/agent/presets/${encodeURIComponent(editingId)}`, form), "saved");
      }}>
        <label><span>{uiText.presets.name}</span><input required maxLength={80} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} disabled={locked} /></label>
        <label><span>{uiText.presets.description}</span><input maxLength={500} value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} disabled={locked} /></label>
        <label><span>{uiText.presets.systemPrompt}</span><textarea required maxLength={12000} rows={7} value={form.system_prompt} onChange={(event) => setForm({ ...form, system_prompt: event.target.value })} disabled={locked} /></label>
        <small>{uiText.presets.bounds}</small>
        <div className="preset-actions"><button type="submit" className="primary" disabled={locked || !form.name.trim() || !form.system_prompt.trim()}><Save size={14} /> {uiText.common.save}</button><button type="button" disabled={saving} onClick={() => setEditingId(null)}><X size={14} /> {uiText.common.cancel}</button></div>
      </form>}
    </details>}
    {error && <p role="alert" className="preset-error">{uiText.errors.requestFailed}</p>}
    {notice && <p role="status"><Check size={14} /> {uiText.presets[notice]}</p>}
  </section>;
}
