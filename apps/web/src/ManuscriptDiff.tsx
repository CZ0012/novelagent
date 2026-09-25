import { Fragment, useId, useMemo } from "react";
import { buildManuscriptDiff, type ManuscriptDiffPart } from "./manuscriptDiffModel";
import "./ManuscriptDiff.css";

export type ManuscriptDiffLabels = {
  title: string;
  added: string;
  removed: string;
  unchanged: string;
  noChanges: string;
  simplified: string;
  lineBreak: string;
};

export type ManuscriptDiffProps = { before: string; after: string; labels: ManuscriptDiffLabels };

function ChangedText({ text, lineBreak }: { text: string; lineBreak: string }) {
  return <>{text.split(/(\r\n|\r|\n)/).map((part, index) => /^(?:\r\n|\r|\n)$/.test(part)
    ? <Fragment key={index}><span className="manuscript-diff-newline" aria-hidden="true">↵</span><span className="manuscript-diff-sr"> {lineBreak} </span>{part}</Fragment>
    : <Fragment key={index}>{part}</Fragment>)}</>;
}

function Part({ part, labels }: { part: ManuscriptDiffPart; labels: ManuscriptDiffLabels }) {
  if (part.kind === "equal") return <>{part.text}</>;
  const contents = <>
    <span className="manuscript-diff-sign" aria-hidden="true">{part.kind === "removed" ? "−" : "+"}</span>
    <span className="manuscript-diff-sr">{part.kind === "removed" ? labels.removed : labels.added}: </span>
    <ChangedText text={part.text} lineBreak={labels.lineBreak} />
  </>;
  return part.kind === "removed" ? <del>{contents}</del> : <ins>{contents}</ins>;
}

/** Prose comparison only: adoption/review actions stay in the parent workflow. */
export function ManuscriptDiff({ before, after, labels }: ManuscriptDiffProps) {
  const titleId = useId();
  const result = useMemo(() => buildManuscriptDiff(before, after), [before, after]);
  return <section className="manuscript-diff" aria-labelledby={titleId}>
    <div className="manuscript-diff-heading">
      <h4 id={titleId}>{labels.title}</h4>
      <div className="manuscript-diff-legend">
        <span className="manuscript-diff-removed"><span aria-hidden="true">− </span>{labels.removed}</span>
        <span className="manuscript-diff-added"><span aria-hidden="true">+ </span>{labels.added}</span>
        <span>{labels.unchanged}</span>
      </div>
    </div>
    {!result.changed && <p className="manuscript-diff-notice">{labels.noChanges}</p>}
    {result.simplified && <p className="manuscript-diff-notice">{labels.simplified}</p>}
    {result.blocks.length > 0 && <div className="manuscript-diff-prose" tabIndex={0} role="region" aria-label={labels.title}>
      {result.blocks.map((item, index) => <p className={`manuscript-diff-block ${item.kind}`} key={index}>
        {item.parts.map((part, partIndex) => <Part key={partIndex} part={part} labels={labels} />)}
      </p>)}
    </div>}
  </section>;
}
