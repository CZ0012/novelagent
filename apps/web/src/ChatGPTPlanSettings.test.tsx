import { withPlanReadiness } from "./ChatGPTPlanSettings";
import { readFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it } from "vitest";
import { ChatGPTPlanSettings, ChatGPTUsage, eligibleChatGPTAccount, CHATGPT_USAGE_URL } from "./ChatGPTPlanSettings";
import { activateLocale } from "./localization";
import { settingsSavePayload, settingsToForm, taskConnectionReady } from "./modelRouting";
import type { AgentSettings } from "./api";
const settings: AgentSettings = { selected_preset_id: "p", agent_presets: [], scene_writer: "llm", provider_label: "Old API", llm_base_url: "https://example.test/v1", llm_model: "old-model", api_key_configured: true, llm_json_mode: true, permission_level: "read_generate", connection_profiles: [{ id: "plan", name: "Plan", auth_mode: "chatgpt_plan", chatgpt_account_id: "account-a", account_ready: true, protocol: "responses", base_url: "", model: "eligible-model", json_mode: true, api_key_configured: false }], task_assignments: { discussion: "plan" } };
beforeEach(async () => { await activateLocale("zh-CN"); });
describe("ChatGPT plan safety", () => {
  it("requires consent and exact connected registration for discovery", () => {
    const status = { supported: true, active_account_id: "other", accounts: [{ account_id: "account-a", label: "Author", connected: true, plan_enabled: false, welcome_pending: true }] };
    expect(eligibleChatGPTAccount(status, "account-a")).toBe(false);
    status.accounts[0].plan_enabled = true;
    expect(eligibleChatGPTAccount(status, "account-a")).toBe(true);
    expect(eligibleChatGPTAccount(status, "other")).toBe(false);
    status.supported = false;
    expect(eligibleChatGPTAccount(status, "account-a")).toBe(false);
  });
  it("uses account readiness independently of API credentials without fallback", () => {
    expect(taskConnectionReady(settings, "discussion")).toBe(true);
    expect(taskConnectionReady({ ...settings, connection_profiles: settings.connection_profiles?.map(p => ({ ...p, account_ready: false })) }, "discussion")).toBe(false);
    expect(taskConnectionReady(settings, "writing")).toBe(true);
  });
  it("round trips account pins without changing default credentials or task routing", () => {
    const payload = settingsSavePayload(settingsToForm(settings), "", false);
    expect(payload.llm_base_url).toBe(settings.llm_base_url);
    expect(payload.llm_model).toBe(settings.llm_model);
    expect(payload.llm_api_key).toBeNull();
    expect(payload.clear_api_key).toBe(false);
    expect(payload.connection_profiles?.[0]).toMatchObject({ auth_mode: "chatgpt_plan", chatgpt_account_id: "account-a", protocol: "responses" });
    expect(payload.connection_profiles?.[0]).not.toHaveProperty("account_ready");
    expect(payload.task_assignments?.discussion).toBe("plan");
  });
  it("shows an explicit sign-in action without a credential or code field", () => {
    const html = renderToStaticMarkup(<ChatGPTPlanSettings apiBase="http://localhost" busy={false} onAdd={() => undefined} onStatus={() => undefined} />);
    expect(html).toContain("Continue with ChatGPT");
    expect(html).not.toContain('type="password"');
    expect(html).not.toContain("localStorage");
    expect(html).toContain(CHATGPT_USAGE_URL);
    expect(renderToStaticMarkup(<ChatGPTUsage active />)).toContain(CHATGPT_USAGE_URL);
    expect(renderToStaticMarkup(<ChatGPTUsage active={false} />)).toBe("");
  });
});

it("resets pending UI locks and discovery state when the backend scope changes", () => {
  const source = readFileSync(new URL("./ChatGPTPlanSettings.tsx", import.meta.url), "utf8");
  const reset = source.slice(source.indexOf("useEffect(() => { generation.current++"), source.indexOf("}, [apiBase]);") + "}, [apiBase]);".length);
  expect(reset).toContain("setWorking(false)");
  expect(reset).toContain("setDiscovered(false)");
  expect(reset).toContain('setAccountId("")');
  expect(reset).toContain("generation.current++");
});

it("does not fabricate settings when local account status arrives first", () => {
  const status = { supported: true, active_account_id: null, accounts: [] };
  expect(withPlanReadiness(null, status)).toBeNull();
  const updated = withPlanReadiness(settings, status)!;
  expect(updated.llm_model).toBe(settings.llm_model);
  expect(updated.connection_profiles?.[0].account_ready).toBe(false);
  expect(withPlanReadiness(updated, status)).toBe(updated);
});