import { describe, expect, it, vi } from "vitest";
import { ApiRequestError, apiPost, isGeneratedLanguageConflict, isInvalidModelOutput } from "./api";

describe("generated output language failures", () => {
  it("classifies safe localized guidance without treating all backend failures as language failures", () => {
    expect(isGeneratedLanguageConflict(new ApiRequestError(422, "Generated output field chapter.title clearly conflicts with output_language zh-CN."))).toBe(true);
    expect(isGeneratedLanguageConflict(new ApiRequestError(422, "Generated output field scene.summary clearly conflicts with output_language en-US."))).toBe(true);
    expect(isGeneratedLanguageConflict(new ApiRequestError(500, "Provider unavailable"))).toBe(false);
    expect(isGeneratedLanguageConflict(new Error("Generated output field text clearly conflicts with output_language zh-CN."))).toBe(false);
  });
});

it("distinguishes malformed model output from backend JSON and unrelated transport failures", () => {
  expect(isInvalidModelOutput(new ApiRequestError(409, "Agent discussion response must be JSON"))).toBe(true);
  expect(isInvalidModelOutput(new ApiRequestError(409, "Agent discussion response must be a JSON object"))).toBe(true);
  expect(isInvalidModelOutput(new ApiRequestError(409, "Invalid generation", "model_output_invalid"))).toBe(true);
  expect(isInvalidModelOutput(new ApiRequestError(500, "Backend returned invalid JSON."))).toBe(false);
  expect(isInvalidModelOutput(new ApiRequestError(502, "Provider unreachable"))).toBe(false);
});

it("retains a stable outline conflict category separately from diagnostic text", async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: {
    category: "outline_language_stale", message: "Outline snapshot is no longer current"
  } }), { status: 409 }));
  vi.stubGlobal("fetch", fetch);
  try {
    await expect(apiPost("http://127.0.0.1:8766", "/projects/project-a/proposals/proposal-a/apply/outline-language", { expected_version: 2 }))
      .rejects.toMatchObject({ status: 409, category: "outline_language_stale", technicalDetails: "Outline snapshot is no longer current" });
  } finally { vi.unstubAllGlobals(); }
});
