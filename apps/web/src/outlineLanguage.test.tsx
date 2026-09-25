import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ApiRequestError, type ProposalArtifact } from "./api";
import { OutlineLanguagePreview } from "./OutlineLanguagePreview";
import { activateLocale } from "./localization";
import { canApplyOutlineLanguagePatch, outlineLanguageApplicationRecorded, outlineLanguageFailureKey, outlineLanguageScopeMatches, parseOutlineLanguagePatch, type OutlineLanguagePatch } from "./outlineLanguage";

const patch: OutlineLanguagePatch = {
  schema: "outline_language_patch_v1", project_id: "project-a", output_language: "zh-CN",
  changes: [
    { node_id: "chapter-a", node_type: "Chapter", field: "title", before: "The Silent Bell", after: "无声之钟" },
    { node_id: "chapter-a", node_type: "Chapter", field: "summary", before: "The bell rang.", after: "钟声响起。" },
    { node_id: "scene-a", node_type: "Scene", field: "goal", before: "Find the bell", after: "找到钟" }
  ]
};
const proposal = (body: unknown = patch, overrides: Partial<ProposalArtifact> = {}): ProposalArtifact => ({
  id: "proposal-a", project_id: "project-a", artifact_type: "canon_patch", body_format: "structured_json",
  status: "accepted", version: 2, content_language: "zh-CN", title: "目录语言建议", body: JSON.stringify(body), ...overrides
} as ProposalArtifact);

describe("outline language proposal boundaries", () => {
  it("recognizes only the supported structured canon patch, leaving other proposals untouched", () => {
    expect(parseOutlineLanguagePatch(proposal())).toEqual(patch);
    expect(parseOutlineLanguagePatch(null)).toBeNull();
    expect(parseOutlineLanguagePatch(proposal(patch, { artifact_type: "outline_draft" }))).toBeNull();
    expect(parseOutlineLanguagePatch(proposal(patch, { body_format: "plain_text" }))).toBeNull();
    expect(parseOutlineLanguagePatch(proposal({ ...patch, schema: "canon_patch_v1" }))).toBeNull();
    expect(parseOutlineLanguagePatch(proposal(patch, { body: "{ malformed" }))).toBeNull();
    expect(parseOutlineLanguagePatch(proposal(patch, { content_language: "en-US" }))).toBeNull();
    expect(parseOutlineLanguagePatch(proposal(patch, { content_language: null }))).toBeNull();
  });

  it("does not offer apply for cross-project, unknown-field, injected-operation or duplicate changes", () => {
    for (const invalid of [
      { ...patch, project_id: "project-b" }, { ...patch, output_language: "und" }, { ...patch, changes: [] },
      { ...patch, changes: [{ ...patch.changes[0], field: "draft_text" }] },
      { ...patch, changes: [{ ...patch.changes[0], node_type: "Project" }] },
      { ...patch, changes: [{ ...patch.changes[0], before: null }] },
      { ...patch, changes: [{ ...patch.changes[0], before: "" }] },
      { ...patch, changes: [{ ...patch.changes[0], after: "文".repeat(2001) }] },
      { ...patch, changes: [{ ...patch.changes[0], after: " " }] },
      { ...patch, changes: [{ ...patch.changes[0], after: patch.changes[0].before }] },
      { ...patch, changes: [{ ...patch.changes[0], operations: [] }] },
      { ...patch, operations: [{ type: "delete_node" }] },
      { ...patch, changes: [patch.changes[0], patch.changes[0]] }
    ]) expect(canApplyOutlineLanguagePatch(proposal(invalid), false, "project-a")).toBe(false);
  });

  it("requires the saved accepted version and current project before explicit application", () => {
    expect(canApplyOutlineLanguagePatch(proposal(), false, "project-a")).toBe(true);
    expect(canApplyOutlineLanguagePatch(proposal(), true, "project-a")).toBe(false);
    expect(canApplyOutlineLanguagePatch(proposal(), false, "project-b")).toBe(false);
    for (const status of ["drafting", "agent_revised", "author_revised", "ready_for_review", "rejected"] as const) {
      expect(canApplyOutlineLanguagePatch(proposal(patch, { status }), false, "project-a")).toBe(false);
    }
  });

  it("rejects stale request completions after either project or API connection changes", () => {
    const target = { apiBase: "http://127.0.0.1:8766", projectId: "project-a" };
    expect(outlineLanguageScopeMatches(target, target.apiBase, "project-a")).toBe(true);
    expect(outlineLanguageScopeMatches(target, target.apiBase, "project-b")).toBe(false);
    expect(outlineLanguageScopeMatches(target, "http://127.0.0.1:8767", "project-a")).toBe(false);
  });

  it("marks a repair applied only with one unique canon-event receipt per changed node, preserving partial receipt recovery", () => {
    const chapterEvent = { kind: "canon_event", ref: `evt_ol_${"a".repeat(32)}` };
    const sceneEvent = { kind: "canon_event", ref: `evt_ol_${"b".repeat(32)}` };
    const complete = proposal(patch, { derived_refs: [chapterEvent, sceneEvent] });
    expect(outlineLanguageApplicationRecorded(complete)).toBe(true);
    expect(canApplyOutlineLanguagePatch(complete, false, "project-a")).toBe(false);
    for (const derived_refs of [[], [chapterEvent], [chapterEvent, chapterEvent], [chapterEvent, { kind: "draft", ref: "draft-a" }]]) {
      const recoverable = proposal(patch, { derived_refs });
      expect(outlineLanguageApplicationRecorded(recoverable)).toBe(false);
      expect(canApplyOutlineLanguagePatch(recoverable, false, "project-a")).toBe(true);
    }
  });

  it("maps only safe provider categories to actionable messages without interpreting provider text", () => {
    const expected = {
      endpoint_not_found: "outlineLanguageProviderEndpoint", invalid_credentials: "outlineLanguageProviderCredentials",
      rate_limit: "outlineLanguageProviderRateLimit", invalid_request: "outlineLanguageProviderInvalidRequest",
      provider_unavailable: "outlineLanguageProviderUnavailable", connection_error: "outlineLanguageProviderConnection",
      invalid_response: "outlineLanguageProviderResponse", request_failed: "outlineLanguageProviderFailed", failed: "outlineLanguageProviderFailed"
    };
    for (const [category, key] of Object.entries(expected)) {
      expect(outlineLanguageFailureKey(new ApiRequestError(502, "The configured provider could not complete outline language repair.", `outline_language_provider_${category}`))).toBe(key);
    }
    expect(outlineLanguageFailureKey(new Error("HTTP 404 invalid_credentials"))).toBeNull();
    expect(outlineLanguageFailureKey(new ApiRequestError(404, "Model not found", "unknown"))).toBeNull();
  });

  it("renders current and suggested text separately while UI language does not rewrite proposal content", async () => {
    await activateLocale("zh-CN");
    const chinese = renderToStaticMarkup(<OutlineLanguagePreview patch={patch} />);
    expect(chinese).toContain("当前内容");
    expect(chinese).toContain("建议内容");
    expect(chinese).toContain("The Silent Bell");
    expect(chinese).toContain("无声之钟");
    expect(chinese).not.toContain("<button");
    await activateLocale("en-US");
    const english = renderToStaticMarkup(<OutlineLanguagePreview patch={patch} />);
    expect(english).toContain("Current text");
    expect(english).toContain("Suggested text");
    expect(english).toContain("Simplified Chinese");
    expect(english).toContain("The Silent Bell");
    expect(english).toContain("无声之钟");
  });
});
