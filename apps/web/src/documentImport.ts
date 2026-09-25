/** Local text extraction only. Never renders HTML, opens links, or executes RTF objects.
 * RTF grammar: Microsoft's RTF 1.x control-word/group rules; this is a bounded
 * plain-text subset, not a layout renderer. Unknown starred destinations are skipped.
 * https://learn.microsoft.com/en-us/previous-versions/office/developer/office2000/aa140277(v=office.10)
 */
export type DocumentMediaType = "text/plain" | "text/markdown" | "application/rtf" |
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
export type DocumentImportErrorCode = "empty_file" | "file_read_failed" | "invalid_docx" |
  "empty_text" | "rtf_invalid" | "rtf_unsupported_encoding" | "unsupported_text_encoding" |
  "file_too_large" | "text_too_large" | "crypto_unavailable" | "rtf_too_complex" |
  "docx_too_large" | "unsupported_format" | "temporary_file";
export type DocumentImportWarningCode = "rtf_text_only" | "rtf_omitted_destinations" | "docx_conversion_warnings";
export class DocumentImportError extends Error {
  constructor(readonly code: DocumentImportErrorCode) {
    super(`import_error:${code}`);
    this.name = "DocumentImportError";
  }
}
export type DocumentFile = Pick<File, "name" | "size" | "arrayBuffer">;
export type DocumentExtraction = {
  mediaType: DocumentMediaType;
  byteSize: number;
  checksumSha256: string;
  text: string | null;
  errorCode: DocumentImportErrorCode | null;
  warnings: DocumentImportWarningCode[];
};
export const DOCUMENT_IMPORT_LIMITS = Object.freeze({
  maxFileBytes: 20 * 1024 * 1024,
  maxTextCharacters: 2_000_000,
  maxRtfDepth: 128,
  maxDocxEntries: 2048,
  maxDocxExpandedBytes: 64 * 1024 * 1024,
  maxDocxDocumentBytes: 16 * 1024 * 1024
});

export function classifyDocumentFile(name: string):
  { kind: "supported"; mediaType: DocumentMediaType } | { kind: "temporary" | "unsupported" } {
  const base = name.replace(/\\/g, "/").split("/").pop()?.toLowerCase() ?? "";
  if (base.startsWith("~$")) return { kind: "temporary" };
  if (base.endsWith(".txt")) return { kind: "supported", mediaType: "text/plain" };
  if (/\.(md|markdown)$/.test(base)) return { kind: "supported", mediaType: "text/markdown" };
  if (base.endsWith(".rtf")) return { kind: "supported", mediaType: "application/rtf" };
  if (base.endsWith(".docx")) return { kind: "supported", mediaType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" };
  return { kind: "unsupported" };
}

function fail(code: DocumentImportErrorCode): never { throw new DocumentImportError(code); }
function assertTextBudget(text: string) {
  if (text.length > DOCUMENT_IMPORT_LIMITS.maxTextCharacters) fail("text_too_large");
}
function validUnicode(text: string): boolean {
  for (let i = 0; i < text.length; i++) {
    const unit = text.charCodeAt(i);
    if (unit >= 0xd800 && unit <= 0xdbff) {
      const next = text.charCodeAt(++i);
      if (!(next >= 0xdc00 && next <= 0xdfff)) return false;
    } else if (unit >= 0xdc00 && unit <= 0xdfff) return false;
  }
  return true;
}

/** Throws only before a trustworthy original-byte identity exists; parse failures
 * return a failed extraction so the caller can persist safe diagnostic metadata. */
export async function extractDocumentFile(file: DocumentFile): Promise<DocumentExtraction> {
  const format = classifyDocumentFile(file.name);
  if (format.kind !== "supported") fail(format.kind === "temporary" ? "temporary_file" : "unsupported_format");
  if (!Number.isSafeInteger(file.size) || file.size < 0) fail("file_read_failed");
  if (file.size > DOCUMENT_IMPORT_LIMITS.maxFileBytes) fail("file_too_large");
  let buffer: ArrayBuffer;
  try { buffer = await file.arrayBuffer(); } catch { return fail("file_read_failed"); }
  if (!(buffer instanceof ArrayBuffer) || buffer.byteLength !== file.size) fail("file_read_failed");
  if (!globalThis.crypto?.subtle) fail("crypto_unavailable");
  let digest: ArrayBuffer;
  try { digest = await crypto.subtle.digest("SHA-256", buffer); } catch { return fail("crypto_unavailable"); }
  const checksumSha256 = Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, "0")).join("");
  const result: DocumentExtraction = { mediaType: format.mediaType, byteSize: buffer.byteLength,
    checksumSha256, text: null, errorCode: null, warnings: [] };
  if (!buffer.byteLength) return { ...result, errorCode: "empty_file" };
  try {
    let text: string;
    if (format.mediaType === "application/rtf") {
      const parsed = extractRtfText(new Uint8Array(buffer));
      text = parsed.text;
      result.warnings = parsed.warnings;
    } else if (format.mediaType.includes("wordprocessingml")) {
      const parsed = await extractDocxText(buffer);
      text = parsed.text;
      result.warnings = parsed.warnings;
    } else {
      text = decodePlainText(new Uint8Array(buffer));
    }
    assertTextBudget(text);
    if (!text.replace(/^\uFEFF/, "").trim()) fail("empty_text");
    result.text = text;
  } catch (error) {
    if (!(error instanceof DocumentImportError)) throw error;
    result.errorCode = error.code;
    result.text = null;
  }
  return result;
}

export function decodePlainText(bytes: Uint8Array): string {
  // UTF-8 remains the default. BOM-marked UTF-16 is accepted; never guess GBK
  // for arbitrary invalid UTF-8, which can silently turn damaged input into prose.
  const encoding = bytes[0] === 0xff && bytes[1] === 0xfe ? "utf-16le" :
    bytes[0] === 0xfe && bytes[1] === 0xff ? "utf-16be" : "utf-8";
  try {
    const text = new TextDecoder(encoding, { fatal: true }).decode(bytes);
    if (!validUnicode(text) || text.includes("\0")) fail("unsupported_text_encoding");
    assertTextBudget(text);
    return text;
  } catch (error) {
    if (error instanceof DocumentImportError) throw error;
    return fail("unsupported_text_encoding");
  }
}

/** ZIP preflight bounds the existing Mammoth extractor before inflation. */
async function validateDocxZip(buffer: ArrayBuffer) {
  const bytes = new Uint8Array(buffer);
  const view = new DataView(buffer);
  if (bytes.length < 22 || view.getUint32(0, true) !== 0x04034b50) fail("invalid_docx");
  let end = -1;
  for (let i = bytes.length - 22; i >= Math.max(0, bytes.length - 22 - 65535); i--) {
    if (view.getUint32(i, true) === 0x06054b50 && i + 22 + view.getUint16(i + 20, true) === bytes.length) { end = i; break; }
  }
  if (end < 0 || view.getUint16(end + 4, true) || view.getUint16(end + 6, true)) fail("invalid_docx");
  const count = view.getUint16(end + 10, true);
  if (count !== view.getUint16(end + 8, true) || count === 0xffff) fail("invalid_docx");
  if (count > DOCUMENT_IMPORT_LIMITS.maxDocxEntries) fail("docx_too_large");
  const size = view.getUint32(end + 12, true);
  let offset = view.getUint32(end + 16, true);
  const directoryEnd = offset + size;
  if (directoryEnd !== end) fail("invalid_docx");
  let expanded = 0;
  const names = new Set<string>();
  for (let entry = 0; entry < count; entry++) {
    if (offset + 46 > directoryEnd || view.getUint32(offset, true) !== 0x02014b50) fail("invalid_docx");
    const flags = view.getUint16(offset + 8, true);
    const compression = view.getUint16(offset + 10, true);
    const compressedSize = view.getUint32(offset + 20, true);
    const uncompressedSize = view.getUint32(offset + 24, true);
    const nameLength = view.getUint16(offset + 28, true);
    const extraLength = view.getUint16(offset + 30, true);
    const commentLength = view.getUint16(offset + 32, true);
    const localOffset = view.getUint32(offset + 42, true);
    const next = offset + 46 + nameLength + extraLength + commentLength;
    if (next > directoryEnd || localOffset + 30 > directoryEnd ||
        view.getUint32(localOffset, true) !== 0x04034b50 || flags & 1 ||
        ![0, 8].includes(compression) || uncompressedSize === 0xffffffff) fail("invalid_docx");
    let name: string;
    const nameBytes = bytes.subarray(offset + 46, offset + 46 + nameLength);
    try { name = new TextDecoder("utf-8", { fatal: true }).decode(nameBytes); }
    catch { return fail("invalid_docx"); }
    // JSZip uses local names and Unicode path extras before normalizing paths.
    // Preflight and extraction must therefore see exactly the same namespace.
    const segments = name.replace(/\/$/, "").split("/");
    if (!name || /[\\:\x00-\x1f\x7f]/.test(name) ||
        segments.some((segment) => !segment || segment === "." || segment === "..") ||
        names.has(name) || names.has(name.endsWith("/") ? name.slice(0, -1) : name + "/")) fail("invalid_docx");
    names.add(name);
    expanded += uncompressedSize;
    if (expanded > DOCUMENT_IMPORT_LIMITS.maxDocxExpandedBytes ||
        name === "word/document.xml" && uncompressedSize > DOCUMENT_IMPORT_LIMITS.maxDocxDocumentBytes) fail("docx_too_large");
    const localNameLength = view.getUint16(localOffset + 26, true);
    const localExtraLength = view.getUint16(localOffset + 28, true);
    const dataStart = localOffset + 30 + localNameLength + localExtraLength;
    if (dataStart + compressedSize > directoryEnd ||
        view.getUint16(localOffset + 8, true) !== compression ||
        view.getUint16(localOffset + 6, true) !== flags || localNameLength !== nameLength ||
        !nameBytes.every((byte, index) => bytes[localOffset + 30 + index] === byte)) fail("invalid_docx");
    const validateExtras = (start: number, length: number) => {
      const extraEnd = start + length;
      while (start < extraEnd) {
        if (start + 4 > extraEnd) fail("invalid_docx");
        const kind = view.getUint16(start, true);
        const size = view.getUint16(start + 2, true);
        start += 4;
        if (start + size > extraEnd || kind === 0x0001) fail("invalid_docx"); // ZIP64 is unsupported.
        if (kind === 0x7075 && (size !== nameBytes.length + 5 || bytes[start] !== 1 ||
            !nameBytes.every((byte, index) => bytes[start + 5 + index] === byte))) fail("invalid_docx");
        start += size;
      }
    };
    validateExtras(offset + 46 + nameLength, extraLength);
    validateExtras(localOffset + 30 + localNameLength, localExtraLength);
    // Never trust the ZIP's claimed expanded size alone: a forged directory
    // must not let a tiny compressed file inflate without an actual byte cap.
    if (compression === 0) {
      if (compressedSize !== uncompressedSize) fail("invalid_docx");
    } else {
      try {
        const stream = new Blob([buffer.slice(dataStart, dataStart + compressedSize)]).stream()
          .pipeThrough(new DecompressionStream("deflate-raw" as CompressionFormat));
        const reader = stream.getReader();
        let actualSize = 0;
        try {
          for (;;) {
            const { value, done } = await reader.read();
            if (done) break;
            actualSize += value.length;
            if (actualSize > uncompressedSize) { await reader.cancel(); fail("invalid_docx"); }
          }
        } finally { reader.releaseLock(); }
        if (actualSize !== uncompressedSize) fail("invalid_docx");
      } catch (error) {
        if (error instanceof DocumentImportError) throw error;
        fail("invalid_docx");
      }
    }
    offset = next;
  }
  if (offset !== directoryEnd || !names.has("word/document.xml") || !names.has("[Content_Types].xml")) fail("invalid_docx");
}

export async function extractDocxText(buffer: ArrayBuffer): Promise<{ text: string; warnings: DocumentImportWarningCode[] }> {
  if (buffer.byteLength > DOCUMENT_IMPORT_LIMITS.maxFileBytes) fail("file_too_large");
  await validateDocxZip(buffer);
  try {
    type MammothApi = { extractRawText: (input: { arrayBuffer: ArrayBuffer }) =>
      Promise<{ value: string; messages: Array<{ message: string }> }> };
    const module = await import("mammoth/mammoth.browser");
    const mammoth = (module as unknown as { default?: MammothApi }).default ?? module as unknown as MammothApi;
    const result = await mammoth.extractRawText({ arrayBuffer: buffer });
    assertTextBudget(result.value);
    if (!validUnicode(result.value)) fail("invalid_docx");
    return { text: result.value, warnings: result.messages.length ? ["docx_conversion_warnings"] : [] };
  } catch (error) {
    if (error instanceof DocumentImportError) throw error;
    return fail("invalid_docx");
  }
}

// Font-table codepages override the document codepage for the selected run.
const CODEPAGES: Record<number, string> = {
  874: "windows-874", 932: "shift_jis", 936: "gbk", 949: "euc-kr", 950: "big5",
  1250: "windows-1250", 1251: "windows-1251", 1252: "windows-1252", 1253: "windows-1253",
  1254: "windows-1254", 1255: "windows-1255", 1256: "windows-1256", 1257: "windows-1257",
  1258: "windows-1258", 10000: "macintosh", 866: "ibm866", 20127: "ascii", 65001: "utf-8", 54936: "gb18030"
};
const CHARSETS: Record<number, number> = {
  77: 10000, 128: 932, 129: 949, 134: 936, 136: 950, 161: 1253, 162: 1254,
  163: 1258, 177: 1255, 178: 1256, 186: 1257, 204: 1251, 222: 874, 238: 1250, 255: 437
};
const OMIT_DESTINATIONS = new Set(("fonttbl colortbl stylesheet info pict object objdata objclass objname objalias objsect " +
  "objtime result datafield fldinst filetbl revtbl rsidtbl generator listtable listoverridetable listpicture " +
  "latentstyles themecolorschememapping colorschememapping xmlnstbl datastore datafield docvar userprops " +
  "header headerl headerr headerf footer footerl footerr footerf annotation atnauthor atndate atnid atnref " +
  "shp shpinst shprslt shpgrp nonshppict shppict background mmathPr mathprops uprhtml htmltag mhtmltag " +
  "bkmkstart bkmkend xe tc private password passwordhash file fname panose falt fontemb fontfile").split(" "));
const SYMBOLS: Record<string, string> = {
  par: "\n\n", line: "\n", tab: "\t", cell: "\t", row: "\n", nestcell: "\t", nestrow: "\n",
  page: "\n\n", sect: "\n\n", emdash: "—", endash: "–", bullet: "•", lquote: "‘", rquote: "’", ldblquote: "“", rdblquote: "”",
  emspace: "\u2003", enspace: "\u2002", qmspace: "\u2005"
};
type RtfState = { skip: boolean; hidden: boolean; deleted: boolean; codepage: number; font: number | null;
  fontTable: boolean; fontDefinition: number | null; uc: number; start: boolean; starred: boolean;
  uprChild: number | null; unicodeAlternative: boolean };

export function extractRtfText(bytes: Uint8Array): { text: string; warnings: DocumentImportWarningCode[] } {
  if (bytes.length > DOCUMENT_IMPORT_LIMITS.maxFileBytes) fail("file_too_large");
  let pos = bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf ? 3 : 0;
  while ([9, 10, 13, 32].includes(bytes[pos])) pos++;
  const head = String.fromCharCode(...bytes.subarray(pos, pos + 6));
  if (!/^\{\\rtf1(?:[^0-9]|$)/.test(head + String.fromCharCode(bytes[pos + 6] ?? 0))) fail("rtf_invalid");
  const rootStart = pos;
  const stack: RtfState[] = [];
  const fonts = new Map<number, { codepage?: number; charset?: number }>();
  let defaultFont: number | null = null;
  let state: RtfState = { skip: false, hidden: false, deleted: false, codepage: 1252, font: null,
    fontTable: false, fontDefinition: null, uc: 1, start: true, starred: false, uprChild: null, unicodeAlternative: false };
  let fallback = 0;
  let pendingBytes: number[] = [];
  const chunks: string[] = [];
  let outputLength = 0;
  let omitted = false;
  let closed = false;
  const emit = (text: string) => {
    if (state.skip || state.hidden || state.deleted) return;
    outputLength += text.length;
    if (outputLength > DOCUMENT_IMPORT_LIMITS.maxTextCharacters) fail("text_too_large");
    chunks.push(text);
  };
  const activeCodepage = () => {
    const font = fonts.get(state.font ?? defaultFont ?? -1);
    if (font?.codepage !== undefined) return font.codepage;
    if (font?.charset !== undefined && ![0, 1].includes(font.charset)) return CHARSETS[font.charset] ?? -1;
    return state.codepage;
  };
  const flush = () => {
    if (!pendingBytes.length) return;
    if (!state.skip && !state.hidden && !state.deleted) {
      const codepage = activeCodepage();
      const label = CODEPAGES[codepage];
      if (!label) fail("rtf_unsupported_encoding");
      try { emit(new TextDecoder(label, { fatal: true }).decode(new Uint8Array(pendingBytes))); }
      catch (error) { if (error instanceof DocumentImportError) throw error; fail("rtf_invalid"); }
    }
    pendingBytes = [];
  };
  const addByte = (byte: number) => {
    if (fallback > 0) { fallback--; return; }
    if (!state.skip && !state.hidden && !state.deleted) pendingBytes.push(byte);
    // Do not split a multibyte codepage sequence at a chunk boundary.
    if (pendingBytes.length > DOCUMENT_IMPORT_LIMITS.maxTextCharacters * 4) fail("text_too_large");
  };
  while (pos < bytes.length) {
    const byte = bytes[pos++];
    if (closed) {
      if (![9, 10, 13, 32].includes(byte)) fail("rtf_invalid");
      continue;
    }
    if (byte === 123) {
      flush(); fallback = 0;
      if (stack.length >= DOCUMENT_IMPORT_LIMITS.maxRtfDepth) fail("rtf_too_complex");
      let skip = state.skip;
      let unicodeAlternative = false;
      if (state.uprChild !== null) {
        state.uprChild++;
        if (state.uprChild === 1) skip = true;
        else if (state.uprChild === 2) unicodeAlternative = true;
        else fail("rtf_invalid");
      }
      stack.push(state);
      state = { ...state, skip, start: true, starred: false, uprChild: null, unicodeAlternative };
      continue;
    }
    if (byte === 125) {
      flush(); fallback = 0;
      if (!stack.length || state.uprChild !== null && state.uprChild !== 2) fail("rtf_invalid");
      state = stack.pop()!;
      if (!stack.length) closed = true;
      continue;
    }
    if (!stack.length || pos === rootStart + 1) fail("rtf_invalid");
    if (byte === 10 || byte === 13) continue; // RTF physical line wrapping is not manuscript text.
    if (byte !== 92) {
      if (byte < 32 && byte !== 9) fail("rtf_invalid");
      state.start = false;
      addByte(byte);
      continue;
    }
    if (pos >= bytes.length) fail("rtf_invalid");
    const next = bytes[pos++];
    if (next === 39) {
      if (pos + 2 > bytes.length) fail("rtf_invalid");
      const hex = String.fromCharCode(bytes[pos++], bytes[pos++]);
      if (!/^[0-9a-fA-F]{2}$/.test(hex)) fail("rtf_invalid");
      state.start = false; addByte(parseInt(hex, 16)); continue;
    }
    if ([92, 123, 125].includes(next)) { state.start = false; addByte(next); continue; }
    flush();
    if (!((next >= 65 && next <= 90) || (next >= 97 && next <= 122))) {
      if (next === 42 && state.start) { state.starred = true; continue; }
      const symbol = next === 126 ? "\u00a0" : next === 95 ? "\u2011" : next === 45 ? "\u00ad" : next === 10 || next === 13 ? "\n" : null;
      if (fallback > 0) fallback--;
      else if (symbol !== null) emit(symbol);
      state.start = false;
      continue;
    }
    let word = String.fromCharCode(next);
    while (pos < bytes.length && (bytes[pos] >= 65 && bytes[pos] <= 90 || bytes[pos] >= 97 && bytes[pos] <= 122)) {
      word += String.fromCharCode(bytes[pos++]);
      if (word.length > 32) fail("rtf_invalid");
    }
    let negative = false;
    if (bytes[pos] === 45) { negative = true; pos++; }
    const numberStart = pos;
    while (bytes[pos] >= 48 && bytes[pos] <= 57) {
      pos++;
      if (pos - numberStart > 10) fail("rtf_invalid");
    }
    if (negative && pos === numberStart) fail("rtf_invalid");
    const parameter = pos > numberStart ? Number(String.fromCharCode(...bytes.subarray(numberStart, pos))) * (negative ? -1 : 1) : null;
    if (parameter !== null && !Number.isSafeInteger(parameter)) fail("rtf_invalid");
    if (bytes[pos] === 32) pos++;
    if (word === "bin") {
      if (parameter === null || parameter < 0 || pos + parameter > bytes.length) fail("rtf_invalid");
      pos += parameter;
      if (fallback > 0) fallback--;
      omitted = true; state.start = false; continue;
    }
    if (state.starred && !(word === "ud" && state.unicodeAlternative)) { state.skip = true; omitted = true; }
    state.starred = false;
    if (OMIT_DESTINATIONS.has(word)) { state.skip = true; omitted = true; }
    if (word === "fonttbl") state.fontTable = true;
    if (word === "upr" && !state.skip) state.uprChild = 0;
    if (word === "ud" && !state.unicodeAlternative && !state.skip) fail("rtf_invalid");
    state.start = false;
    if (word === "rtf") { if (parameter !== 1 || stack.length !== 1) fail("rtf_invalid"); }
    else if (word === "deff" && parameter !== null) defaultFont = parameter;
    else if (word === "f" && parameter !== null) {
      if (state.fontTable) { state.fontDefinition = parameter; if (!fonts.has(parameter)) fonts.set(parameter, {}); }
      else state.font = parameter;
    } else if (state.fontTable && ["fcharset", "cpg"].includes(word) && parameter !== null && state.fontDefinition !== null) {
      fonts.set(state.fontDefinition, { ...fonts.get(state.fontDefinition), [word === "cpg" ? "codepage" : "charset"]: parameter });
    } else if (!state.skip && ["ansicpg", "ansi", "mac", "pc", "pca"].includes(word)) {
      const codepage = word === "ansicpg" ? parameter : word === "ansi" ? 1252 : word === "mac" ? 10000 : word === "pc" ? 437 : 850;
      if (codepage === null || !CODEPAGES[codepage]) fail("rtf_unsupported_encoding");
      state.codepage = codepage;
    } else if (word === "uc") {
      if (parameter === null || parameter < 0 || parameter > 32) fail("rtf_invalid");
      state.uc = parameter;
    } else if (word === "u") {
      if (parameter === null || parameter < -32768 || parameter > 65535) fail("rtf_invalid");
      emit(String.fromCharCode(parameter < 0 ? parameter + 65536 : parameter));
      fallback = state.uc;
    } else if (word === "v") {
      state.hidden = parameter !== 0; if (state.hidden) omitted = true;
    } else if (word === "deleted") {
      state.deleted = parameter !== 0; if (state.deleted) omitted = true;
    } else if (word === "plain") { state.hidden = false; state.font = defaultFont; }
    else if (word in SYMBOLS) { if (fallback > 0) fallback--; else emit(SYMBOLS[word]); }
    else if (fallback > 0) fallback--; // A control word counts as one Unicode fallback character.
  }
  if (!closed || stack.length) fail("rtf_invalid");
  flush();
  const text = chunks.join("");
  if (!validUnicode(text)) fail("rtf_invalid");
  return { text, warnings: omitted ? ["rtf_text_only", "rtf_omitted_destinations"] : ["rtf_text_only"] };
}
