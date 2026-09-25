import type { AgentDiscussionMode, AgentSettings, AgentSettingsUpdate, ConnectionProfileUpdate, ModelExecution, ModelTask, TaskAssignments } from "./api";

export const MODEL_TASKS: ModelTask[] = ["planning", "writing", "revision", "discussion", "extraction"];

export function settingsToForm(settings: AgentSettings): AgentSettingsUpdate {
  return {
    scene_writer: settings.scene_writer, provider_label: settings.provider_label, llm_base_url: settings.llm_base_url,
    llm_model: settings.llm_model, llm_json_mode: settings.llm_json_mode, permission_level: settings.permission_level,
    llm_protocol: settings.llm_protocol ?? "chat_completions",
    connection_profiles: settings.connection_profiles?.map((profile) => ({ id: profile.id, name: profile.name, protocol: profile.protocol, base_url: profile.base_url, model: profile.model, json_mode: profile.json_mode })),
    task_assignments: settings.task_assignments ? { ...settings.task_assignments } : undefined
  };
}

/** Only explicit editable fields cross the settings write boundary. Secret previews never do. */
export function settingsSavePayload(form: AgentSettingsUpdate, key: string, clear: boolean): AgentSettingsUpdate {
  const profiles = form.connection_profiles?.map((profile): ConnectionProfileUpdate => ({
    id: profile.id, name: profile.name, protocol: profile.protocol, base_url: profile.base_url, model: profile.model, json_mode: profile.json_mode,
    ...(profile.api_key ? { api_key: profile.api_key } : {}), ...(profile.clear_api_key ? { clear_api_key: true } : {})
  }));
  const assignments = form.task_assignments ? Object.fromEntries(MODEL_TASKS.map((task) => [task, form.task_assignments?.[task] ?? null])) as TaskAssignments : undefined;
  return { scene_writer: form.scene_writer, provider_label: form.provider_label, llm_base_url: form.llm_base_url,
    llm_model: form.llm_model, llm_protocol: form.llm_protocol, llm_json_mode: form.llm_json_mode, permission_level: form.permission_level,
    ...(form.selected_preset_id ? { selected_preset_id: form.selected_preset_id } : {}),
    ...(profiles ? { connection_profiles: profiles } : {}), ...(assignments ? { task_assignments: assignments } : {}),
    llm_api_key: key || null, clear_api_key: clear };
}

export function removeConnection(form: AgentSettingsUpdate, profileId: string): AgentSettingsUpdate {
  return { ...form, connection_profiles: form.connection_profiles?.filter((profile) => profile.id !== profileId),
    task_assignments: Object.fromEntries(MODEL_TASKS.map((task) => [task, form.task_assignments?.[task] === profileId ? null : form.task_assignments?.[task] ?? null])) };
}

export function discussionTask(mode: AgentDiscussionMode): ModelTask {
  return mode === "discuss" ? "discussion" : mode === "revise_scene" || mode === "revise_selection" ? "revision" : "writing";
}

export function resolvedTask(settings: AgentSettings | null, task: ModelTask): ModelExecution | null {
  if (!settings) return null;
  if (settings.resolved_tasks?.[task]) return settings.resolved_tasks[task]!;
  const id = settings.task_assignments?.[task];
  if (id) {
    const profile = settings.connection_profiles?.find((candidate) => candidate.id === id);
    return profile ? { task, profile_id: profile.id, profile_name: profile.name, protocol: profile.protocol, model: profile.model } : null;
  }
  return { task, profile_id: "default", profile_name: settings.provider_label, protocol: settings.llm_protocol ?? "chat_completions", model: settings.llm_model };
}
export function taskConnectionReady(settings: AgentSettings | null, task: ModelTask): boolean {
  const execution = resolvedTask(settings, task);
  if (!settings || !execution?.model.trim()) return false;
  if (execution.profile_id === "default") return Boolean(settings.api_key_configured && settings.llm_base_url.trim());
  const profile = settings.connection_profiles?.find((item) => item.id === execution.profile_id);
  return Boolean(profile?.api_key_configured && profile.base_url.trim());
}

export function settingsRequestIsCurrent(request: { apiBase: string; sequence: number; revision: number }, current: { apiBase: string; sequence: number; revision: number }): boolean {
  return request.apiBase === current.apiBase && request.sequence === current.sequence && request.revision === current.revision;
}
