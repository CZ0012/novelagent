"""Candidate Fact persistence."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import RLock
from typing import Protocol

from storygraph.core.errors import ContractError
from storygraph.models.candidate import CandidateFact


class CandidateStore(Protocol):
    def add(self, candidate: CandidateFact) -> CandidateFact:
        raise NotImplementedError

    def get(self, candidate_id: str) -> CandidateFact:
        raise NotImplementedError

    def update(self, candidate: CandidateFact) -> CandidateFact:
        raise NotImplementedError

    def list(self, *, project_id: str | None = None, pending_only: bool = False) -> list[CandidateFact]:
        raise NotImplementedError


class InMemoryCandidateStore(CandidateStore):
    def __init__(self) -> None:
        self._facts: dict[str, CandidateFact] = {}

    def add(self, candidate: CandidateFact) -> CandidateFact:
        if candidate.id in self._facts:
            raise ContractError(f"Duplicate CandidateFact id: {candidate.id}")
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


class SQLiteCandidateStore(CandidateStore):
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self._lock = RLock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS candidate_facts (
                  id TEXT PRIMARY KEY,
                  project_id TEXT NOT NULL,
                  review_status TEXT NOT NULL,
                  candidate_status TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  payload_json TEXT NOT NULL
                )
                """
            )
            self._connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_candidate_facts_project_review
                ON candidate_facts(project_id, review_status, created_at)
                """
            )
            self._connection.commit()

    def add(self, candidate: CandidateFact) -> CandidateFact:
        with self._lock:
            if self._exists(candidate.id):
                raise ContractError(f"Duplicate CandidateFact id: {candidate.id}")
            self._connection.execute(
                """
                INSERT INTO candidate_facts
                (id, project_id, review_status, candidate_status, created_at, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                self._row_values(candidate),
            )
            self._connection.commit()
            return candidate

    def get(self, candidate_id: str) -> CandidateFact:
        with self._lock:
            row = self._connection.execute(
                "SELECT payload_json FROM candidate_facts WHERE id = ?",
                (candidate_id,),
            ).fetchone()
            if row is None:
                raise ContractError(f"CandidateFact not found: {candidate_id}")
            return CandidateFact.model_validate_json(row["payload_json"])

    def update(self, candidate: CandidateFact) -> CandidateFact:
        with self._lock:
            if not self._exists(candidate.id):
                raise ContractError(f"CandidateFact not found: {candidate.id}")
            self._connection.execute(
                """
                UPDATE candidate_facts
                SET project_id = ?, review_status = ?, candidate_status = ?, created_at = ?, payload_json = ?
                WHERE id = ?
                """,
                (
                    candidate.project_id,
                    candidate.review.status,
                    candidate.status,
                    candidate.created_at,
                    candidate.model_dump_json(),
                    candidate.id,
                ),
            )
            self._connection.commit()
            return candidate

    def list(self, *, project_id: str | None = None, pending_only: bool = False) -> list[CandidateFact]:
        query = "SELECT payload_json FROM candidate_facts"
        clauses: list[str] = []
        params: list[str] = []
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        if pending_only:
            clauses.append("review_status = ?")
            params.append("pending")
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at ASC, id ASC"
        with self._lock:
            rows = self._connection.execute(query, params).fetchall()
            return [CandidateFact.model_validate_json(row["payload_json"]) for row in rows]

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _exists(self, candidate_id: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM candidate_facts WHERE id = ?",
            (candidate_id,),
        ).fetchone()
        return row is not None

    @staticmethod
    def _row_values(candidate: CandidateFact) -> tuple[str, str, str, str, str, str]:
        return (
            candidate.id,
            candidate.project_id,
            candidate.review.status,
            candidate.status,
            candidate.created_at,
            candidate.model_dump_json(),
        )
