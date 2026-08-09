export const SOURCE_PANE_PREFERENCE_VERSION = 1 as const;
export const SOURCE_PANE_STORAGE_KEY = "storygraph.ui.source-pane.v1";
export const SOURCE_PANE_STACK_BREAKPOINT_PX = 1180;
export const SOURCE_PANE_HANDLE_SIZE_PX = 10;
export const SOURCE_PANE_MIN_HEIGHT_PX = 360;
export const SOURCE_PANE_MIN_TREE_WIDTH_PX = 200;
export const SOURCE_PANE_MIN_READER_WIDTH_PX = 360;

export type SourcePaneLayout = {
  panelHeight: number;
  treeWidth: number;
};

export type SourcePaneBounds = {
  minPanelHeight: number;
  maxPanelHeight: number;
  minTreeWidth: number;
  maxTreeWidth: number;
};

export type SourcePaneStorage = {
  getItem: (key: string) => string | null;
  setItem: (key: string, value: string) => void;
};

export const DEFAULT_SOURCE_PANE_LAYOUT: SourcePaneLayout = {
  panelHeight: 640,
  treeWidth: 300
};

type StoredSourcePaneLayout = SourcePaneLayout & {
  version: typeof SOURCE_PANE_PREFERENCE_VERSION;
};

export function sourcePaneBounds({
  viewportHeight,
  panelTop,
  containerWidth
}: {
  viewportHeight: number;
  panelTop: number;
  containerWidth: number;
}): SourcePaneBounds {
  const availableHeight = Math.floor(viewportHeight - Math.max(0, panelTop) - 16);
  const availableTreeWidth = Math.floor(
    containerWidth - SOURCE_PANE_MIN_READER_WIDTH_PX - SOURCE_PANE_HANDLE_SIZE_PX
  );
  return {
    minPanelHeight: SOURCE_PANE_MIN_HEIGHT_PX,
    maxPanelHeight: Math.max(SOURCE_PANE_MIN_HEIGHT_PX, availableHeight),
    minTreeWidth: SOURCE_PANE_MIN_TREE_WIDTH_PX,
    maxTreeWidth: Math.max(SOURCE_PANE_MIN_TREE_WIDTH_PX, availableTreeWidth)
  };
}

export function clampSourcePaneLayout(
  layout: SourcePaneLayout,
  bounds: SourcePaneBounds
): SourcePaneLayout {
  return {
    panelHeight: clamp(layout.panelHeight, bounds.minPanelHeight, bounds.maxPanelHeight),
    treeWidth: clamp(layout.treeWidth, bounds.minTreeWidth, bounds.maxTreeWidth)
  };
}

export function parseSourcePaneLayout(value: string | null): SourcePaneLayout {
  if (!value) return { ...DEFAULT_SOURCE_PANE_LAYOUT };
  try {
    const parsed = JSON.parse(value) as Partial<StoredSourcePaneLayout>;
    if (
      parsed.version !== SOURCE_PANE_PREFERENCE_VERSION ||
      !isFiniteNumber(parsed.panelHeight) ||
      !isFiniteNumber(parsed.treeWidth)
    ) {
      return { ...DEFAULT_SOURCE_PANE_LAYOUT };
    }
    return {
      panelHeight: Math.round(parsed.panelHeight),
      treeWidth: Math.round(parsed.treeWidth)
    };
  } catch {
    return { ...DEFAULT_SOURCE_PANE_LAYOUT };
  }
}

export function serializeSourcePaneLayout(layout: SourcePaneLayout): string {
  const stored: StoredSourcePaneLayout = {
    version: SOURCE_PANE_PREFERENCE_VERSION,
    panelHeight: Math.round(layout.panelHeight),
    treeWidth: Math.round(layout.treeWidth)
  };
  return JSON.stringify(stored);
}

export function readSourcePaneLayout(storage: SourcePaneStorage): SourcePaneLayout {
  return parseSourcePaneLayout(storage.getItem(SOURCE_PANE_STORAGE_KEY));
}

export function writeSourcePaneLayout(
  storage: SourcePaneStorage,
  layout: SourcePaneLayout
): void {
  storage.setItem(SOURCE_PANE_STORAGE_KEY, serializeSourcePaneLayout(layout));
}

export function resetSourcePaneLayoutDimension(
  layout: SourcePaneLayout,
  dimension: keyof SourcePaneLayout,
  bounds: SourcePaneBounds
): SourcePaneLayout {
  return clampSourcePaneLayout(
    { ...layout, [dimension]: DEFAULT_SOURCE_PANE_LAYOUT[dimension] },
    bounds
  );
}

export function separatorKeyboardValue({
  key,
  value,
  min,
  max,
  orientation,
  largeStep = false
}: {
  key: string;
  value: number;
  min: number;
  max: number;
  orientation: "horizontal" | "vertical";
  largeStep?: boolean;
}): number | null {
  if (key === "Home") return min;
  if (key === "End") return max;
  const step = largeStep ? 48 : 16;
  if (orientation === "horizontal") {
    if (key === "ArrowUp") return clamp(value - step, min, max);
    if (key === "ArrowDown") return clamp(value + step, min, max);
  } else {
    if (key === "ArrowLeft") return clamp(value - step, min, max);
    if (key === "ArrowRight") return clamp(value + step, min, max);
  }
  return null;
}

function clamp(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  return Math.min(max, Math.max(min, Math.round(value)));
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}
