import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AgentSettings, AgentSettingsUpdate, ConnectionProfile } from "./api";
import { activateLocale } from "./localization";
import { ModelRoutingSettings, modelExecutionLabel } from "./ModelRoutingSettings";
import { discussionTask, MODEL_TASKS, removeConnection, resolvedTask, settingsRequestIsCurrent, settingsSavePayload, settingsToForm, taskConnectionReady } from "./modelRouting";

const legacy: AgentSettings = { selected_preset_id: "preset", agent_presets: [], scene_writer: "llm", provider_label: "My provider", llm_base_url: "https://example.test/v1", llm_model: "custom-model", api_key_configured: true, api_key_preview: "masked-only", llm_json_mode: true, permission_level: "read_generate" };
const profile: ConnectionProfile = { id: "novelist", name: "Novel provider", protocol: "anthropic_messages", base_url: "https://other.test", model: "custom-novel", json_mode: false, api_key_configured: true, api_key_preview: "masked-profile" };
beforeEach(async () => { await activateLocale("zh-CN"); });

describe("saved task routing", () => {
  it("keeps legacy flat settings as the default Chat Completions connection for all tasks", () => {
    for (const task of MODEL_TASKS) {
      expect(resolvedTask(legacy, task)).toEqual({ task, profile_id: "default", profile_name: "My provider", protocol: "chat_completions", model: "custom-model" });
      expect(taskConnectionReady(legacy, task)).toBe(true);
    }
  });
  it("can use an explicitly assigned profile even when default credentials are absent", () => {
    const settings = { ...legacy, api_key_configured: false, connection_profiles: [profile], task_assignments: { writing: profile.id } };
    expect(resolvedTask(settings, "writing")?.model).toBe(profile.model);
    expect(taskConnectionReady(settings, "writing")).toBe(true);
    expect(taskConnectionReady(settings, "discussion")).toBe(false);
  });
  it("never falls back from a missing or unconfigured explicit profile", () => {
    expect(resolvedTask({ ...legacy, task_assignments: { writing: "deleted" } }, "writing")).toBeNull();
    expect(taskConnectionReady({ ...legacy, connection_profiles: [{ ...profile, api_key_configured: false }], task_assignments: { revision: profile.id } }, "revision")).toBe(false);
  });
  it("uses the backend resolved snapshot when supplied", () => {
    const snapshot = { task: "writing" as const, profile_id: profile.id, profile_name: "Resolved name", protocol: "responses" as const, model: "pinned-model" };
    expect(resolvedTask({ ...legacy, resolved_tasks: { writing: snapshot } }, "writing")).toEqual(snapshot);
  });
  it.each([["discuss", "discussion"], ["revise_scene", "revision"], ["revise_selection", "revision"], ["continue_scene", "writing"], ["create_scene", "writing"]] as const)("routes %s to %s", (mode, task) => expect(discussionTask(mode)).toBe(task));
});

describe("settings write boundary", () => {
  it("never copies saved key previews, resolved snapshots, or an old preset into the editable form", () => {
    const form = settingsToForm({ ...legacy, connection_profiles: [profile], task_assignments: { writing: profile.id } });
    expect(form.llm_protocol).toBe("chat_completions");
    expect(form.selected_preset_id).toBeUndefined();
    expect(JSON.stringify(form)).not.toMatch(/masked|api_key_configured|api_key_preview|resolved_tasks/);
  });
  it("preserves blank credentials and serializes only explicit whitelisted fields", () => {
    const form = { ...settingsToForm(legacy), connection_profiles: [{ ...profile, api_key: "", unexpected_secret: "do-not-send" }], unexpected_secret: "also-private" };
    const payload = settingsSavePayload(form, "", false);
    expect(payload.llm_api_key).toBeNull();
    expect(payload.connection_profiles?.[0]).not.toHaveProperty("api_key");
    expect(JSON.stringify(payload)).not.toMatch(/masked|unexpected|do-not-send|also-private|api_key_configured/);
  });
  it("supports an explicit replacement and clear independently for each connection", () => {
    const form = { ...settingsToForm(legacy), connection_profiles: [{ ...profile, api_key: "replacement-key" }, { ...profile, id: "clear-me", clear_api_key: true }] };
    const payload = settingsSavePayload(form, "new-default-key", false);
    expect(payload.llm_api_key).toBe("new-default-key");
    expect(payload.connection_profiles?.[0].api_key).toBe("replacement-key");
    expect(payload.connection_profiles?.[1].clear_api_key).toBe(true);
    expect(settingsSavePayload(form, "", true).clear_api_key).toBe(true);
  });
  it("removes task references when explicitly deleting a connection", () => {
    const form: AgentSettingsUpdate = { ...settingsToForm(legacy), connection_profiles: [profile, { ...profile, id: "other" }], task_assignments: { writing: profile.id, discussion: profile.id, planning: "other" } };
    const next = removeConnection(form, profile.id);
    expect(next.connection_profiles?.map((item) => item.id)).toEqual(["other"]);
    expect(next.task_assignments).toMatchObject({ writing: null, discussion: null, planning: "other" });
  });
  it("rejects stale responses after navigation, another request, or author edits", () => {
    const request = { apiBase: "http://localhost:8000", sequence: 2, revision: 3 };
    expect(settingsRequestIsCurrent(request, { ...request })).toBe(true);
    expect(settingsRequestIsCurrent(request, { ...request, apiBase: "http://localhost:8001" })).toBe(false);
    expect(settingsRequestIsCurrent(request, { ...request, sequence: 3 })).toBe(false);
    expect(settingsRequestIsCurrent(request, { ...request, revision: 4 })).toBe(false);
  });
});

describe("model settings presentation", () => {
  function render() {
    return renderToStaticMarkup(<ModelRoutingSettings apiBase="http://localhost:8000" settings={legacy} form={settingsToForm(legacy)} onFormChange={vi.fn()} apiKeyInput="" onApiKeyChange={vi.fn()} clearApiKey={false} onClearApiKeyChange={vi.fn()} busy={false} />);
  }
  it("keeps extra connections and role assignment folded, with truthful model-list and QA descriptions", () => {
    const html = render();
    expect(html).toContain("更多连接配置"); expect(html).toContain("任务模型分工");
    expect(html).not.toContain("<details open");
    expect(html).toContain("不证明文本接口或工具调用兼容"); expect(html).toContain("当前使用规则检查，不调用模型");
    expect(html).toContain('type="password"'); expect(html).toContain('value="anthropic_messages"');
  });
  it("loads English independently and describes the exact stored execution", async () => {
    await activateLocale("en-US");
    const html = render(); expect(html).toContain("Anthropic Messages"); expect(html).not.toContain("默认模型连接");
    expect(modelExecutionLabel({ task: "revision", profile_id: profile.id, profile_name: profile.name, protocol: profile.protocol, model: profile.model })).toContain("custom-novel");
  });
});
