import { readFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, expect, it, vi } from "vitest";
import { activateLocale } from "./localization";
import { MainAgentDock, MainAgentWelcome } from "./MainAgentDock";
import { clampMainAgentShare, mainAgentKeyboardShare, readMainAgentShare, writeMainAgentShare } from "./mainAgentLayout";

beforeEach(async () => { await activateLocale("zh-CN"); });
it("bounds saved proportions and tolerates corrupt, unavailable and old storage", () => {
  expect(readMainAgentShare({ getItem: () => '{"version":1,"share":500}' })).toBe(72);
  for (const raw of ["broken", '{"version":2,"share":35}', '{"version":1,"share":"35"}']) expect(readMainAgentShare({ getItem: () => raw })).toBe(48);
  expect(readMainAgentShare({ getItem: () => { throw new Error(); } })).toBe(48);
  const setItem = vi.fn(); writeMainAgentShare({ setItem }, 24);
  expect(JSON.parse(setItem.mock.calls[0][1])).toEqual({ version: 1, share: 28 });
  expect(() => writeMainAgentShare({ setItem: () => { throw new Error(); } }, 40)).not.toThrow();
  expect(clampMainAgentShare(Number.NaN)).toBe(48);
});
it("keyboard controls use the same bounded proportion as pointer resizing", () => {
  expect(mainAgentKeyboardShare("ArrowUp", 48)).toBe(50);
  expect(mainAgentKeyboardShare("ArrowDown", 48, true)).toBe(38);
  expect(mainAgentKeyboardShare("Home", 48)).toBe(28);
  expect(mainAgentKeyboardShare("End", 48)).toBe(72);
  expect(mainAgentKeyboardShare("ArrowUp", 72)).toBe(72);
  expect(mainAgentKeyboardShare("Enter", 48)).toBeNull();
});
it("renders a single accessible persistent dock and local project onboarding in each locale", async () => {
  for (const locale of ["zh-CN", "en-US"] as const) {
    await activateLocale(locale);
    const html = renderToStaticMarkup(<MainAgentDock manuscript={<p>manuscript</p>}><p>conversation</p></MainAgentDock>);
    expect(html.match(/role="separator"/g)).toHaveLength(1);
    expect(html).toContain('aria-valuenow="48"');
    expect(html).toContain('aria-orientation="horizontal"');
    expect(html).toContain('tabindex="0"');
    const welcome = renderToStaticMarkup(<MainAgentWelcome busy={false} canCreate modelReady={false} onCreate={async () => {}} onOpenSettings={() => {}} />);
    expect(welcome).toContain(locale === "zh-CN" ? "打开模型设置" : "Open model settings");
    expect(welcome).toContain(locale === "zh-CN" ? "创建本地项目与会话" : "Create local project and session");
  }
});
it("App hosts the main conversation once independently from upper workspace navigation", () => {
  const app = readFileSync(new URL("./App.tsx", import.meta.url), "utf8");
  expect(app.match(/<AuthoringStudio\b/g)).toHaveLength(1);
  expect(app).toContain('active={true} layout="dock"');
  expect(app).not.toContain('<div hidden={workspaceTab !== "authoring"}>');
  expect(app).toContain('key={`authoring:${apiBase}:${projectId}`}');
});
