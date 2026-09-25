import { describe, expect, it } from "vitest";
import { selectedManuscriptRange } from "./ManuscriptReader";

function selectionFixture(full: string, start: number, text: string) {
  const node = {} as Node;
  const root = { textContent: full, contains: (item: Node) => item === node } as unknown as HTMLElement;
  const prefix = { selectNodeContents: () => {}, setEnd: () => {}, toString: () => full.slice(0, start) };
  const selection = { isCollapsed: false, anchorNode: node, focusNode: node, rangeCount: 1, getRangeAt: () => ({ startContainer: node, startOffset: start, cloneRange: () => prefix, toString: () => text }) } as unknown as Selection;
  return { root, selection };
}
describe("exact manuscript selection", () => {
  it("preserves spaces, CRLF, and the UTF-16 position of the second identical passage", () => {
    const full = "🌟第一段\r\n 重复。\r\n 重复。";
    const start = full.lastIndexOf(" 重复。"); const text = " 重复。";
    const { root, selection } = selectionFixture(full, start, text);
    expect(selectedManuscriptRange(root, selection)).toEqual({ text, start, end: full.length });
  });
  it("rejects ranges crossing outside the manuscript instead of including toolbar text", () => {
    const { root, selection } = selectionFixture("正文", 0, "正文");
    Object.defineProperty(selection, "focusNode", { value: {} });
    expect(selectedManuscriptRange(root, selection)).toBeNull();
  });
  it("rejects stale rendered ranges and collapsed selections", () => {
    const { root, selection } = selectionFixture("新正文", 0, "旧正文");
    expect(selectedManuscriptRange(root, selection)).toBeNull();
    expect(selectedManuscriptRange(root, null)).toBeNull();
    Object.defineProperty(selection, "isCollapsed", { value: true });
    expect(selectedManuscriptRange(root, selection)).toBeNull();
  });
});
