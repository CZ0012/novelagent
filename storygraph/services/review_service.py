"""Human review path for candidate facts."""

from __future__ import annotations

from storygraph.core.errors import ContractError, GraphStoreError
from storygraph.core.time import utc_now
from storygraph.models.candidate import CandidateFact, ReviewDecision
from storygraph.stores.candidate_store import CandidateStore
from storygraph.stores.graph_base import GraphStore


class ReviewService:
    def __init__(self, candidate_store: CandidateStore, graph_store: GraphStore) -> None:
        self.candidate_store = candidate_store
        self.graph_store = graph_store

    def submit(self, candidates: list[CandidateFact]) -> list[CandidateFact]:
        validated = [self.validate_candidate_scope(candidate) for candidate in candidates]
        return self.candidate_store.add_many(validated)

    def pending(self, *, project_id: str | None = None) -> list[CandidateFact]:
        return self.candidate_store.list(project_id=project_id, pending_only=True)

    def validate_candidate_scope(
        self,
        candidate: CandidateFact,
        *,
        project_id: str | None = None,
    ) -> CandidateFact:
        try:
            return self.graph_store.validate_candidate_scope(
                candidate,
                expected_project_id=project_id,
            )
        except GraphStoreError as exc:
            if exc.category != "conflict_detected":
                raise
            raise ContractError(str(exc)) from exc

    def accept(self, candidate_id: str, *, reviewer: str, note: str | None = None) -> CandidateFact:
        candidate = self.candidate_store.get(candidate_id)
        self._require_pending(candidate)
        candidate = self.validate_candidate_scope(candidate)
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
        return self._persist_review_and_commit(
            original=candidate,
            reviewed=reviewed,
            reviewer=reviewer,
            rationale=note or reviewed.rationale,
        )

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
                "proposed_graph_patch": candidate.proposed_graph_patch.model_copy(
                    update={
                        "properties": {
                            **candidate.proposed_graph_patch.properties,
                            **patch_properties,
                        }
                    }
                ),
            }
        )
        patched_candidate = self.validate_candidate_scope(patched_candidate)
        patched_candidate = patched_candidate.model_copy(
            update={
                "status": "ACCEPTED_FOR_CANON",
                "review": ReviewDecision(
                    status="edited",
                    reviewer=reviewer,
                    reviewed_at=utc_now(),
                    note=note,
                ),
            }
        )
        return self._persist_review_and_commit(
            original=candidate,
            reviewed=patched_candidate,
            reviewer=reviewer,
            rationale=note or patched_candidate.rationale,
        )

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
        return self.candidate_store.update_if_pending(rejected)

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
        return self.candidate_store.update_if_pending(deferred)

    @staticmethod
    def _require_pending(candidate: CandidateFact) -> None:
        if candidate.review.status != "pending":
            raise ContractError(
                f"CandidateFact {candidate.id} is already reviewed: {candidate.review.status}"
            )

    def _persist_review_and_commit(
        self,
        *,
        original: CandidateFact,
        reviewed: CandidateFact,
        reviewer: str,
        rationale: str,
    ) -> CandidateFact:
        """Persist the review before canon, compensating if the graph rejects it.

        Candidate and graph persistence cannot share a database transaction across
        every supported backend. This ordering guarantees that a failed candidate
        write never reaches canon. A synchronous graph failure is compensated by
        restoring the original pending record; the graph exception remains the
        observable failure even if that best-effort compensation also fails.
        """

        self.candidate_store.update_if_pending(reviewed)
        try:
            self.graph_store.commit_candidate_fact(
                reviewed,
                reviewer=reviewer,
                rationale=rationale,
            )
        except Exception:
            try:
                self.candidate_store.replace_if_current(original, expected=reviewed)
            except Exception:
                # Preserve the graph failure. Recovery/audit tooling can reconcile
                # a reviewed candidate whose canon commit did not complete.
                pass
            raise
        return reviewed
