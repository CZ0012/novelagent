import type { AgentSettings, AgentSettingsUpdate } from "./api";
import { settingsToForm } from "./modelRouting";
/** A targeted commit rebases only its new profile and an unedited discussion assignment. */
export function mergeConnectionCommit(current: AgentSettingsUpdate, before: AgentSettings | null, saved: AgentSettings, profileId: string): AgentSettingsUpdate {
  const profile = settingsToForm(saved).connection_profiles?.find(item => item.id === profileId);
  const exists = current.connection_profiles?.some(item => item.id === profileId);
  return { ...current, connection_profiles: profile && !exists ? [...(current.connection_profiles ?? []), profile] : current.connection_profiles, task_assignments: (current.task_assignments?.discussion ?? null) === (before?.task_assignments?.discussion ?? null) ? { ...current.task_assignments, discussion: saved.task_assignments?.discussion ?? null } : current.task_assignments };
}
