import { describe, expect, it, vi } from "vitest";
import { readFile } from "node:fs/promises";
import JSZip from "jszip";
import {
  classifyDocumentFile, decodePlainText, DOCUMENT_IMPORT_LIMITS, DocumentImportError,
  extractDocumentFile, extractDocxText, extractRtfText, type DocumentFile
} from "./documentImport";

const ascii = (text: string) => Uint8Array.from(text, character => character.charCodeAt(0));
const rtf = (text: string) => extractRtfText(ascii(text));
const file = (name: string, bytes: Uint8Array): DocumentFile => ({ name, size: bytes.length,
  arrayBuffer: async () => bytes.slice().buffer as ArrayBuffer });
const errorCode = (fn: () => unknown, code: string) => {
  try { fn(); throw new Error("Expected failure"); } catch (error) {
    expect(error).toBeInstanceOf(DocumentImportError);
    expect((error as DocumentImportError).code).toBe(code);
  }
};

describe("local document file classification and identities", () => {
  it("recognizes supported extensions and skips Office lock files before reading", async () => {
    expect(classifyDocumentFile("Notes.MARKDOWN")).toEqual({ kind: "supported", mediaType: "text/markdown" });
    expect(classifyDocumentFile("novel.RTF")).toEqual({ kind: "supported", mediaType: "application/rtf" });
    expect(classifyDocumentFile("folder/~$novel.docx")).toEqual({ kind: "temporary" });
    const read = vi.fn();
    await expect(extractDocumentFile({ name: "~$novel.docx", size: 162, arrayBuffer: read })).rejects.toMatchObject({ code: "temporary_file" });
    expect(read).not.toHaveBeenCalled();
    expect(classifyDocumentFile("old.doc")).toEqual({ kind: "unsupported" });
  });
  it.each(["novel.docx", "novel.rtf", "novel.txt"])("classifies a genuinely empty %s without calling it damaged", async name => {
    const result = await extractDocumentFile(file(name, new Uint8Array()));
    expect(result).toMatchObject({ byteSize: 0, text: null, errorCode: "empty_file",
      checksumSha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" });
  });
  it("rejects read errors and short/oversized reads without creating false checksums", async () => {
    await expect(extractDocumentFile({ name: "novel.docx", size: 12, arrayBuffer: async () => { throw new Error("private/path"); } })).rejects.toMatchObject({ code: "file_read_failed", message: "import_error:file_read_failed" });
    await expect(extractDocumentFile({ ...file("novel.docx", ascii("abc")), size: 12 })).rejects.toMatchObject({ code: "file_read_failed" });
    await expect(extractDocumentFile({ ...file("novel.docx", ascii("abc")), size: 0 })).rejects.toMatchObject({ code: "file_read_failed" });
    const read = vi.fn();
    await expect(extractDocumentFile({ name: "huge.rtf", size: DOCUMENT_IMPORT_LIMITS.maxFileBytes + 1, arrayBuffer: read })).rejects.toMatchObject({ code: "file_too_large" });
    expect(read).not.toHaveBeenCalled();
  });
  it("preserves UTF-8 TXT/Markdown bytes and identifies whitespace-only input separately", async () => {
    const text = "第一段。\r\n\r\nSecond paragraph. 😀";
    const bytes = new TextEncoder().encode(text);
    const result = await extractDocumentFile(file("novel.md", bytes));
    expect(result.text).toBe(text);
    expect(result.byteSize).toBe(bytes.length);
    expect(result.errorCode).toBeNull();
    const blank = await extractDocumentFile(file("novel.txt", ascii(" \r\n\t")));
    expect(blank.errorCode).toBe("empty_text");
    expect(blank.byteSize).toBe(4);
  });
  it("reads BOM-marked UTF16 without guessing arbitrary legacy text encodings", () => {
    expect(decodePlainText(new Uint8Array([0xff, 0xfe, 0x2d, 0x4e, 0x87, 0x65]))).toBe("中文");
    expect(decodePlainText(new Uint8Array([0xfe, 0xff, 0x4e, 0x2d, 0x65, 0x87]))).toBe("中文");
    errorCode(() => decodePlainText(new Uint8Array([0xff, 0xff])), "unsupported_text_encoding");
  });
});

describe("bounded RTF plain-text extraction", () => {
  it("reads nested formatting, paragraph/line breaks and literal escapes", () => {
    expect(rtf(String.raw`{\rtf1\ansi First {\b bold {\i nested}} end.\par Second\line Line\tab Tab \\ \{x\}}`).text)
      .toBe("First bold nested end.\n\nSecond\nLine\tTab \\ {x}");
  });
  it("reads Chinese signed Unicode and supplementary UTF16 pairs", () => {
    expect(rtf(String.raw`{\rtf1\ansi\uc1 \u20013?\u25991?\u-10179?\u-8704?\par \u38634?}`).text).toBe("中文😀\n\n雪");
  });
  it("honors group-scoped uc fallback counts, hex fallback bytes and escaped fallback symbols", () => {
    expect(rtf(String.raw`{\rtf1\ansi\uc1 \u20013?{\uc2\u25991\'ce\'c4}\u23383\?\uc0\u20320\u22909}`).text).toBe("中文字你好");
  });
  it("decodes ansicpg936 escaped GBK bytes and font-specific codepages", () => {
    expect(rtf(String.raw`{\rtf1\ansi\ansicpg936 \'d6\'d0\'ce\'c4}`).text).toBe("中文");
    expect(rtf(String.raw`{\rtf1\ansi\ansicpg1252\deff0{\fonttbl{\f0\fnil\fcharset0 Arial;}{\f1\fcharset134 SimSun;}{\f2\fcharset2 Symbol;}}\f1 \'d6\'d0\'ce\'c4\f0 English}`).text).toBe("中文English");
    expect(rtf(String.raw`{\rtf1\ansi\ansicpg1252{\fonttbl{\f1\fcharset0\cpg936 SimSun;}}\f1 \'d6\'d0}`).text).toBe("中");
  });
  it("decodes raw GBK and mixed codepage scopes without losing multibyte runs", () => {
    const bytes = new Uint8Array([...ascii(String.raw`{\rtf1\ansi\ansicpg936 `), 0xd6, 0xd0, 0xce, 0xc4, ...ascii("}")]);
    expect(extractRtfText(bytes).text).toBe("中文");
    expect(rtf(String.raw`{\rtf1\ansi\ansicpg1252 caf\'e9 {\ansicpg936\'d6\'d0} fin}`).text).toBe("café 中 fin");
    const long = String.raw`{\rtf1\ansi\ansicpg936 ` + String.raw`\'d6\'d0`.repeat(40_000) + "}";
    expect(rtf(long).text).toHaveLength(40_000);
  });
  it("ignores font/info/pictures/objects/starred destinations and field instructions, keeps displayed field text", () => {
    const result = rtf(String.raw`{\rtf1\ansi{\fonttbl{\f0 Arial;}}{\info{\title private title}}Before {\pict\pngblip 012345}{\object{\objdata evil.exe}}{\*\unknown private}{\field{\*\fldinst HYPERLINK "https://invalid.test/private"}{\fldrslt display}} after.}`);
    expect(result.text).toBe("Before display after.");
    expect(result.warnings).toContain("rtf_omitted_destinations");
  });
  it("skips binary payload by byte count without treating embedded braces as syntax", () => {
    expect(rtf(String.raw`{\rtf1 Before {\pict\bin5 ` + "}{\\{}" + "} after.}").text).toBe("Before  after.");
  });
  it("chooses the Unicode representation of upr instead of duplicating ANSI and Unicode text", () => {
    expect(rtf(String.raw`{\rtf1\ansi {\upr{fallback}{\*\ud\uc1\u20013?\u25991?}}}`).text).toBe("中文");
  });
  it("omits hidden/deleted text and restores group properties", () => {
    expect(rtf(String.raw`{\rtf1 A{\v hidden}B{\deleted removed}C}`).text).toBe("ABC");
  });
  it("keeps deletion and visibility independent for bytes, Unicode and symbols", () => {
    expect(rtf(String.raw`{\rtf1 A{\deleted\v0 removed\u20013?\tab}B{\v\deleted0 hidden\'41\par}C}`).text).toBe("ABC");
    expect(rtf(String.raw`{\rtf1 A{\deleted\v\deleted0 hidden\v0 shown}B}`).text).toBe("AshownB");
    expect(rtf(String.raw`{\rtf1 A{\v\deleted\v0 removed\deleted0 shown}B}`).text).toBe("AshownB");
  });
  it("restores scoped deletion and resets plain formatting without accepting deletions", () => {
    expect(rtf(String.raw`{\rtf1 A{\deleted removed{\deleted0 kept}removed}B}`).text).toBe("AkeptB");
    expect(rtf(String.raw`{\rtf1 A{\v hidden\plain shown}B{\deleted removed\plain stillremoved}C}`).text).toBe("AshownBC");
  });
  it.each([
    "not RTF", String.raw`{\rtf2 text}`, String.raw`{\rtf1 missing`, String.raw`{\rtf1 x}}`, String.raw`{\rtf1 x}garbage`,
    String.raw`{\rtf1 \'zz}`, String.raw`{\rtf1 \bin999 abc}`, String.raw`{\rtf1 \u-10179?}`, String.raw`{\rtf1 \u-8704?}`,
    String.raw`{\rtf1 \uc-1 x}`, String.raw`{\rtf1 \u70000?}`, String.raw`{\rtf1\ansicpg936 \'d6}`
  ])("rejects malformed input rather than returning partial text: %s", text => errorCode(() => rtf(text), "rtf_invalid"));
  it("rejects unsupported declared/active encodings but ignores unused font charsets", () => {
    errorCode(() => rtf(String.raw`{\rtf1\ansicpg9999 abc}`), "rtf_unsupported_encoding");
    errorCode(() => rtf(String.raw`{\rtf1{\fonttbl{\f1\fcharset2 Symbol;}}\f1 abc}`), "rtf_unsupported_encoding");
    expect(rtf(String.raw`{\rtf1{\fonttbl{\f1\fcharset2 Symbol;}}safe}`).text).toBe("safe");
  });
  it("enforces input, nesting and output limits", () => {
    errorCode(() => extractRtfText(new Uint8Array(DOCUMENT_IMPORT_LIMITS.maxFileBytes + 1)), "file_too_large");
    errorCode(() => rtf(String.raw`{\rtf1 ` + "{".repeat(130) + "x" + "}".repeat(131)), "rtf_too_complex");
    errorCode(() => rtf(String.raw`{\rtf1 ` + "a".repeat(DOCUMENT_IMPORT_LIMITS.maxTextCharacters + 1) + "}"), "text_too_large");
  });
  it("reports textless and invalid RTF as failed extraction, never ready synthetic prose", async () => {
    expect((await extractDocumentFile(file("novel.rtf", ascii(String.raw`{\rtf1{\pict ff00}}`)))).errorCode).toBe("empty_text");
    const failed = await extractDocumentFile(file("novel.rtf", ascii(String.raw`{\rtf1 broken`)));
    expect(failed.errorCode).toBe("rtf_invalid");
    expect(failed.text).toBeNull();
    expect(failed.checksumSha256).toHaveLength(64);
  });
});

describe("DOCX regression and bounded archive diagnostics", () => {
  it("does not send an arbitrary nonempty DOCX to the ZIP parser", async () => {
    const result = await extractDocumentFile(file("bad.docx", ascii("This is not a zip.")));
    expect(result.errorCode).toBe("invalid_docx");
    expect(result.text).toBeNull();
  });
  it("keeps real Mammoth single-paragraph extraction working", async () => {
    const bytes = await readFile(new URL("../node_modules/mammoth/test/test-data/single-paragraph.docx", import.meta.url));
    const result = await extractDocxText(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
    expect(result.text).toContain("Walking on imported air");
  });
  it("distinguishes a valid DOCX with no extracted text from an unreadable DOCX", async () => {
    const bytes = await readFile(new URL("../node_modules/mammoth/test/test-data/empty.docx", import.meta.url));
    const result = await extractDocumentFile(file("empty.docx", bytes));
    expect(result.errorCode).toBe("empty_text");
  });
  it("rejects a declared archive expansion beyond its cap before extraction", async () => {
    const original = await readFile(new URL("../node_modules/mammoth/test/test-data/single-paragraph.docx", import.meta.url));
    const bytes = new Uint8Array(original);
    const view = new DataView(bytes.buffer);
    for (let i = 0; i < bytes.length - 46; i++) {
      if (view.getUint32(i, true) === 0x02014b50) { view.setUint32(i + 24, DOCUMENT_IMPORT_LIMITS.maxDocxExpandedBytes + 1, true); break; }
    }
    await expect(extractDocxText(bytes.buffer)).rejects.toMatchObject({ code: "docx_too_large" });
  });
});

it("rejects a forged ZIP expanded size instead of inflating unbounded data", async () => {
  const original = await readFile(new URL("../node_modules/mammoth/test/test-data/single-paragraph.docx", import.meta.url));
  const bytes = new Uint8Array(original);
  const view = new DataView(bytes.buffer);
  for (let i = 0; i < bytes.length - 46; i++) {
    if (view.getUint32(i, true) === 0x02014b50 && view.getUint16(i + 10, true) === 8) {
      view.setUint32(i + 24, 0, true); break;
    }
  }
  await expect(extractDocxText(bytes.buffer)).rejects.toMatchObject({ code: "invalid_docx" });
});

async function generatedDocx(extraName?: string): Promise<ArrayBuffer> {
  const original = await readFile(new URL("../node_modules/mammoth/test/test-data/single-paragraph.docx", import.meta.url));
  const zip = await JSZip.loadAsync(original);
  if (extraName) zip.file(extraName, "Synthetic extra", { createFolders: false });
  return zip.generateAsync({ type: "arraybuffer", compression: "DEFLATE" });
}

it("rejects central/local name disagreement before extracting a JSZip-generated DOCX", async () => {
  const buffer = await generatedDocx();
  expect((await extractDocxText(buffer)).text).toBe("Walking on imported air\n\n");
  const view = new DataView(buffer);
  const bytes = new Uint8Array(buffer);
  let altered = false;
  for (let i = 0; i < bytes.length - 46; i++) {
    if (view.getUint32(i, true) !== 0x02014b50) continue;
    const name = new TextDecoder().decode(bytes.subarray(i + 46, i + 46 + view.getUint16(i + 28, true)));
    if (name === "word/document.xml") { bytes[i + 46] = 97; altered = true; break; }
  }
  expect(altered).toBe(true);
  await expect(extractDocxText(buffer)).rejects.toMatchObject({ code: "invalid_docx" });
});

it("rejects a Unicode path override even when local and central raw names match", async () => {
  const buffer = await generatedDocx("中文.xml");
  const view = new DataView(buffer);
  const bytes = new Uint8Array(buffer);
  let altered = false;
  for (let i = 0; i < bytes.length - 46; i++) {
    if (view.getUint32(i, true) !== 0x02014b50) continue;
    const length = view.getUint16(i + 28, true);
    if (new TextDecoder().decode(bytes.subarray(i + 46, i + 46 + length)) !== "中文.xml") continue;
    const local = view.getUint32(i + 42, true);
    view.setUint16(i + 8, view.getUint16(i + 8, true) & ~0x800, true);
    view.setUint16(local + 6, view.getUint16(local + 6, true) & ~0x800, true);
    const end = i + 46 + length + view.getUint16(i + 30, true);
    for (let extra = i + 46 + length; extra < end; extra += 4 + view.getUint16(extra + 2, true)) {
      if (view.getUint16(extra, true) === 0x7075) {
        bytes.set(new TextEncoder().encode("文本.xml"), extra + 9); altered = true; break;
      }
    }
    break;
  }
  expect(altered).toBe(true);
  await expect(extractDocxText(buffer)).rejects.toMatchObject({ code: "invalid_docx" });
});

it.each(["../word/document.xml", "word/../document.xml", "word\\document.xml", "/absolute.xml", "word/./document.xml", "word//document.xml"])("rejects ambiguous ZIP entry path %s", async name => {
  await expect(extractDocxText(await generatedDocx(name))).rejects.toMatchObject({ code: "invalid_docx" });
});

it("does not open RTF links or evaluate objects while extracting text", () => {
  const request = vi.fn(() => { throw new Error("External access forbidden"); });
  vi.stubGlobal("fetch", request);
  try {
    const result = rtf(String.raw`{\rtf1 {\field{\*\fldinst INCLUDEPICTURE "https://invalid.test/picture"}{\fldrslt Label}}{\object\objlink{\*\objclass Package}{\*\objdata 001122}}}`);
    expect(result.text).toBe("Label");
    expect(request).not.toHaveBeenCalled();
  } finally { vi.unstubAllGlobals(); }
});
