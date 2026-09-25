import { describe, expect, it } from "vitest";
import { ApiRequestError } from "./api";
import { modelProviderFailureKey } from "./modelProviderErrors";
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
