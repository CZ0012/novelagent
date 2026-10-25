import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it } from "vitest";
import { activateLocale } from "./localization";
import { LongformRevision } from "./LongformRevision";
import { observationPreviews, ObservationNotice, FactProposalObservations } from "./FactObservation";
beforeEach(async () => { await activateLocale("zh-CN"); });
describe("review-safe plan revisions and observational state", () => {
  it("offers a new alternative only for unapplied plans and guards unavailable or dirty actions", () => {
    const props = { applied: false, disabled: true, modelLabel: "planning-model", onRevise: () => undefined };
    const html = renderToStaticMarkup(<LongformRevision {...props} />);
    expect(html).toContain("新的独立提案"); expect(html).toContain('value="targeted" selected=""'); expect(html).toContain("定点修订"); expect(html).toContain("文字与人物开篇已知秘密"); expect(html).toContain("状态槽保持固定"); expect(html).toContain("重新构思完整规划"); expect(html).toContain('maxLength="12000"'); expect(html).toContain('disabled=""');
    const applied = renderToStaticMarkup(<LongformRevision {...props} applied />); expect(applied).toContain("不能原地修订"); expect(applied).not.toContain("<textarea");
  });
  it("labels operation-none previews and facts as observations without implying state updates", () => {
    const body = JSON.stringify({ candidate_previews: [{ id: "observation", value: "角色感到疲倦", proposed_graph_patch: { operation: "none" } }, { id: "relationship", value: "角色加入组织", proposed_graph_patch: { operation: "create_relation" } }] });
    expect(observationPreviews(body)).toEqual([{ id: "observation", value: "角色感到疲倦" }]);
    expect(observationPreviews('{')).toEqual([]);
    const html = renderToStaticMarkup(<FactProposalObservations body={body} />); expect(html).toContain("仅记录观察"); expect(html).toContain("不表示状态已更新"); expect(html).not.toContain("角色加入组织");
    expect(renderToStaticMarkup(<ObservationNotice operation="create_relation" />)).toBe("");
  });
});
