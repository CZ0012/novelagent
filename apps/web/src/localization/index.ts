import type { LocaleCatalog } from "./schema";

export const UI_LOCALE_STORAGE_KEY = "storygraph.ui_locale.v1";
// Add a catalog and one registry entry to introduce another display language.
// The type-only schema import never includes the reference catalog at runtime.
export const localeRegistry = {
  "zh-CN": { label: "简体中文", load: () => import("./zh-CN").then((module) => module.zhCN) },
  "en-US": { label: "English", load: () => import("./en-US").then((module) => module.enUS) }
};
export type AppLocale = keyof typeof localeRegistry;
export const SUPPORTED_UI_LOCALES = Object.keys(localeRegistry) as AppLocale[];
const catalogs = new Map<AppLocale, Promise<LocaleCatalog>>();

// Vite can reevaluate this module while React preserves the mounted app. Keep
// the last complete catalog available during that transition; fresh launches
// still await the asynchronous bootstrap in main.tsx.
let activeLocale = import.meta.hot?.data.activeLocale as LocaleCatalog;
if (import.meta.hot) {
  import.meta.hot.dispose((data) => { data.activeLocale = activeLocale; });
}

export let APP_LOCALE: string = activeLocale?.locale;
export let appText: LocaleCatalog["app"] = activeLocale?.app;
export let uiText: LocaleCatalog["ui"] = activeLocale?.ui;
export let localizedTerms: LocaleCatalog["terms"] = activeLocale?.terms;
export let permissionLabels: LocaleCatalog["permissions"]["labels"] = activeLocale?.permissions.labels;
export let defaultPermissionDescriptions: LocaleCatalog["permissions"]["descriptions"] = activeLocale?.permissions.descriptions;
export let proposalTypeLabels: LocaleCatalog["proposalTypes"] = activeLocale?.proposalTypes;
export let proposalStatusLabels: LocaleCatalog["proposalStatuses"] = activeLocale?.proposalStatuses;
export let stepLabels: LocaleCatalog["steps"] = activeLocale?.steps;
export let reviewActionLabels: LocaleCatalog["reviewActions"] = activeLocale?.reviewActions;

export function normalizeAppLocale(value: string | null | undefined): AppLocale {
  return value && Object.prototype.hasOwnProperty.call(localeRegistry, value) ? value as AppLocale : "zh-CN";
}

export function loadLocaleCatalog(locale: string | null | undefined): Promise<LocaleCatalog> {
  const key = normalizeAppLocale(locale);
  let pending = catalogs.get(key);
  if (!pending) {
    pending = localeRegistry[key].load().catch((error) => {
      catalogs.delete(key);
      throw error;
    });
    catalogs.set(key, pending);
  }
  return pending;
}

export async function activateLocale(locale: AppLocale): Promise<LocaleCatalog> {
  activeLocale = await loadLocaleCatalog(locale);
  APP_LOCALE = activeLocale.locale;
  appText = activeLocale.app;
  uiText = activeLocale.ui;
  localizedTerms = activeLocale.terms;
  permissionLabels = activeLocale.permissions.labels;
  defaultPermissionDescriptions = activeLocale.permissions.descriptions;
  proposalTypeLabels = activeLocale.proposalTypes;
  proposalStatusLabels = activeLocale.proposalStatuses;
  stepLabels = activeLocale.steps;
  reviewActionLabels = activeLocale.reviewActions;
  return activeLocale;
}

export function localizeSystemValue(value: string | null | undefined): string {
  if (!value) return "";
  return activeLocale.demoText[value as keyof typeof activeLocale.demoText] ?? value;
}

export function localizeStatus(value: string | null | undefined): string {
  if (!value) return "";
  return activeLocale.statuses[value as keyof typeof activeLocale.statuses] ?? value;
}

export function formatStatus(status: string | null | undefined): string {
  if (!status) return uiText.common.none;
  return localizeStatus(status);
}

export function formatSeverity(severity: string): string {
  return activeLocale.severities[severity as keyof typeof activeLocale.severities] ?? severity;
}

export function formatDimension(dimension: string): string {
  return activeLocale.dimensions[dimension as keyof typeof activeLocale.dimensions] ?? dimension;
}

export function formatIssueType(issueType: string): string {
  return activeLocale.issueTypes[issueType as keyof typeof activeLocale.issueTypes] ?? issueType;
}

export function formatKnownMessage(message: string): string {
  return activeLocale.knownMessages[message as keyof typeof activeLocale.knownMessages] ?? message;
}

export function formatRefKind(kind: string): string {
  return activeLocale.refKinds[kind as keyof typeof activeLocale.refKinds] ?? kind;
}

export function formatProvenanceMethod(method: string | null | undefined): string {
  if (!method) return activeLocale.provenanceMethods.manual;
  return (
    activeLocale.provenanceMethods[method as keyof typeof activeLocale.provenanceMethods] ?? method
  );
}
