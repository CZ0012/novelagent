import { uiText } from "./localization";
import type { AuthoringStructurePreview } from "./authoring";

export function AuthoringStructure({ preview, names = {} }: { preview: AuthoringStructurePreview; names?: Record<string, string> }) {
  const t = uiText.authoring;
  const fields = { title: t.sceneCards, name: t.generalName, chapter_title: t.structureFields.chapter_title, timeline_position: t.structureFields.timeline_position, goal: t.structureFields.goal, conflict: t.structureFields.conflict, emotional_turn: t.structureFields.emotional_turn, outcome: t.outcome, target_length: t.structureFields.target_length, summary: t.authorSummary };
  const labels: Record<string, string> = { ...fields, ...t.structureExtraFields, ...uiText.writerVisibility.styleFields };
  const referencedNames = { ...Object.fromEntries((preview.reuse ?? []).map(node => [node.id, node.name ?? node.public_name ?? node.id])), ...names };
  function valueText(value: unknown): string {
    if (value === undefined || value === null || value === "") return uiText.common.none;
    if (typeof value === "boolean") return value ? t.enabled : t.disabled;
    if (Array.isArray(value)) return value.length ? value.map(valueText).join("；") : uiText.common.none;
    if (typeof value === "object") return Object.entries(value).map(([key, item]) => `${labels[key] ?? key}: ${valueText(item)}`).join("；");
    return typeof value === "string" ? referencedNames[value] ?? value : String(value);
  }
  function gapText(field: string) { return field.startsWith("character_mapping:") ? t.mappingGap : field === "location_mapping" ? t.locationGap : t.structureFields[field as keyof typeof t.structureFields] ?? field; }
  return <section aria-label={preview.operation === "update" ? t.structureUpdatePreview : t.structurePreview}><p>{preview.operation === "update" ? t.structureUpdateBoundary : t.structureBoundary}</p>{preview.gaps.length > 0 && <div role="status"><p>{t.structureGaps}</p><ul>{preview.gaps.map(field => <li key={field}>{gapText(field)}</li>)}</ul></div>}
    {(preview.reuse?.length ?? 0) > 0 && <section><h4>{t.structureReuse}</h4>{preview.reuse?.map(node => <p key={node.id}>{t.structureKinds[node.type as keyof typeof t.structureKinds] ?? node.type}: {node.name ?? node.public_name}{node.public_name && node.public_name !== node.name ? ` · ${uiText.writerVisibility.publicName}: ${node.public_name}` : ""}</p>)}</section>}
    {preview.operation === "update" && <section><h4>{String(preview.current_scene?.properties.title ?? "")}</h4>{!preview.changes?.length && <p>{t.structureNoChanges}</p>}{preview.changes?.map(change => <article className="authoring-card" key={change.field}><h5>{labels[change.field] ?? change.field}</h5><dl><dt>{t.before}</dt><dd>{valueText(change.before)}</dd><dt>{t.after}</dt><dd>{valueText(change.after)}</dd></dl></article>)}</section>}
    {preview.nodes.map(node => <article key={node.id} className="authoring-card"><h4>{t.structureKinds[node.type as keyof typeof t.structureKinds] ?? node.type} · {String(node.properties.name ?? node.properties.title ?? "")}</h4><dl>{Object.entries(fields).filter(([key]) => node.properties[key] !== undefined && node.properties[key] !== "").map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{String(node.properties[key])}</dd></div>)}</dl>{node.type === "Scene" && Boolean(node.properties.style_constraints) && <><h5>{uiText.writerVisibility.styleSummary}</h5><dl>{Object.entries(node.properties.style_constraints as Record<string, unknown>).filter(([, value]) => value !== null && value !== "" && (!Array.isArray(value) || value.length > 0)).map(([key, value]) => <div key={key}><dt>{uiText.writerVisibility.styleFields[key as keyof typeof uiText.writerVisibility.styleFields] ?? key}</dt><dd>{Array.isArray(value) ? value.join("；") : String(value)}</dd></div>)}</dl></>}</article>)}
  </section>;
}
