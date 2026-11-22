import { describe, expect, it } from "vitest";
import type { AgentSettings, WriterChoice } from "./api";
import { effectiveWriterChoice, writerEntryMode, writerChoiceReference, scopedWriterChoice, writerChoiceExecution, writerChoiceReady } from "./WriterChoicePicker";
const choice: WriterChoice = { profile_id: "plan", profile_name: "Writer A", model: "eligible", auth_mode: "chatgpt_plan", fingerprint: "frozen-registration" };
const settings: AgentSettings = { selected_preset_id: "p", agent_presets: [], scene_writer: "llm", provider_label: "Old default", llm_base_url: "https://example.test/v1", llm_model: "default-model", api_key_configured: true, llm_json_mode: true, permission_level: "read_generate", connection_profiles: [{ id: "plan", name: "Writer A", model: "eligible", auth_mode: "chatgpt_plan", chatgpt_account_id: "author", protocol: "responses", base_url: "", api_key_configured: false, account_ready: true, json_mode: true }] };
describe("per-request Writer selection", () => {
  it("does not reuse choices across API, project or scene boundaries", () => {
    const scope = { apiBase: "http://local", projectId: "p", sceneId: "s" };
    const state = { ...scope, choice };
    expect(scopedWriterChoice(state, scope)).toBe(choice);
    for (const changed of [{ apiBase: "http://other" }, { projectId: "other" }, { sceneId: "other" }]) expect(scopedWriterChoice(state, { ...scope, ...changed })).toBeNull();
  });
  it("uses selected registration readiness and never inherits a ready API default", () => {
    expect(writerChoiceReady(choice, settings)).toBe(true);
    expect(writerChoiceReady(choice, { ...settings, connection_profiles: [] })).toBe(false);
    expect(writerChoiceReady(choice, { ...settings, connection_profiles: settings.connection_profiles?.map(p => ({ ...p, account_ready: false })) })).toBe(false);
    expect(writerChoiceReady({ ...choice, model: "old" }, settings)).toBe(false);
    expect(writerChoiceReady({ ...choice, auth_mode: "api_key" }, settings)).toBe(false);
    expect(writerChoiceExecution(choice, settings, "revision")).toMatchObject({ profile_id: "plan", protocol: "responses", model: "eligible", auth_mode: "chatgpt_plan", task: "revision" });
    expect(settings.task_assignments).toBeUndefined();
  });
});

it("automatically follows the restored session for ordinary scene writing but preserves explicit overrides", () => {
  const scope = { apiBase: "local", projectId: "p", sceneId: "s" };
  const context = { apiBase: "local", projectId: "p", sessionId: "session-a", choice };
  expect(effectiveWriterChoice(context, null, scope)).toBe(choice);
  const reset = { ...scope, sessionId: "session-a", choice: null };
  expect(effectiveWriterChoice(context, reset, scope)).toBeNull();
  expect(effectiveWriterChoice({ ...context, choice: { ...choice, model: "new-main-choice" } }, reset, scope)).toBeNull();
  const manual = { ...reset, choice: { ...choice, profile_id: "manual" } };
  expect(effectiveWriterChoice(context, manual, scope)?.profile_id).toBe("manual");
  expect(effectiveWriterChoice({ ...context, sessionId: "session-b" }, manual, scope)).toBe(choice);
  expect(effectiveWriterChoice(context, manual, { ...scope, sceneId: "next-scene" })).toBe(choice);
  expect(effectiveWriterChoice(context, manual, { ...scope, projectId: "foreign" })).toBeNull();
  expect(effectiveWriterChoice(context, manual, { ...scope, apiBase: "foreign" })).toBeNull();
});
it("includes only the fingerprint reference for all prose modes and excludes discussion/private reasons", () => {
  for (const mode of ["create_scene", "continue_scene", "revise_scene", "revise_selection"] as const) expect(writerChoiceReference(mode, { ...choice, reason: "private author discussion" })).toEqual({ profile_id: choice.profile_id, fingerprint: choice.fingerprint });
  expect(writerChoiceReference("discuss", choice)).toBeUndefined();
  expect(writerChoiceReference("continue_scene", null)).toBeUndefined();
});
it("opens saved prose as continuation and empty scenes as creation", () => {
  expect(writerEntryMode({ text: "saved original prose" })).toEqual({ mode: "continue_scene", includeLatestDraft: true });
  expect(writerEntryMode(null)).toEqual({ mode: "create_scene", includeLatestDraft: false });
  expect(writerEntryMode({ text: "  " })).toEqual({ mode: "create_scene", includeLatestDraft: false });
});
