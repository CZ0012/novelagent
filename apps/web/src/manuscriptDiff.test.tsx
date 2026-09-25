import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ManuscriptDiff, type ManuscriptDiffLabels } from "./ManuscriptDiff";
import { buildManuscriptDiff, type ManuscriptDiffResult } from "./manuscriptDiffModel";

const parts = (result: ManuscriptDiffResult) => result.blocks.flatMap((item) => item.parts);
function reconstruct(result: ManuscriptDiffResult, side: "before" | "after") {
  return parts(result).filter((part) => part.kind !== (side === "before" ? "added" : "removed")).map((part) => part.text).join("");
}
function expectLossless(before: string, after: string) {
  const result = buildManuscriptDiff(before, after);
  expect(reconstruct(result, "before")).toBe(before);
  expect(reconstruct(result, "after")).toBe(after);
  return result;
}

const labels: ManuscriptDiffLabels = {
  title: "正文比较", added: "新增", removed: "删除", unchanged: "未改动", noChanges: "正文一致",
  simplified: "内容较长，部分修改按整段显示；两份正文均完整保留。", lineBreak: "换行"
};

// Exercise alignment deterministically even while desktop compilation uses the
// same machine. The separate budget test explicitly advances this clock.
beforeEach(() => { vi.spyOn(Date, "now").mockReturnValue(0); });
afterEach(() => { vi.restoreAllMocks(); });

describe("lossless prose comparison", () => {
  it("shows the changed Han characters inside unspaced Chinese prose", () => {
    const result = expectLossless("她推开蓝色的门。", "她推开红色的门。");
    expect(parts(result)).toEqual([
      { kind: "equal", text: "她推开" }, { kind: "removed", text: "蓝" },
      { kind: "added", text: "红" }, { kind: "equal", text: "色的门。" }
    ]);
  });

  it("keeps English words and punctuation readable instead of highlighting matching word fragments", () => {
    const result = expectLossless("She quietly walked home.", "She quietly ran home!");
    expect(parts(result).filter((part) => part.kind === "removed").map((part) => part.text)).toEqual(["walked", "."]);
    expect(parts(result).filter((part) => part.kind === "added").map((part) => part.text)).toEqual(["ran", "!"]);
  });

  it.each([
    ["", ""], ["", "新的开头。\n\n第二段。\n"], ["被删掉的开头。\n", ""],
    ["一样\r\n\r\n", "一样\r\n\r\n"], ["没有尾部换行", "没有尾部换行\n"],
    ["甲\r\n乙\r\n", "甲\n乙\n"], ["首段\n\n末段", "首段\n\n新增段\n\n末段"],
    ["回声\n回声\n终点", "回声\n插入\n回声\n终点"],
    ["a  b\tc", "a b\t\tc"], ["她望向🌒。", "她望向🌕。"],
    ["Café—don't go.", "Café—don't leave."], ["一\r二", "一\r\n二"]
  ])("preserves both sides including repeated paragraphs, whitespace and newlines: %j → %j", (before, after) => {
    const result = expectLossless(before, after);
    expect(result.changed).toBe(before !== after);
  });

  it("shows continuation as an insertion while retaining its full exact baseline", () => {
    const before = "钟声停了。\n\n屋内只剩他一人。";
    const after = before + "\n\n门外传来脚步声。";
    const result = expectLossless(before, after);
    expect(parts(result).some((part) => part.kind === "removed")).toBe(false);
    expect(parts(result).filter((part) => part.kind === "added").map((part) => part.text).join("")).toBe("\n\n门外传来脚步声。");
  });

  it("falls back for a very large rewrite without discarding any text", () => {
    const before = "共同开头🌒" + "甲".repeat(40000) + "相同结尾\r\n";
    const after = "共同开头🌕" + "乙".repeat(40000) + "相同结尾\r\n";
    const result = expectLossless(before, after);
    expect(result.simplified).toBe(true);
    expect(parts(result).length).toBeLessThanOrEqual(4);
    for (const part of parts(result)) {
      expect(part.text).not.toMatch(/^[\uDC00-\uDFFF]|[\uD800-\uDBFF]$/u);
    }
  });

  it("retains a long continuation even when paragraph alignment reaches its input bound", () => {
    const before = "原稿中的段落。\n".repeat(5000);
    const result = expectLossless(before, before + "最后，灯亮了。\n");
    expect(result.simplified).toBe(true);
    expect(parts(result)).toEqual([{ kind: "equal", text: before }, { kind: "added", text: "最后，灯亮了。\n" }]);
  });

  it("uses a lossless fallback when the comparison time budget expires", () => {
    const clock = vi.spyOn(Date, "now").mockReturnValueOnce(0).mockReturnValue(1000);
    try {
      const result = expectLossless("共同\n旧的段落\n尾声", "共同\n新的一段\n尾声");
      expect(result.simplified).toBe(true);
    } finally { clock.mockRestore(); }
  });

  it("reconstructs deterministic mixed-script edits including repeated tokens", () => {
    const vocabulary = ["风", "雨", "门", "🌕", "The", " door", " ", "\n", "\r\n", "。", "é"];
    let seed = 410;
    const next = () => (seed = (seed * 1664525 + 1013904223) >>> 0);
    for (let run = 0; run < 120; run++) {
      const original = Array.from({ length: 12 + next() % 50 }, () => vocabulary[next() % vocabulary.length]);
      const updated = [...original];
      for (let edit = 0; edit < 5; edit++) updated.splice(next() % (updated.length + 1), next() % 3, vocabulary[next() % vocabulary.length]);
      expectLossless(original.join(""), updated.join(""));
    }
  });
});

describe("accessible prose diff", () => {
  it("renders semantic deletion/insertion with explicit signs and localized reading labels", () => {
    const markup = renderToStaticMarkup(<ManuscriptDiff before="旧门。" after="新门。" labels={labels} />);
    expect(markup).toContain("<del>");
    expect(markup).toContain("<ins>");
    expect(markup).toContain("删除: ");
    expect(markup).toContain("新增: ");
    expect(markup).toContain("−");
    expect(markup).toContain("+");
    expect(markup).toContain('tabindex="0"');
    expect(markup).not.toContain("<button");
  });

  it("marks newline-only changes visibly and for screen readers", () => {
    const markup = renderToStaticMarkup(<ManuscriptDiff before="一句话。" after={"一句话。\n"} labels={labels} />);
    expect(markup).toContain("↵");
    expect(markup).toContain("换行");
    expect(markup).toContain("<ins>");
    expect(markup).not.toContain("<del>");
  });

  it("escapes manuscript markup and keeps all display text supplied by the caller", () => {
    const english = { title: "Compare", added: "Added", removed: "Removed", unchanged: "Unchanged", noChanges: "No changes", simplified: "Paragraph comparison", lineBreak: "Line break" };
    const markup = renderToStaticMarkup(<ManuscriptDiff before="<script>alert('x')</script>" after="<script>alert('x')</script>" labels={english} />);
    expect(markup).toContain("No changes");
    expect(markup).toContain("&lt;script&gt;");
    expect(markup).not.toContain("<script>");
    expect(markup).not.toContain("删除");
  });
});
