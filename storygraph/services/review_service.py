"""Human review path for candidate facts."""

from __future__ import annotations

from storygraph.core.errors import ContractError
from storygraph.core.time import utc_now
from storygraph.models.candidate import CandidateFact, ReviewDecision
from storygraph.stores.candidate_store import CandidateStore
from storygraph.stores.graph_base import GraphStore


class ReviewService:
    def __init__(self, candidate_store: CandidateStore, graph_store: GraphStore) -> None:
        self.candidate_store = candidate_store
        self.graph_store = graph_store

    def submit(self, candidates: list[CandidateFact]) -> list[CandidateFact]:
        return [self.candidate_store.add(candidate) for candidate in candidates]

    def pending(self, *, project_id: str | None = None) -> list[CandidateFact]:
        return self.candidate_store.list(project_id=project_id, pending_only=True)

    def accept(self, candidate_id: str, *, reviewer: str, note: str | None = None) -> CandidateFact:
        candidate = self.candidate_store.get(candidate_id)
        self._require_pending(candidate)
        reviewed = candidate.model_copy(
            update={
                "status": "ACCEPTED_FOR_CANON",
                "review": ReviewDecision(
                    status="accepted",
                    reviewer=reviewer,
                    reviewed_at=utc_now(),
                    note=note,
                ),
            }
        )
        self.graph_store.commit_candidate_fact(
            reviewed,
            reviewer=reviewer,
            rationale=note or reviewed.rationale,
        )
        self.candidate_store.update(reviewed)
        return reviewed

    def edit_and_accept(
        self,
        candidate_id: str,
        *,
        reviewer: str,
        patch_properties: dict,
        note: str | None = None,
    ) -> CandidateFact:
        candidate = self.candidate_store.get(candidate_id)
        self._require_pending(candidate)
        patched_candidate = candidate.model_copy(
            update={
                "status": "ACCEPTED_FOR_CANON",
                "proposed_graph_patch": candidate.proposed_graph_patch.model_copy(
                    update={
                        "properties": {
                            **candidate.proposed_graph_patch.properties,
                            **patch_properties,
                        }
                    }
                ),
                "review": ReviewDecision(
                    status="edited",
                    reviewer=reviewer,
                    reviewed_at=utc_now(),
                    note=note,
                ),
            }
        )
        self.graph_store.commit_candidate_fact(
            patched_candidate,
            reviewer=reviewer,
            rationale=note or patched_candidate.rationale,
        )
        self.candidate_store.update(patched_candidate)
        return patched_candidate

    def reject(self, candidate_id: str, *, reviewer: str, note: str | None = None) -> CandidateFact:
        candidate = self.candidate_store.get(candidate_id)
        self._require_pending(candidate)
        rejected = candidate.model_copy(
            update={
                "status": "REJECTED",
                "review": ReviewDecision(
                    status="rejected",
                    reviewer=reviewer,
                    reviewed_at=utc_now(),
                    note=note,
                ),
            }
        )
        return self.candidate_store.update(rejected)

    def defer(self, candidate_id: str, *, reviewer: str, note: str | None = None) -> CandidateFact:
        candidate = self.candidate_store.get(candidate_id)
        self._require_pending(candidate)
        deferred = candidate.model_copy(
            update={
                "status": "DEFERRED",
                "review": ReviewDecision(
                    status="deferred",
                    reviewer=reviewer,
                    reviewed_at=utc_now(),
                    note=note,
                ),
            }
        )
        return self.candidate_store.update(deferred)

    @staticmethod
    def _require_pending(candidate: CandidateFact) -> None:
        if candidate.review.status != "pending":
            raise ContractError(
                f"CandidateFact {candidate.id} is already reviewed: {candidate.review.status}"
            )
