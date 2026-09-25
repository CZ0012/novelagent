import { readFileSync } from "node:fs";
import ts from "typescript";
import { describe, expect, it, vi } from "vitest";
import { activateLocale, appText, formatRefKind, loadLocaleCatalog, localeRegistry, localizeGraphLabel, normalizeAppLocale, uiText } from "./index";

function leaves(value: unknown, prefix = ""): Record<string, string> {
  if (typeof value !== "object" || value === null) return { [prefix]: typeof value };
  return Object.fromEntries(Object.entries(value).flatMap(([key, nested]) => Object.entries(leaves(nested, `${prefix}.${key}`))));
}

describe("independent language catalogs", () => {
  it("keeps locale resource modules self-contained with type-only dependencies", () => {
    for (const locale of Object.keys(localeRegistry)) {
      const source = readFileSync(new URL(`./${locale}.ts`, import.meta.url), "utf8");
      const parsed = ts.createSourceFile(`${locale}.ts`, source, ts.ScriptTarget.Latest, true);
      const runtimeImports: string[] = [];
      function visit(node: ts.Node): void {
        if (ts.isImportDeclaration(node) && !node.importClause?.isTypeOnly) runtimeImports.push(node.getText(parsed));
        if (ts.isExportDeclaration(node) && node.moduleSpecifier && !node.isTypeOnly) runtimeImports.push(node.getText(parsed));
        if (ts.isImportEqualsDeclaration(node) && !node.isTypeOnly) runtimeImports.push(node.getText(parsed));
        if (ts.isCallExpression(node) && node.expression.kind === ts.SyntaxKind.ImportKeyword) runtimeImports.push(node.getText(parsed));
        ts.forEachChild(node, visit);
      }
      visit(parsed);
      expect(runtimeImports, `${locale} must not load another catalog at runtime`).toEqual([]);
    }
  });

  it("can start the English UI when loading the Chinese catalog would fail", async () => {
    vi.resetModules();
    vi.doMock("./zh-CN", () => { throw new Error("Unselected Chinese catalog was requested"); });
    try {
      const isolated = await import("./index");
      await isolated.activateLocale("en-US");
      expect(isolated.uiText.tabs.write).toBe("Write");
    } finally {
      vi.doUnmock("./zh-CN");
      vi.resetModules();
    }
  });

  it("requires every registered language to supply the same complete string and formatter keys", async () => {
    const catalogs = await Promise.all(Object.keys(localeRegistry).map(loadLocaleCatalog));
    const reference = leaves(catalogs[0]);
    expect(Object.keys(reference).length).toBeGreaterThan(400);
    for (const catalog of catalogs) expect(leaves(catalog)).toEqual(reference);
  });

  it("loading project content labels does not activate that UI locale", async () => {
    await activateLocale("en-US");
    const content = await loadLocaleCatalog("zh-CN");
    expect(content.contentDefaults.genre).toBe("奇幻");
    expect(uiText.tabs.write).toBe("Write");
    const title = appText.documentTitle;
    await loadLocaleCatalog("zh-CN");
    expect(appText.documentTitle).toBe(title);
    await activateLocale("zh-CN");
    expect(uiText.tabs.write).toBe("写作");
  });

  it("defaults unsupported saved preferences safely without conflating content language", () => {
    expect(normalizeAppLocale("unknown")).toBe("zh-CN");
    expect(normalizeAppLocale("en-US")).toBe("en-US");
    expect(normalizeAppLocale("__proto__")).toBe("zh-CN");
  });

  it("provides readable graph labels for every node and edge in the backend contract model", async () => {
    const graphModel = readFileSync(new URL("../../../../storygraph/models/graph.py", import.meta.url), "utf8");
    const labels = ["NODE_LABELS", "EDGE_LABELS"].flatMap((name) => {
      const block = graphModel.match(new RegExp(`${name}\\s*=\\s*\\{([^}]+)\\}`));
      expect(block, `${name} must be discoverable in the graph contract model`).not.toBeNull();
      return [...block![1].matchAll(/"([A-Za-z_]+)"/g)].map((match) => match[1]);
    });
    expect(labels.length).toBeGreaterThan(30);
    for (const locale of Object.keys(localeRegistry)) {
      const catalog = await loadLocaleCatalog(locale);
      const graphLabels = catalog.graphLabels as Record<string, string>;
      for (const label of labels) {
        expect(Object.prototype.hasOwnProperty.call(graphLabels, label), `${locale}: ${label}`).toBe(true);
        expect(graphLabels[label].trim()).not.toBe("");
        if (locale === "zh-CN") expect(graphLabels[label], label).toMatch(/\p{Script=Han}/u);
        if (label.includes("_")) expect(graphLabels[label], label).not.toContain("_");
      }
    }
  });

  it("uses the active UI catalog for graph enums without translating unknown author text", async () => {
    await activateLocale("zh-CN");
    expect(localizeGraphLabel("NEXT_SCENE")).toBe("下一场景");
    expect(localizeGraphLabel("WorldRule")).toBe("世界规则");
    expect(formatRefKind("project")).toBe("项目");
    expect(formatRefKind("canon_event")).toBe("正典变更记录");
    expect(localizeGraphLabel("A Historical Scene Title")).toBe("A Historical Scene Title");
    expect(localizeGraphLabel("__proto__")).toBe("__proto__");
    await activateLocale("en-US");
    expect(localizeGraphLabel("NEXT_SCENE")).toBe("Next scene");
    expect(formatRefKind("project")).toBe("Project");
    expect(formatRefKind("canon_event")).toBe("Canon change record");
    expect(localizeGraphLabel("既有中文标题")).toBe("既有中文标题");
  });
});
