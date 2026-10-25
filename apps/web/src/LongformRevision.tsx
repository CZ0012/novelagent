import { useState } from "react";
import { uiText } from "./localization";
export type LongformRevisionMode = "full" | "targeted";
export function LongformRevision({ applied, disabled, modelLabel, onRevise }: { applied: boolean; disabled: boolean; modelLabel: string; onRevise: (instruction: string, mode: LongformRevisionMode) => void }) {
  const [instruction, setInstruction] = useState("");
  const [mode, setMode] = useState<LongformRevisionMode>("targeted");
  const t = uiText.planning;
  if (applied) return <p className="proposal-inline-warning">{t.appliedRevisionLimit}</p>;
  return <details className="longform-revision"><summary>{t.revise}</summary><p>{t.reviseHelp}</p><small>{modelLabel}</small><label>{t.revisionMode}<select disabled={disabled} value={mode} onChange={(event) => setMode(event.target.value as LongformRevisionMode)}><option value="targeted">{t.targetedRevision}</option><option value="full">{t.fullRevision}</option></select></label>{mode === "targeted" && <p>{t.targetedRevisionHelp}</p>}<label>{t.revisionInstruction}<textarea maxLength={12000} rows={4} value={instruction} disabled={disabled} onChange={(event) => setInstruction(event.target.value)} /></label><button type="button" disabled={disabled || !instruction.trim()} onClick={() => onRevise(instruction, mode)}>{t.revise}</button></details>;
}
