import { diffArrays } from "diff";

export type ManuscriptDiffPart = { kind: "equal" | "removed" | "added"; text: string };
export type ManuscriptDiffBlock = { kind: "equal" | "changed" | "removed" | "added"; parts: ManuscriptDiffPart[] };
export type ManuscriptDiffResult = { blocks: ManuscriptDiffBlock[]; changed: boolean; simplified: boolean };

// Linear tokenization plus explicitly bounded alignment: a large rewrite must
// never attempt the unbounded quadratic comparison of an entire manuscript.
const MAX_LINES = 4000;
const MAX_INLINE_CHARS = 12000;
const MAX_INLINE_TOKENS = 3000;
const MAX_TOTAL_INLINE_TOKENS = 20000;
const MAX_INLINE_GROUPS = 64;
const TIME_BUDGET_MS = 60;

function append(parts: ManuscriptDiffPart[], kind: ManuscriptDiffPart["kind"], text: string) {
  if (!text) return;
  const last = parts[parts.length - 1];
  if (last?.kind === kind) last.text += text;
  else parts.push({ kind, text });
}

function block(parts: ManuscriptDiffPart[]): ManuscriptDiffBlock {
  const removed = parts.some((part) => part.kind === "removed");
  const added = parts.some((part) => part.kind === "added");
  return { kind: removed && added ? "changed" : removed ? "removed" : added ? "added" : "equal", parts };
}

/** Preserve line endings and empty paragraphs, including a final newline. */
function lines(text: string): string[] {
  return text.match(/[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+$/g) ?? [];
}

/** English words stay whole; Han characters can align inside unspaced prose.
 * Unicode mode keeps supplementary characters intact. No whitespace is lost. */
function proseTokens(text: string): string[] {
  return text.match(/\r\n|[\r\n]|[^\S\r\n]+|[\p{Script=Latin}\p{N}\p{M}_]+(?:['’][\p{Script=Latin}\p{N}\p{M}_]+)*|[\s\S]/gu) ?? [];
}

function splitsBoundary(text: string, index: number): boolean {
  const previous = text.charCodeAt(index - 1);
  const next = text.charCodeAt(index);
  return (previous >= 0xd800 && previous <= 0xdbff && next >= 0xdc00 && next <= 0xdfff)
    || (previous === 13 && next === 10);
}

/** A coarse fallback is still lossless. Common edges remain visible, so a
 * long continuation does not mark the complete original as deleted. */
function coarse(before: string, after: string): ManuscriptDiffPart[] {
  let prefix = 0;
  while (prefix < before.length && prefix < after.length && before[prefix] === after[prefix]) prefix++;
  while (prefix && (splitsBoundary(before, prefix) || splitsBoundary(after, prefix))) prefix--;
  let suffix = 0;
  while (suffix < before.length - prefix && suffix < after.length - prefix
    && before[before.length - suffix - 1] === after[after.length - suffix - 1]) suffix++;
  while (suffix && (splitsBoundary(before, before.length - suffix) || splitsBoundary(after, after.length - suffix))) suffix--;
  const parts: ManuscriptDiffPart[] = [];
  append(parts, "equal", before.slice(0, prefix));
  append(parts, "removed", before.slice(prefix, before.length - suffix));
  append(parts, "added", after.slice(prefix, after.length - suffix));
  if (suffix) append(parts, "equal", before.slice(before.length - suffix));
  return parts;
}

/** Pure, display-only comparison. Callers must supply the exact recorded Draft
 * baseline; this function neither resolves a version nor normalizes either text. */
export function buildManuscriptDiff(before: string, after: string): ManuscriptDiffResult {
  if (before === after) return { blocks: before ? [block([{ kind: "equal", text: before }])] : [], changed: false, simplified: false };
  if (!before || !after) return { blocks: [block([{ kind: before ? "removed" : "added", text: before || after }])], changed: true, simplified: false };

  const deadline = Date.now() + TIME_BUDGET_MS;
  const beforeLines = lines(before);
  const afterLines = lines(after);
  const alignment = beforeLines.length + afterLines.length <= MAX_LINES
    ? diffArrays(beforeLines, afterLines, { maxEditLength: 256, timeout: Math.max(0, deadline - Date.now()) })
    : undefined;
  if (!alignment) return { blocks: [block(coarse(before, after))], changed: true, simplified: true };

  const blocks: ManuscriptDiffBlock[] = [];
  let removed = "";
  let added = "";
  let simplified = false;
  let inlineGroups = 0;
  let totalTokens = 0;
  const flush = () => {
    if (!removed && !added) return;
    if (!removed || !added) {
      blocks.push(block([{ kind: removed ? "removed" : "added", text: removed || added }]));
    } else {
      let parts: ManuscriptDiffPart[] | undefined;
      if (removed.length + added.length <= MAX_INLINE_CHARS && ++inlineGroups <= MAX_INLINE_GROUPS && Date.now() < deadline) {
        const left = proseTokens(removed);
        const right = proseTokens(added);
        const count = left.length + right.length;
        totalTokens += count;
        if (count <= MAX_INLINE_TOKENS && totalTokens <= MAX_TOTAL_INLINE_TOKENS) {
          const changes = diffArrays(left, right, { maxEditLength: 128, timeout: Math.max(0, deadline - Date.now()) });
          if (changes) {
            parts = [];
            for (const change of changes) append(parts, change.removed ? "removed" : change.added ? "added" : "equal", change.value.join(""));
          }
        }
      }
      if (!parts) { parts = coarse(removed, added); simplified = true; }
      blocks.push(block(parts));
    }
    removed = "";
    added = "";
  };
  for (const change of alignment) {
    if (change.removed) removed += change.value.join("");
    else if (change.added) added += change.value.join("");
    else {
      flush();
      blocks.push(block([{ kind: "equal", text: change.value.join("") }]));
    }
  }
  flush();
  return { blocks, changed: true, simplified };
}
