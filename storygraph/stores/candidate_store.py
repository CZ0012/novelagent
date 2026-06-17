"""Candidate Fact persistence."""

from __future__ import annotations

from storygraph.core.errors import ContractError
from storygraph.models.candidate import CandidateFact


class InMemoryCandidateStore:
    def __init__(self) -> None:
        self._facts: dict[str, CandidateFact] = {}

    def add(self, candidate: CandidateFact) -> CandidateFact:
        self._facts[candidate.id] = candidate
        return candidate

    def get(self, candidate_id: str) -> CandidateFact:
        try:
            return self._facts[candidate_id]
        except KeyError as exc:
            raise ContractError(f"CandidateFact not found: {candidate_id}") from exc

    def update(self, candidate: CandidateFact) -> CandidateFact:
        if candidate.id not in self._facts:
            raise ContractError(f"CandidateFact not found: {candidate.id}")
        self._facts[candidate.id] = candidate
        return candidate

    def list(self, *, project_id: str | None = None, pending_only: bool = False) -> list[CandidateFact]:
        facts = list(self._facts.values())
        if project_id:
            facts = [fact for fact in facts if fact.project_id == project_id]
        if pending_only:
            facts = [fact for fact in facts if fact.review.status == "pending"]
        return sorted(facts, key=lambda fact: fact.created_at)

