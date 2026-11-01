import type { VisibilitySpec } from "./WriterVisibilityPanel";
import type { AuthoringReaderRecord } from "./authoring";
import { uiText } from "./localization";

const styleFields = ["pov", "tense", "tone", "sentence_rhythm", "diction", "dialogue_style", "rubric", "banned_patterns"] as const;

export function AuthoringWriterPolicy({ policy }: { policy: VisibilitySpec }) {
  const t = uiText.writerVisibility, a = uiText.authoring;
  const name = (id: string | null) => policy.characters.find(character => character.character_id === id)?.public_name ?? id;
  const styleKeys = [...new Set<string>([...styleFields, ...Object.keys(policy.writer_style)])];
  function content(value: unknown) {
    if (Array.isArray(value)) return value.length ? <ul>{value.map((item, index) => <li key={index}>{String(item)}</li>)}</ul> : uiText.common.none;
    return value === null || value === undefined || value === "" ? uiText.common.none : String(value);
  }
  return <details open className="authoring-writer-policy"><summary>{t.title}</summary><p>{a.writerPolicyReviewHelp}</p>
    <dl><dt>{t.mode}</dt><dd>{t[policy.access_mode]}</dd><dt>{t.allowedPlan}</dt><dd>{policy.surface_plan.text ?? t.currentSummary}</dd></dl>
    <h5>{t.cast}</h5>{policy.characters.length ? <ul>{policy.characters.map(character => <li key={character.character_id}>{character.public_name}{character.allow_offstage_name ? ` · ${t.offstage}` : ""}</li>)}</ul> : <p>{uiText.common.none}</p>}
    <h5>{t.claims}</h5>{policy.visible_claims.length ? policy.visible_claims.map((claim, index) => <article key={index}><strong>{t.presentations[claim.presentation]} · {claim.phase === "entry" ? a.entry : a.acquired}{claim.character_id ? ` · ${name(claim.character_id)}` : ""}</strong><p>{claim.text}</p></article>) : <p>{uiText.common.none}</p>}
    <h5>{t.styleSummary}</h5><dl><dt>{t.styleOrigin}</dt><dd>{t.styleOrigins[policy.writer_style_origin]}</dd>{styleKeys.map(key => <div key={key}><dt>{t.styleFields[key as keyof typeof t.styleFields] ?? key}</dt><dd>{content(policy.writer_style[key])}</dd></div>)}</dl>
    <section><h5>{a.privatePolicyContext}</h5><p>{t.readerHelp}</p><h6>{a.reader}</h6>{policy.reader_presented.length ? policy.reader_presented.map((value, index) => { const record = value as AuthoringReaderRecord; return <blockquote key={index}><strong>{a.readerPresentation[record.presentation] ?? record.presentation}</strong><p>{record.expected_text}</p><small>{record.draft_id} v{record.version} · {record.start}–{record.end}</small></blockquote>; }) : <p>{uiText.common.none}</p>}<dl><dt>{t.inference}</dt><dd>{policy.expected_reader_inference || uiText.common.none}</dd></dl></section>
  </details>;
}
