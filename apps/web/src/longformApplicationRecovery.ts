import { ApiRequestError, type ProposalArtifact } from "./api";
export type LongformApplyAttempt = { apiBase: string; projectId: string; proposalId: string; expectedVersion: number; reviewId: string; body: string; title: string };
export function indeterminateApplyFailure(error: unknown): boolean {
  return error instanceof ApiRequestError ? error.status >= 500 && error.status <= 599 : error instanceof TypeError;
}
export function longformRetryMatches(attempt: LongformApplyAttempt | null, apiBase: string, projectId: string, proposal: ProposalArtifact | null, dirty: boolean): boolean {
  return Boolean(attempt && proposal && !dirty && proposal.status === "accepted" && proposal.artifact_type === "outline_draft" && attempt.apiBase === apiBase && attempt.projectId === projectId && proposal.project_id === projectId && attempt.proposalId === proposal.id && attempt.expectedVersion === proposal.version && attempt.body === proposal.body && attempt.title === proposal.title && attempt.reviewId);
}
