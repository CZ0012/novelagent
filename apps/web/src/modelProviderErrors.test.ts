import { describe, expect, it } from "vitest";
import { ApiRequestError } from "./api";
import { modelProviderFailureKey, storedProviderFailureKey } from "./modelProviderErrors";
describe("finite provider error classification", () => {
  it("explains missing task configuration without silently selecting another connection", () => {
    expect(modelProviderFailureKey(new ApiRequestError(409, "Missing configuration", "llm_not_configured"))).toBe("modelMissingConfig");
  });
  it.each(["invalid_credentials", "rate_limit", "endpoint_not_found", "invalid_request", "provider_unavailable", "connection_error", "invalid_response", "incomplete_response", "unsupported_output", "request_failed"])("localizes %s consistently across tasks", (category) => {
    const key = modelProviderFailureKey(new ApiRequestError(502, `LLM provider HTTP 400 [${category}]: Safe backend guidance`));
    expect(key).not.toBeNull();
    expect(modelProviderFailureKey(new ApiRequestError(502, "Safe backend guidance", `composition_provider_${category}`))).toBe(key);
  });
  it("rejects arbitrary remote text and never returns it as a user-facing message", () => {
    expect(modelProviderFailureKey(new ApiRequestError(500, "remote novel excerpt [connection_error]: private"))).toBeNull();
    expect(modelProviderFailureKey(new ApiRequestError(500, "LLM provider [invented]: private"))).toBeNull();
    expect(modelProviderFailureKey(new Error("LLM provider [connection_error]: private"))).toBeNull();
  });
});

it.each(["plan_usage_limit", "plan_permission_required", "plan_not_eligible", "plan_usage_unavailable"])("localizes actual plan failure category %s without a generic fallback", category => {
  expect(modelProviderFailureKey(new ApiRequestError(409, "safe backend guidance", category))).toMatch(/^modelPlan/);
});


it("preserves finite provider diagnostics when reopening a saved session", () => {
  for (const category of ["request_failed", "invalid_request", "json_mode_input_required", "plan_permission_required", "provider_unavailable", "connection_error"]) {
    expect(storedProviderFailureKey(category)).toBe(modelProviderFailureKey(new ApiRequestError(502, "safe", category)));
    expect(storedProviderFailureKey(category)).not.toBeNull();
  }
  expect(storedProviderFailureKey("json_mode_input_required")).toBe("modelJsonInputRequired");
  expect(storedProviderFailureKey("private provider body")).toBeNull();
  expect(storedProviderFailureKey("__proto__")).toBeNull();
  expect(storedProviderFailureKey(null)).toBeNull();
});
