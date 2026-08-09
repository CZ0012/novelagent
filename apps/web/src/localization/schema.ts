import type { zhCN } from "./zh-CN";

type WidenCatalog<T> = T extends (...args: infer Args) => string
  ? (...args: Args) => string
  : T extends string
    ? string
    : T extends Record<string, unknown>
      ? { [Key in keyof T]: WidenCatalog<T[Key]> }
      : T;

export type LocaleCatalog = WidenCatalog<typeof zhCN>;
