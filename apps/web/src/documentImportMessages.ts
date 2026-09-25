import type { SourceDocumentSummary } from "./api";
import { DocumentImportError, type DocumentImportErrorCode, type DocumentImportWarningCode } from "./documentImport";
import { uiText } from "./localization";
const emptyChecksum = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";
const errorCodes: DocumentImportErrorCode[] = ["empty_file", "file_read_failed", "invalid_docx", "empty_text", "rtf_invalid", "rtf_unsupported_encoding", "unsupported_text_encoding", "file_too_large", "text_too_large", "crypto_unavailable", "rtf_too_complex", "docx_too_large", "unsupported_format", "temporary_file"];
const warningCodes: DocumentImportWarningCode[] = ["rtf_text_only", "rtf_omitted_destinations", "docx_conversion_warnings"];
export function importErrorCode(error: unknown): DocumentImportErrorCode | null {
  if (error instanceof DocumentImportError) return error.code;
  const marker = typeof error === "string" ? error.match(/^import_error:([a-z_]+)$/)?.[1] : undefined;
  return marker && errorCodes.includes(marker as DocumentImportErrorCode) ? marker as DocumentImportErrorCode : null;
}
export function sourceImportFailureMessage(document: Pick<SourceDocumentSummary, "byte_size" | "checksum_sha256" | "error">): string {
  if (document.byte_size === 0 || document.checksum_sha256 === emptyChecksum) return uiText.documentImport.empty_file;
  const code = importErrorCode(document.error);
  return code ? uiText.documentImport[code] : uiText.documentImport.unknown_error;
}
export function importFailureMessage(error: unknown): string | null {
  const code = importErrorCode(error);
  return code ? uiText.documentImport[code] : null;
}
export function sourceImportWarningMessage(warning: string): string {
  const code = warning.match(/^import_warning:([a-z_]+)$/)?.[1] ?? warning;
  return warningCodes.includes(code as DocumentImportWarningCode) ? uiText.documentImport[code as DocumentImportWarningCode] : uiText.documentImport.unknown_warning;
}
