import type { ReactNode } from "react";
import { uiText } from "./localization";
/** Graph data stays complete; its optional display cannot consume the inspector's main row. */
export function InspectorGraphDisclosure({ children }: { children: ReactNode }) {
  return <details className="inspector-graph-disclosure"><summary>{uiText.graph.title}</summary><div className="inspector-graph-scroll">{children}</div></details>;
}
