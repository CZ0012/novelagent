import { webcrypto } from "node:crypto";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Draft, GraphNodePayload } from "./api";
import { correctionValueAllowed, exactCorrectionSpan, prepareTemporalCorrection, readonlyCorrectionSelection } from "./temporalCorrection";
const text = "甲🌟乙受伤。甲🌟乙恢复。";
const assertion: GraphNodePayload = { id: "state-old", type: "Event", status: "CANON", properties: { event_kind: "temporal_state_assertion_v1", project_id: "book", subject_id: "hero", field: "physical_state", value: "injured", valid_from_scene: "scene-a" } };
const draft: Draft = { id: "draft-correction", project_id: "book", scene_id: "scene-a", version: 4, text, discarded: false, created_at: "2026-10-25", updated_at: "2026-10-25" };
const selection = { text: "甲🌟乙恢复。", start: text.indexOf("甲🌟乙恢复。"), end: text.length };
beforeEach(() => { vi.stubGlobal("crypto", webcrypto); });
describe("author temporal corrections from exact saved prose", () => {
  it("converts UTF-16 selections to backend codepoint offsets and pins repeated passages by position", () => {
    expect(exactCorrectionSpan(text, selection)).toEqual({ start_offset: 6, end_offset: 12, quote: "甲🌟乙恢复。" });
    const repeated = "甲🌟乙。甲🌟乙。";
    expect(exactCorrectionSpan(repeated, { text: "甲🌟乙", start: 5, end: 9 })).toEqual({ start_offset: 4, end_offset: 7, quote: "甲🌟乙" });
  });
  it("reads original text-node ranges for repeated non-BMP passages while preserving CRLF", async () => {
    const original = "甲🌟乙\r\n相同。甲🌟乙\r\n相同。";
    const node = { nodeType: 3 } as Node;
    const root = { textContent: original, childNodes: [node], firstChild: node } as unknown as HTMLElement;
    const start = original.lastIndexOf("甲🌟乙"); const end = original.length;
    const nativeSelection = { isCollapsed: false, rangeCount: 1, getRangeAt: () => ({ startContainer: node, startOffset: start, endContainer: node, endOffset: end }) } as unknown as Selection;
    const selected = readonlyCorrectionSelection(root, original, nativeSelection);
    expect(selected).toEqual({ text: original.slice(start, end), start, end });
    expect(exactCorrectionSpan(original, selected)).toEqual({ start_offset: [...original.slice(0, start)].length, end_offset: [...original].length, quote: "甲🌟乙\r\n相同。" });
    const normalizedRoot = { ...root, textContent: original.replace(/\r\n/g, "\n") } as unknown as HTMLElement;
    expect(readonlyCorrectionSelection(normalizedRoot, original, nativeSelection)).toBeNull();
    const request = await prepareTemporalCorrection({ projectId: "book", assertion, fingerprint: "f".repeat(64), draft: { ...draft, text: original }, dirty: false, selection: selected, value: "healing", rationale: "保留换行证据", references: [] });
    expect(request?.source_span.quote).toContain("\r\n");
    const normalizedHash = await webcrypto.subtle.digest("SHA-256", new TextEncoder().encode(original.replace(/\r\n/g, "\n")));
    expect(request?.expected_source_sha256).not.toBe(Array.from(new Uint8Array(normalizedHash), (n) => n.toString(16).padStart(2, "0")).join(""));
  });
  it("rejects stale ranges, surrogate splits, blank evidence and oversized quotes", () => {
    expect(exactCorrectionSpan(text, { ...selection, text: "错误引文" })).toBeNull();
    expect(exactCorrectionSpan(text, { text: text.slice(2, 4), start: 2, end: 4 })).toBeNull();
    expect(exactCorrectionSpan(text, { text: text.slice(0, 2), start: 0, end: 2 })).toBeNull();
    expect(exactCorrectionSpan(" ", { text: " ", start: 0, end: 1 })).toBeNull();
    expect(exactCorrectionSpan("字".repeat(501), { text: "字".repeat(501), start: 0, end: 501 })).toBeNull();
  });
  it("computes hash, exact saved version and slot fingerprint without accepting typed provenance", async () => {
    const request = await prepareTemporalCorrection({ projectId: "book", assertion, fingerprint: "f".repeat(64), draft, dirty: false, selection, value: "healing", rationale: "依原场景修正恢复状态", references: [] });
    expect(request).toMatchObject({ assertion_id: "state-old", source_draft_id: draft.id, expected_draft_version: 4, source_span: { start_offset: 6, end_offset: 12, quote: selection.text }, expected_slot_fingerprint: "f".repeat(64), value: "healing" });
    const hash = await webcrypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
    expect(request?.expected_source_sha256).toBe(Array.from(new Uint8Array(hash), (n) => n.toString(16).padStart(2, "0")).join(""));
  });
  it("blocks dirty, cross-project, cross-scene, unchanged and invalid-value corrections", async () => {
    const args = { projectId: "book", assertion, fingerprint: "f".repeat(64), draft, dirty: false, selection, value: "healing", rationale: "更正", references: [] };
    for (const patch of [{ dirty: true }, { projectId: "other" }, { draft: { ...draft, scene_id: "other" } }, { draft: { ...draft, project_id: "other" } }, { value: "injured" }, { value: "alive" }, { rationale: " " }, { fingerprint: "typed-hash" }]) expect(await prepareTemporalCorrection({ ...args, ...patch })).toBeNull();
  });
  it("allows only canonical typed references and distinguishes known unowned", () => {
    const refs = [{ id: "city", label: "雾城", type: "Location" }, { id: "hero", label: "主角", type: "Character" }];
    expect(correctionValueAllowed("location_id", "city", refs)).toBe(true);
    expect(correctionValueAllowed("location_id", "hero", refs)).toBe(false);
    expect(correctionValueAllowed("owner_id", "hero", refs)).toBe(true);
    expect(correctionValueAllowed("owner_id", null, refs)).toBe(true);
    expect(correctionValueAllowed("location_id", null, refs)).toBe(false);
    expect(correctionValueAllowed("owner_id", "arbitrary-id", refs)).toBe(false);
  });
});
