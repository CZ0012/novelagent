import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AgentSettings, AgentSettingsUpdate, ConnectionProfile } from "./api";
import { activateLocale } from "./localization";
import { ModelRoutingSettings, modelExecutionLabel } from "./ModelRoutingSettings";
import { discussionTask, MODEL_TASKS, removeConnection, resolvedTask, settingsRequestIsCurrent, settingsSavePayload, settingsToForm, taskConnectionReady, supportsExplicitThinking, thinkingModePatch } from "./modelRouting";

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
    expect(html).toContain("不证明文本接口或工具调用兼容"); expect(html).toContain("规则质检不调用模型"); expect(html).toContain("语义连续性审阅");
    expect(html).toContain('type="password"'); expect(html).toContain('value="anthropic_messages"');
  });
  it("loads English independently and describes the exact stored execution", async () => {
    await activateLocale("en-US");
    const html = render(); expect(html).toContain("Anthropic Messages"); expect(html).not.toContain("默认模型连接");
    expect(modelExecutionLabel({ task: "revision", profile_id: profile.id, profile_name: profile.name, protocol: profile.protocol, model: profile.model })).toContain("custom-novel");
  });
});

describe("official DeepSeek thinking preferences", () => {
  it("preserves explicit default and named-profile values through form and save serialization", () => {
    const settings: AgentSettings = { ...legacy, llm_base_url: "https://api.deepseek.com/v1", llm_thinking_mode: "disabled", connection_profiles: [{ ...profile, protocol: "chat_completions", base_url: "https://api.deepseek.com", thinking_mode: "enabled" }] };
    const form = settingsToForm(settings); const saved = settingsSavePayload(form, "", false);
    expect(saved.llm_thinking_mode).toBe("disabled"); expect(saved.connection_profiles?.[0].thinking_mode).toBe("enabled");
    expect(resolvedTask(settings, "planning")?.thinking_mode).toBe("disabled");
    expect(resolvedTask({ ...settings, task_assignments: { planning: profile.id } }, "planning")?.thinking_mode).toBe("enabled");
    expect(settingsSavePayload(settingsToForm(legacy), "", false).llm_thinking_mode).toBe("provider_default");
    expect(settingsSavePayload({ ...settingsToForm(legacy), connection_profiles: [profile] }, "", false).connection_profiles?.[0].thinking_mode).toBe("provider_default");
  });
  it("restricts explicit controls to the official HTTPS Chat Completions endpoint", () => {
    expect(supportsExplicitThinking("https://api.deepseek.com/v1", "chat_completions")).toBe(true);
    for (const url of ["http://api.deepseek.com", "https://api.deepseek.com.example.test", "https://example.test", "https://user:password@api.deepseek.com", "https://api.deepseek.com:8443", "https://api.deepseek.com?route=one", "https://api.deepseek.com#other"]) expect(supportsExplicitThinking(url, "chat_completions")).toBe(false);
    expect(supportsExplicitThinking("https://api.deepseek.com", "responses")).toBe(false);
  });
  it("shows selector values without resetting an incompatible saved preference", () => {
    const settings: AgentSettings = { ...legacy, llm_thinking_mode: "disabled" }; const html = renderToStaticMarkup(<ModelRoutingSettings apiBase="http://localhost" settings={settings} form={settingsToForm(settings)} onFormChange={() => undefined} apiKeyInput="" onApiKeyChange={() => undefined} clearApiKey={false} onClearApiKeyChange={() => undefined} busy={false} />);
    expect(html).toContain("DeepSeek 思考模式"); expect(html).toContain("请恢复为服务商默认"); expect(html).toMatch(/value="disabled" disabled="" selected=""/);
    expect(settingsToForm(settings).llm_thinking_mode).toBe("disabled");
  });
});

describe("explicit official DeepSeek reasoning effort", () => {
  it("preserves default and named effort while omitting legacy unset settings and provenance", () => {
    const settings: AgentSettings = { ...legacy, llm_base_url: "https://api.deepseek.com/v1", llm_thinking_mode: "provider_default", llm_reasoning_effort: "low", connection_profiles: [{ ...profile, protocol: "chat_completions", base_url: "https://api.deepseek.com", thinking_mode: "enabled", reasoning_effort: "max" }] };
    const saved = settingsSavePayload(settingsToForm(settings), "", false);
    expect(saved.llm_reasoning_effort).toBe("low"); expect(saved.connection_profiles?.[0].reasoning_effort).toBe("max");
    expect(resolvedTask(settings, "planning")?.reasoning_effort).toBe("low");
    expect(resolvedTask({ ...settings, task_assignments: { planning: profile.id } }, "planning")?.reasoning_effort).toBe("max");
    const oldPayload = settingsSavePayload(settingsToForm({ ...legacy, connection_profiles: [profile] }), "", false);
    expect(oldPayload).not.toHaveProperty("llm_reasoning_effort"); expect(oldPayload.connection_profiles?.[0]).not.toHaveProperty("reasoning_effort");
    expect(resolvedTask(legacy, "planning")).not.toHaveProperty("reasoning_effort");
    expect(resolvedTask({ ...legacy, llm_reasoning_effort: null }, "planning")).not.toHaveProperty("reasoning_effort");
    expect(settingsSavePayload(settingsToForm({ ...legacy, llm_reasoning_effort: null }), "", false).llm_reasoning_effort).toBeNull();
  });
  it("explicitly clears effort when thinking is disabled without changing model or credentials", () => {
    const patch = thinkingModePatch("disabled"); expect(patch).toEqual({ thinking_mode: "disabled", reasoning_effort: null });
    const changed = { ...profile, reasoning_effort: "high" as const, ...patch };
    const payload = settingsSavePayload({ ...settingsToForm(legacy), connection_profiles: [changed], llm_thinking_mode: patch.thinking_mode, llm_reasoning_effort: patch.reasoning_effort }, "", false);
    expect(payload.connection_profiles?.[0].reasoning_effort).toBeNull(); expect(payload.llm_reasoning_effort).toBeNull();
    expect(payload.connection_profiles?.[0].model).toBe(profile.model); expect(payload.connection_profiles?.[0]).not.toHaveProperty("api_key");
    expect(thinkingModePatch("enabled")).not.toHaveProperty("reasoning_effort");
  });
  it("shows localized effort labels and requires saved effort before model discovery", async () => {
    const settings: AgentSettings = { ...legacy, llm_base_url: "https://api.deepseek.com/v1", llm_thinking_mode: "provider_default", llm_reasoning_effort: "low" };
    const props = { apiBase: "http://localhost", settings, form: settingsToForm(settings), onFormChange: () => undefined, apiKeyInput: "", onApiKeyChange: () => undefined, clearApiKey: false, onClearApiKeyChange: () => undefined, busy: false };
    let html = renderToStaticMarkup(<ModelRoutingSettings {...props} />); expect(html).toContain("推理强度"); expect(html).toMatch(/value="low" selected=""/); expect(modelExecutionLabel(resolvedTask(settings, "planning"))).toContain("推理强度: 低");
    html = renderToStaticMarkup(<ModelRoutingSettings {...props} form={{ ...props.form, llm_reasoning_effort: "high" }} />); expect(html).toContain("连接有未保存修改");
    await activateLocale("en-US"); expect(modelExecutionLabel(resolvedTask(settings, "planning"))).toContain("Reasoning effort: Low");
  });
  it("keeps invalid explicit effort visible with a safe capability hint until cleared", () => {
    const settings: AgentSettings = { ...legacy, llm_thinking_mode: "disabled", llm_reasoning_effort: "high" };
    const html = renderToStaticMarkup(<ModelRoutingSettings apiBase="http://localhost" settings={settings} form={settingsToForm(settings)} onFormChange={() => undefined} apiKeyInput="" onApiKeyChange={() => undefined} clearApiKey={false} onClearApiKeyChange={() => undefined} busy={false} />);
    expect(html).toContain("请清除强度或调整思考模式"); expect(html).toMatch(/value="high" disabled="" selected=""/);
  });
});
