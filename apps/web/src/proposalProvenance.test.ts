import { describe, expect, it } from "vitest";
import { proposalCreationMethod } from "./proposalProvenance";
import type { ProposalArtifact } from "./api";
const snapshot = (version: number, via: ProposalArtifact["provenance"]["created_via"], id = "proposal-a", project = "project-a") => ({ id, project_id: project, version, provenance: { created_by: "author", created_via: via } });
describe("proposal creation provenance", () => {
  it("retains LLM creation across manual submission and acceptance versions", () => {
    const v1 = snapshot(1, "llm");
    expect(proposalCreationMethod(v1, [])).toBe("llm");
    expect(proposalCreationMethod(snapshot(2, "manual"), [v1])).toBe("llm");
    expect(proposalCreationMethod(snapshot(3, "manual"), [v1, snapshot(2, "manual")])).toBe("llm");
  });
  it("does not mistake later LLM revisions for the original creation method", () => {
    expect(proposalCreationMethod(snapshot(2, "llm"), [snapshot(1, "manual")])).toBe("manual");
  });
  it("waits for same-proposal same-project v1 instead of inventing an origin", () => {
    expect(proposalCreationMethod(snapshot(2, "manual"), [])).toBeNull();
    expect(proposalCreationMethod(snapshot(2, "manual"), [snapshot(1, "llm", "other")])).toBeNull();
    expect(proposalCreationMethod(snapshot(2, "manual"), [snapshot(1, "llm", "proposal-a", "other")])).toBeNull();
  });
});
