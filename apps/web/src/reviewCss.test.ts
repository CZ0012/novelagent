import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const css = readFileSync(new URL("./styles.css", import.meta.url), "utf8");
const appSource = readFileSync(new URL("./App.tsx", import.meta.url), "utf8");

describe("review workspace static boundaries", () => {
  it("uses the unified diff at 620px without horizontally overflowing author text", () => {
    const narrow = css.slice(css.indexOf("@media (max-width: 620px)"));
    expect(narrow).toContain(".proposal-diff-side-by-side");
    expect(narrow).toMatch(/\.proposal-diff-side-by-side\s*\{\s*display:\s*none;/);
    expect(narrow).toMatch(/\.proposal-diff-unified\s*\{[\s\S]*?display:\s*block;/);
    expect(narrow).toMatch(/\.proposal-diff-unified code\s*\{[\s\S]*?overflow-wrap:\s*anywhere;/);
  });

  it("keeps implementation strings out of App.tsx so both catalogs own the UI", () => {
    expect(appSource.match(/[\u3400-\u9fff]/g) ?? []).toHaveLength(0);
    expect(appSource).not.toMatch(/requestAgentProposal|onRequestAgent|onExtractFactDraft/);
  });

  it("routes every sidebar action that can switch project or scene through the dirty guard", () => {
    for (const prop of ["onCreateProject", "onCreateScene", "onArchiveDemo"]) {
      expect(appSource).toMatch(new RegExp(`${prop}=\\{\\(\\) => requestProposalNavigation\\(`));
    }
    expect(appSource).toMatch(/onSelectProject=\{[\s\S]*?requestProposalNavigation\(/);
    expect(appSource).toMatch(/onSelectScene=\{[\s\S]*?requestProposalNavigation\(/);
  });

  it("does not silently clear selected cross-language Source IDs when policy changes", () => {
    const start = appSource.indexOf("const changeCrossLanguagePolicy");
    const end = appSource.indexOf("const runEditCommand", start);
    const callback = appSource.slice(start, end);
    expect(callback).toContain("setCrossLanguagePolicy(policy)");
    expect(callback).not.toContain("setSelectedAgentSourceIds");
  });

  it("keeps Source-to-Agent handoff selection-only", () => {
    const start = appSource.indexOf("const useSourceWithAgent");
    const end = appSource.indexOf("const changeCrossLanguagePolicy", start);
    const callback = appSource.slice(start, end);
    expect(callback).toContain("addStableSourceSelection(current, source.id)");
    expect(callback).toContain('setWorkspaceTab("write")');
    expect(callback).toContain('setActiveTab("agent")');
    expect(callback).not.toMatch(/api(Get|Post|Patch|Put)|setAgentDiscussionForm|setCrossLanguagePolicy/);
  });

  it("runs guarded save-and-continue destinations only after the save action unlocks", () => {
    expect(appSource).toContain("onSave={saveProposalAndNavigate}");
    const start = appSource.indexOf("const saveProposalAndNavigate");
    const end = appSource.indexOf("const submitProposalReview", start);
    const callback = appSource.slice(start, end);
    expect(callback).toContain("continueAfterSuccessfulSave");
    expect(callback).toContain('await runAction("proposal-save-navigation"');
    expect(callback.indexOf("action?.()")).toBeGreaterThan(callback.indexOf("await runAction"));
  });

  it("invalidates pending latest-Draft loads before committing exact promoted Drafts", () => {
    const promotionStart = appSource.indexOf("const promoteProposalToDraft");
    const promotionEnd = appSource.indexOf("const applyProjectStructureProposal", promotionStart);
    const promotion = appSource.slice(promotionStart, promotionEnd);
    expect(promotion.indexOf("draftRequestSequenceRef.current += 1")).toBeGreaterThan(-1);
    expect(promotion.indexOf("draftRequestSequenceRef.current += 1")).toBeLessThan(
      promotion.indexOf("setDraft(result.draft)")
    );
    expect(promotion).toContain('setDraftSelection("")');
    expect(promotion).toContain('selectedText: ""');

    const openStart = appSource.indexOf("onOpenPromotedDraft={() =>");
    const openEnd = appSource.indexOf("onPromoteDraft=", openStart);
    const open = appSource.slice(openStart, openEnd);
    expect(open).toContain("exactDraftMatchesEditorScene");
    expect(open.indexOf("draftRequestSequenceRef.current += 1")).toBeGreaterThan(-1);
    expect(open.indexOf("draftRequestSequenceRef.current += 1")).toBeLessThan(
      open.indexOf("setDraft(proposalPromotedDraft.draft)")
    );
  });

  it("guards proposal-list writes by request sequence, API base, and active project", () => {
    const start = appSource.indexOf("const refreshProposals");
    const end = appSource.indexOf("const refreshFacts", start);
    const callback = appSource.slice(start, end);
    expect(callback).toContain("++proposalListRequestSequenceRef.current");
    expect(callback).toContain("projectRequestIsCurrent");
    expect(callback).toContain("activeApiBaseRef.current");
    expect(callback).toContain("activeProjectIdRef.current");
    expect(callback.indexOf("if (!requestIsCurrent()) return []")).toBeLessThan(
      callback.indexOf("setProposals(payload.proposals)")
    );
  });
});
