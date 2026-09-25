import { ApiRequestError } from "./api";
const failureKeys = {
  invalid_credentials: "outlineLanguageProviderCredentials", rate_limit: "outlineLanguageProviderRateLimit",
  endpoint_not_found: "outlineLanguageProviderEndpoint", invalid_request: "outlineLanguageProviderInvalidRequest",
  provider_unavailable: "outlineLanguageProviderUnavailable", connection_error: "outlineLanguageProviderConnection",
  invalid_response: "outlineLanguageProviderResponse", incomplete_response: "modelIncompleteResponse",
  unsupported_output: "modelUnsupportedOutput", request_failed: "modelRequestFailed", failed: "modelRequestFailed", llm_not_configured: "modelMissingConfig"
} as const;
/** Classify only backend-owned finite diagnostics; never display provider bodies. */
export function modelProviderFailureKey(error: unknown): typeof failureKeys[keyof typeof failureKeys] | null {
  if (!(error instanceof ApiRequestError)) return null;
  const category = error.category === "llm_not_configured" ? "llm_not_configured" : error.category?.match(/^(?:composition|outline_language)_provider_([a-z_]+)$/)?.[1]
    ?? error.technicalDetails.match(/^LLM provider(?: HTTP \d{3})? \[([a-z_]+)\]: /)?.[1];
  return category && Object.prototype.hasOwnProperty.call(failureKeys, category) ? failureKeys[category as keyof typeof failureKeys] : null;
}
