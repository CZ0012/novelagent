import { zhCN } from "./zh-CN";

const activeLocale = zhCN;

export const APP_LOCALE = activeLocale.locale;
export const appText = activeLocale.app;
export const uiText = activeLocale.ui;
export const localizedTerms = activeLocale.terms;
export const permissionLabels = activeLocale.permissions.labels;
export const defaultPermissionDescriptions = activeLocale.permissions.descriptions;
export const proposalTypeLabels = activeLocale.proposalTypes;
export const proposalStatusLabels = activeLocale.proposalStatuses;
export const stepLabels = activeLocale.steps;
export const reviewActionLabels = activeLocale.reviewActions;

export function localizeText(value: string | null | undefined): string {
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
