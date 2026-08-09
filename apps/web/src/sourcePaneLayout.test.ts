import { describe, expect, it } from "vitest";
import {
  DEFAULT_SOURCE_PANE_LAYOUT,
  SOURCE_PANE_PREFERENCE_VERSION,
  clampSourcePaneLayout,
  parseSourcePaneLayout,
  readSourcePaneLayout,
  resetSourcePaneLayoutDimension,
  separatorKeyboardValue,
  serializeSourcePaneLayout,
  sourcePaneBounds,
  writeSourcePaneLayout
} from "./sourcePaneLayout";

describe("source pane layout preferences", () => {
  it("uses versioned defaults for missing, corrupt, and stale preferences", () => {
    expect(parseSourcePaneLayout(null)).toEqual(DEFAULT_SOURCE_PANE_LAYOUT);
    expect(parseSourcePaneLayout("not json")).toEqual(DEFAULT_SOURCE_PANE_LAYOUT);
    expect(
      parseSourcePaneLayout(JSON.stringify({ version: 0, panelHeight: 500, treeWidth: 250 }))
    ).toEqual(DEFAULT_SOURCE_PANE_LAYOUT);
  });

  it("round-trips only numeric UI dimensions", () => {
    const serialized = serializeSourcePaneLayout({ panelHeight: 611.4, treeWidth: 287.7 });
    expect(JSON.parse(serialized)).toEqual({
      version: SOURCE_PANE_PREFERENCE_VERSION,
      panelHeight: 611,
      treeWidth: 288
    });
    expect(parseSourcePaneLayout(serialized)).toEqual({ panelHeight: 611, treeWidth: 288 });
  });

  it("reads and writes the versioned local-storage entry without story data", () => {
    const values = new Map<string, string>();
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value)
    };
    writeSourcePaneLayout(storage, { panelHeight: 588, treeWidth: 276 });
    expect(readSourcePaneLayout(storage)).toEqual({ panelHeight: 588, treeWidth: 276 });
    expect(Array.from(values.values())[0]).not.toMatch(/project|scene|source_document/i);
  });

  it("clamps height to the visible viewport and width to the reader minimum", () => {
    const bounds = sourcePaneBounds({ viewportHeight: 900, panelTop: 180, containerWidth: 980 });
    expect(bounds).toEqual({
      minPanelHeight: 360,
      maxPanelHeight: 704,
      minTreeWidth: 200,
      maxTreeWidth: 610
    });
    expect(clampSourcePaneLayout({ panelHeight: 900, treeWidth: 900 }, bounds)).toEqual({
      panelHeight: 704,
      treeWidth: 610
    });
  });


  it("resets either separator to its clamped default", () => {
    const bounds = sourcePaneBounds({ viewportHeight: 620, panelTop: 100, containerWidth: 860 });
    expect(
      resetSourcePaneLayoutDimension({ panelHeight: 400, treeWidth: 220 }, "panelHeight", bounds)
    ).toEqual({ panelHeight: 504, treeWidth: 220 });
    expect(
      resetSourcePaneLayoutDimension({ panelHeight: 400, treeWidth: 220 }, "treeWidth", bounds)
    ).toEqual({ panelHeight: 400, treeWidth: 300 });
  });
});

describe("source pane keyboard separators", () => {
  it("uses orientation-specific arrows and supports Home/End", () => {
    expect(separatorKeyboardValue({ key: "ArrowDown", value: 500, min: 360, max: 700, orientation: "horizontal" })).toBe(516);
    expect(separatorKeyboardValue({ key: "ArrowLeft", value: 300, min: 200, max: 600, orientation: "vertical", largeStep: true })).toBe(252);
    expect(separatorKeyboardValue({ key: "Home", value: 500, min: 360, max: 700, orientation: "horizontal" })).toBe(360);
    expect(separatorKeyboardValue({ key: "End", value: 300, min: 200, max: 600, orientation: "vertical" })).toBe(600);
    expect(separatorKeyboardValue({ key: "ArrowRight", value: 500, min: 360, max: 700, orientation: "horizontal" })).toBeNull();
  });
});
