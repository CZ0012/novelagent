import { zhCN } from "./zh-CN";
import { enUS } from "./en-US";
import type { LocaleCatalog } from "./schema";

export type AppLocale = "zh-CN" | "en-US";
export const UI_LOCALE_STORAGE_KEY = "storygraph.ui_locale.v1";
export const SUPPORTED_UI_LOCALES: readonly AppLocale[] = ["zh-CN", "en-US"];

const catalogs: Record<AppLocale, LocaleCatalog> = {
  "zh-CN": zhCN,
  "en-US": enUS
};

let activeLocale: LocaleCatalog = zhCN;

export let APP_LOCALE = activeLocale.locale;
export let appText = activeLocale.app;
export let uiText = activeLocale.ui;
export let localizedTerms = activeLocale.terms;
export let permissionLabels = activeLocale.permissions.labels;
export let defaultPermissionDescriptions = activeLocale.permissions.descriptions;
export let proposalTypeLabels = activeLocale.proposalTypes;
export let proposalStatusLabels = activeLocale.proposalStatuses;
export let stepLabels = activeLocale.steps;
export let reviewActionLabels = activeLocale.reviewActions;

export function normalizeAppLocale(value: string | null | undefined): AppLocale {
  return value === "en-US" ? "en-US" : "zh-CN";
}

export function getLocaleCatalog(locale: string | null | undefined): LocaleCatalog {
  return catalogs[normalizeAppLocale(locale)];
}

export function activateLocale(locale: AppLocale): LocaleCatalog {
  activeLocale = catalogs[locale];
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
