import { describe, expect, it } from "vitest";
import { ApiRequestError, type ProposalArtifact } from "./api";
import { indeterminateApplyFailure, longformRetryMatches, type LongformApplyAttempt } from "./longformApplicationRecovery";
const proposal = { id: "plan-a", project_id: "book", artifact_type: "outline_draft", status: "accepted", version: 4, body: "exact plan body", title: "plan" } as ProposalArtifact;
const attempt: LongformApplyAttempt = { apiBase: "http://localhost:8000", projectId: "book", proposalId: "plan-a", expectedVersion: 4, reviewId: "review-exact-v4", body: proposal.body, title: proposal.title };
describe("explicit uncertain longform application recovery", () => {
  it("permits retained attempts after network or 5xx outcomes only", () => {
    expect(indeterminateApplyFailure(new TypeError("Failed to fetch"))).toBe(true);
    expect(indeterminateApplyFailure(new ApiRequestError(500, "safe"))).toBe(true);
    expect(indeterminateApplyFailure(new ApiRequestError(503, "safe"))).toBe(true);
    for (const status of [200, 400, 403, 404, 409, 422]) expect(indeterminateApplyFailure(new ApiRequestError(status, "safe"))).toBe(false);
    expect(indeterminateApplyFailure(new Error("arbitrary application error"))).toBe(false);
  });
  it("pins the original version/review ID and clears eligibility on scope or content changes", () => {
    expect(longformRetryMatches(attempt, attempt.apiBase, "book", proposal, false)).toBe(true);
    expect(attempt.reviewId).toBe("review-exact-v4"); expect(attempt.expectedVersion).toBe(4);
    expect(longformRetryMatches(attempt, "http://other", "book", proposal, false)).toBe(false);
    expect(longformRetryMatches(attempt, attempt.apiBase, "other", proposal, false)).toBe(false);
    for (const patch of [{ id: "other-plan" }, { version: 5 }, { body: "edited body" }, { title: "edited title" }, { status: "author_revised" }, { project_id: "foreign" }]) expect(longformRetryMatches(attempt, attempt.apiBase, "book", { ...proposal, ...patch } as ProposalArtifact, false)).toBe(false);
    expect(longformRetryMatches(attempt, attempt.apiBase, "book", proposal, true)).toBe(false);
    expect(longformRetryMatches(null, attempt.apiBase, "book", proposal, false)).toBe(false);
    expect(longformRetryMatches({ ...attempt, reviewId: "" }, attempt.apiBase, "book", proposal, false)).toBe(false);
  });
});
