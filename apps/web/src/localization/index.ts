import { zhCN } from "./zh-CN";

const activeLocale = zhCN;

export function localizeText(value: string | null | undefined): string {
  if (!value) return "";
  return activeLocale.demoText[value as keyof typeof activeLocale.demoText] ?? value;
}

export function localizeStatus(value: string | null | undefined): string {
  if (!value) return "";
  return activeLocale.statuses[value as keyof typeof activeLocale.statuses] ?? value;
}
