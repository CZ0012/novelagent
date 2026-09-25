import type { ProposalArtifact } from "./api";

type ProvenanceSnapshot = Pick<ProposalArtifact, "id" | "project_id" | "version" | "provenance">;
/** Creation provenance belongs to immutable v1, not later review bookkeeping. */
export function proposalCreationMethod(current: ProvenanceSnapshot | null, history: ProvenanceSnapshot[]): ProposalArtifact["provenance"]["created_via"] | null {
  if (!current) return null;
  if (current.version === 1) return current.provenance.created_via;
  return history.find((version) => version.id === current.id && version.project_id === current.project_id && version.version === 1)?.provenance.created_via ?? null;
}
