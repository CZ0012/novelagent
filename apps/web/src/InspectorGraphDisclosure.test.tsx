import { readFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it } from "vitest";
import { activateLocale } from "./localization";
import { InspectorGraphDisclosure } from "./InspectorGraphDisclosure";
const css = readFileSync(new URL("./styles.css", import.meta.url), "utf8");
const app = readFileSync(new URL("./App.tsx", import.meta.url), "utf8");
beforeEach(async () => { await activateLocale("zh-CN"); });
describe("large-project inspector space", () => {
  it("keeps a 200-scene graph collapsed by default while preserving every scene", () => {
    const html = renderToStaticMarkup(<InspectorGraphDisclosure><div>{Array.from({ length: 200 }, (_, index) => <p key={index}>场景 {index + 1}</p>)}</div></InspectorGraphDisclosure>);
    expect(html).toContain('<details class="inspector-graph-disclosure">'); expect(html).not.toContain("<details open"); expect(html).toContain("场景 200"); expect(html.match(/<p>/g)).toHaveLength(200);
  });
  it("gives evidence its own scrollable main row and bounds expanded graph height", () => {
    expect(app).toContain('<div className="inspector-content" ref={inspectorContentRef}>');
    expect(app).toContain('<InspectorGraphDisclosure><GraphPreview');
    expect(css).toMatch(/\.inspector-content\s*\{[^}]*min-height:\s*0;[^}]*overflow:\s*auto;/);
    expect(css).toMatch(/\.inspector-graph-scroll\s*\{[^}]*max-height:\s*min\(28vh,\s*250px\);[^}]*overflow:\s*auto;/);
    expect(css).toMatch(/\.inspector-graph-disclosure\s*\{[^}]*max-height:\s*min\(36vh,\s*300px\);/);
  });
});
