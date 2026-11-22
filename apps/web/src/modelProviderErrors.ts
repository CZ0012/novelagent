import { ApiRequestError } from "./api";
const failureKeys = {
  plan_usage_limit: "modelPlanUsageLimit", plan_permission_required: "modelPlanPermission", plan_not_eligible: "modelPlanEligibility", plan_usage_unavailable: "modelPlanUnavailable",
  invalid_credentials: "outlineLanguageProviderCredentials", rate_limit: "outlineLanguageProviderRateLimit",
  endpoint_not_found: "outlineLanguageProviderEndpoint", invalid_request: "outlineLanguageProviderInvalidRequest",
  provider_unavailable: "outlineLanguageProviderUnavailable", connection_error: "outlineLanguageProviderConnection",
  invalid_response: "outlineLanguageProviderResponse", incomplete_response: "modelIncompleteResponse",
  unsupported_output: "modelUnsupportedOutput", request_failed: "modelRequestFailed", failed: "modelRequestFailed", llm_not_configured: "modelMissingConfig"
} as const;
/** Classify only backend-owned finite diagnostics; never display provider bodies. */
export function modelProviderFailureKey(error: unknown): typeof failureKeys[keyof typeof failureKeys] | null {
  if (!(error instanceof ApiRequestError)) return null;
  const category = error.category && Object.prototype.hasOwnProperty.call(failureKeys, error.category) ? error.category : error.category?.match(/^(?:composition|outline_language)_provider_([a-z_]+)$/)?.[1]
    ?? error.technicalDetails.match(/^LLM provider(?: HTTP \d{3})? \[([a-z_]+)\]: /)?.[1];
  return category && Object.prototype.hasOwnProperty.call(failureKeys, category) ? failureKeys[category as keyof typeof failureKeys] : null;
}

export function isPlanProviderFailure(error: unknown): boolean { const key = modelProviderFailureKey(error); return Boolean(key?.startsWith("modelPlan")); }
export function storedPlanFailureKey(category: string | null | undefined): "modelPlanUsageLimit" | "modelPlanPermission" | "modelPlanEligibility" | "modelPlanUnavailable" | null { return category === "plan_usage_limit" ? "modelPlanUsageLimit" : category === "plan_permission_required" ? "modelPlanPermission" : category === "plan_not_eligible" ? "modelPlanEligibility" : category === "plan_usage_unavailable" ? "modelPlanUnavailable" : null; }
