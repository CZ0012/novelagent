import { localizeGraphLabel, uiText } from "./localization";
import type { OutlineLanguagePatch } from "./outlineLanguage";

export function OutlineLanguagePreview({ patch }: { patch: OutlineLanguagePatch }) {
  const groups = new Map<string, typeof patch.changes>();
  for (const change of patch.changes) groups.set(change.node_id, [...(groups.get(change.node_id) ?? []), change]);
  return <section className="outline-language-review" aria-label={uiText.outlineLanguage.reviewTitle}>
    <h3>{uiText.outlineLanguage.reviewTitle}</h3>
    <p>{uiText.outlineLanguage.reviewHelp}</p>
    <p>{uiText.language.projectLanguageLabel}: {patch.output_language === "zh-CN" ? uiText.language.chinese : uiText.language.english}</p>
    {[...groups].map(([nodeId, changes], index) => <section key={nodeId}>
      <h4 title={nodeId}>{changes.find((change) => change.field === "title")?.before || `${localizeGraphLabel(changes[0].node_type)} ${index + 1}`}</h4>
      <table>
        <thead><tr><th>{uiText.outlineLanguage.field}</th><th>{uiText.outlineLanguage.before}</th><th>{uiText.outlineLanguage.after}</th></tr></thead>
        <tbody>{changes.map((change) => <tr key={change.field}>
          <th>{uiText.outlineLanguage.fields[change.field as keyof typeof uiText.outlineLanguage.fields]}</th>
          <td>{change.before || uiText.common.none}</td><td>{change.after}</td>
        </tr>)}</tbody>
      </table>
    </section>)}
  </section>;
}
