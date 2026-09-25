import { renderToStaticMarkup } from "react-dom/server";
import { beforeAll, describe, expect, it } from "vitest";
import type { ChapterOutline } from "./api";
import { activateLocale, uiText } from "./localization";
import { ProjectTree, sceneChapter, toggleChapterExpansion } from "./ProjectTree";
import { genreLabel } from "./genreLabels";

const chapters = [
  { id: "chapter-a", title: "Existing English chapter", scenes: [{ id: "scene-a", title: "Author's English title" }] },
  { id: "chapter-b", title: "第二章", scenes: [] }
] as unknown as ChapterOutline[];

beforeAll(async () => { await activateLocale("zh-CN"); });

describe("manuscript chapter tree", () => {
  it("expands chapters independently without changing which scene owns the draft", () => {
    const initial = new Set(["chapter-a"]);
    const closed = toggleChapterExpansion(initial, "chapter-a");
    expect(closed.has("chapter-a")).toBe(false);
    expect(initial.has("chapter-a")).toBe(true);
    expect(toggleChapterExpansion(closed, "chapter-b").has("chapter-b")).toBe(true);
    expect(sceneChapter(chapters, "scene-a")).toBe("chapter-a");
  });

  it("renders expandable chapter buttons and document leaves, preserving author titles", () => {
    const html = renderToStaticMarkup(<ProjectTree projectId="project-a" chapters={chapters} sceneId="scene-a" selectedChapterId="chapter-b" busy={false} onSelectChapter={() => {}} onSelectScene={() => {}} />);
    expect(html).toContain('aria-expanded="true"');
    expect(html).toContain('aria-expanded="false"');
    expect(html).toContain('aria-controls="chapter-children-chapter-a"');
    expect(html).toContain("Existing English chapter");
    expect(html).toContain("Author&#x27;s English title");
    const leaf = html.match(/<button[^>]*class="scene-row[\s\S]*?<\/button>/)?.[0];
    expect(leaf).toContain("lucide-file-text");
    expect(leaf).toContain('aria-current="page"');
    expect(leaf).not.toContain("aria-expanded");
    expect(leaf).not.toContain("lucide-chevron");
  });
});

describe("genre display localization", () => {
  it("localizes known enum values without translating titles or custom genre labels", () => {
    expect(genreLabel("fantasy", uiText.genres, "none")).toBe("奇幻");
    expect(genreLabel("My fantasy setting", uiText.genres, "none")).toBe("My fantasy setting");
    expect(genreLabel("自定义流派", uiText.genres, "none")).toBe("自定义流派");
    expect(genreLabel("__proto__", uiText.genres, "none")).toBe("__proto__");
  });
});
