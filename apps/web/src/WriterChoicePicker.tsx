import { useEffect, useRef, useState } from "react";
import { apiGet, type AgentDiscussionMode, type AgentSettings, type ModelExecution, type ModelTask, type WriterChoice } from "./api";
import { uiText } from "./localization";
export type SessionWriterContext = { apiBase: string; projectId: string; sessionId: string; choice: WriterChoice | null };
export type WriterOverride = { apiBase: string; projectId: string; sceneId: string; sessionId: string | null; choice: WriterChoice | null };
export function effectiveWriterChoice(context: SessionWriterContext | null, override: WriterOverride | null, scope: { apiBase: string; projectId: string; sceneId: string }): WriterChoice | null {
  const session = context?.apiBase === scope.apiBase && context.projectId === scope.projectId ? context : null;
  if (override?.apiBase === scope.apiBase && override.projectId === scope.projectId && override.sceneId === scope.sceneId && override.sessionId === (session?.sessionId ?? null)) return override.choice;
  return scope.sceneId ? session?.choice ?? null : null;
}
export function writerChoiceReference(mode: AgentDiscussionMode, choice: WriterChoice | null): Pick<WriterChoice, "profile_id" | "fingerprint"> | undefined { return mode !== "discuss" && choice ? { profile_id: choice.profile_id, fingerprint: choice.fingerprint } : undefined; }
export function writerEntryMode(draft: { text: string } | null): { mode: "continue_scene" | "create_scene"; includeLatestDraft: boolean } { return draft?.text.trim() ? { mode: "continue_scene", includeLatestDraft: true } : { mode: "create_scene", includeLatestDraft: false }; }
export type ScopedWriterChoice = { apiBase: string; projectId: string; sceneId: string; choice: WriterChoice };
export function scopedWriterChoice(value: ScopedWriterChoice | null, scope: Omit<ScopedWriterChoice, "choice">): WriterChoice | null { return value && value.apiBase === scope.apiBase && value.projectId === scope.projectId && value.sceneId === scope.sceneId ? value.choice : null; }
export function writerChoiceExecution(choice: WriterChoice | null, settings: AgentSettings | null, task: ModelTask): ModelExecution | null {
  if (!choice || !settings) return null;
  if (choice.profile_id === "default") return { profile_id: "default", profile_name: choice.profile_name, model: choice.model, auth_mode: choice.auth_mode, protocol: settings.llm_protocol ?? "chat_completions", task };
  const profile = settings.connection_profiles?.find(p => p.id === choice.profile_id);
  return profile ? { profile_id: choice.profile_id, profile_name: choice.profile_name, model: choice.model, auth_mode: choice.auth_mode, protocol: profile.protocol, task } : null;
}
export function writerChoiceReady(choice: WriterChoice | null, settings: AgentSettings | null): boolean {
  if (!choice || !settings) return false;
  if (choice.profile_id === "default") return choice.auth_mode === "api_key" && settings.api_key_configured && Boolean(settings.llm_base_url.trim()) && settings.llm_model === choice.model;
  const profile = settings.connection_profiles?.find(p => p.id === choice.profile_id);
  return Boolean(profile && profile.model === choice.model && (profile.auth_mode ?? "api_key") === choice.auth_mode && (profile.auth_mode === "chatgpt_plan" ? profile.account_ready === true : profile.api_key_configured && profile.base_url.trim()));
}
export function WriterChoicePicker({ apiBase, projectId, sceneId, choice, sessionChoice, busy, onChange }: { apiBase: string; projectId: string; sceneId: string; choice: WriterChoice | null; sessionChoice: WriterChoice | null; busy: boolean; onChange: (choice: WriterChoice | null) => void }) {
  const [writers, setWriters] = useState<WriterChoice[]>([]), [loading, setLoading] = useState(false), [error, setError] = useState(false);
  const scope = `${apiBase}:${projectId}:${sceneId}`, currentScope = useRef(scope); currentScope.current = scope;
  useEffect(() => { setWriters([]); setLoading(false); setError(false); }, [scope]);
  async function refresh() { const request = scope; setLoading(true); setError(false); try { const result = await apiGet<{ writers: WriterChoice[] }>(apiBase, "/settings/agent/writers"); if (request === currentScope.current) setWriters(result.writers); } catch { if (request === currentScope.current) setError(true); } finally { if (request === currentScope.current) setLoading(false); } }
  return <div className="writer-choice-picker"><label><span>{uiText.chatgpt.writerChoice}</span><select disabled={busy || loading} value={choice?.fingerprint ?? ""} onChange={e => onChange(e.target.value ? writers.find(w => w.fingerprint === e.target.value) ?? (sessionChoice?.fingerprint === e.target.value ? sessionChoice : choice) : null)}><option value="">{uiText.chatgpt.writerDefault}</option>{choice && !writers.some(w => w.fingerprint === choice.fingerprint) && <option value={choice.fingerprint}>{choice.profile_name} · {choice.model}</option>}{writers.map(w => <option key={w.fingerprint} value={w.fingerprint}>{w.profile_name} · {w.model} · {w.auth_mode === "chatgpt_plan" ? uiText.chatgpt.using : "API Key"}</option>)}</select></label><button type="button" disabled={busy || loading} onClick={() => { void refresh(); }}>{uiText.chatgpt.writerRefresh}</button>{sessionChoice && <button type="button" disabled={busy || loading} onClick={() => onChange(sessionChoice)}>{uiText.chatgpt.writerSession}</button>}{choice && <button type="button" disabled={busy} onClick={() => onChange(null)}>{uiText.chatgpt.writerDefault}</button>}{error && <p role="alert">{uiText.chatgpt.writerMissing}</p>}<small>{uiText.chatgpt.writerOverrideHelp}</small></div>;
}
