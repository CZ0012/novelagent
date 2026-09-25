import { describe, expect, it } from "vitest";
import { ApiRequestError, isGeneratedLanguageConflict } from "./api";

describe("generated output language failures", () => {
  it("classifies safe localized guidance without treating all backend failures as language failures", () => {
    expect(isGeneratedLanguageConflict(new ApiRequestError(422, "Generated output field chapter.title clearly conflicts with output_language zh-CN."))).toBe(true);
    expect(isGeneratedLanguageConflict(new ApiRequestError(422, "Generated output field scene.summary clearly conflicts with output_language en-US."))).toBe(true);
    expect(isGeneratedLanguageConflict(new ApiRequestError(500, "Provider unavailable"))).toBe(false);
    expect(isGeneratedLanguageConflict(new Error("Generated output field text clearly conflicts with output_language zh-CN."))).toBe(false);
  });
});
