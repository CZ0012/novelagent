import { beforeEach, describe, expect, it } from "vitest";
import { activateLocale, uiText } from "./localization";
import { DocumentImportError } from "./documentImport";
import { importErrorCode, importFailureMessage, sourceImportFailureMessage, sourceImportWarningMessage } from "./documentImportMessages";
beforeEach(async () => { await activateLocale("zh-CN"); });
describe("safe localized source import diagnostics", () => {
  it("identifies legacy zero-byte DOCX as empty instead of a ZIP failure", () => {
    expect(sourceImportFailureMessage({ byte_size: 0, checksum_sha256: "", error: "DOCX extraction failed: End of data reached" })).toBe(uiText.documentImport.empty_file);
  });
  it("recognizes the empty checksum even for inconsistent legacy byte metadata", () => {
    expect(sourceImportFailureMessage({ byte_size: 42, checksum_sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", error: null })).toBe(uiText.documentImport.empty_file);
  });
  it("localizes code-only persisted errors and typed read failures", () => {
    expect(sourceImportFailureMessage({ byte_size: 42, checksum_sha256: "abc", error: "import_error:invalid_docx" })).toBe(uiText.documentImport.invalid_docx);
    expect(importFailureMessage(new DocumentImportError("file_read_failed"))).toBe(uiText.documentImport.file_read_failed);
  });
  it("never substitutes empty-file text for a nonempty failed document or exposes raw exception text", () => {
    for (const error of [null, "private C:/author/novel.docx excerpt", "import_error:invented"]) {
      expect(sourceImportFailureMessage({ byte_size: 42, checksum_sha256: "abc", error })).toBe(uiText.documentImport.unknown_error);
      expect(importErrorCode(error)).toBeNull();
    }
  });
  it("localizes finite conversion warnings without repeating raw content", () => {
    expect(sourceImportWarningMessage("import_warning:rtf_text_only")).toBe(uiText.documentImport.rtf_text_only);
    expect(sourceImportWarningMessage("private text from original document")).toBe(uiText.documentImport.unknown_warning);
  });
  it("uses the independently activated English catalog", async () => {
    await activateLocale("en-US");
    expect(sourceImportFailureMessage({ byte_size: 0, checksum_sha256: "", error: null })).toBe(uiText.documentImport.empty_file);
    expect(importFailureMessage(new DocumentImportError("rtf_invalid"))).not.toMatch(/[\u4e00-\u9fff]/);
  });
});
