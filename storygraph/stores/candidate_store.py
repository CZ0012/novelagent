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

    def add_many(self, candidates: list[CandidateFact]) -> list[CandidateFact]:
        raise NotImplementedError

    def get(self, candidate_id: str) -> CandidateFact:
        raise NotImplementedError

    def update(self, candidate: CandidateFact) -> CandidateFact:
        raise NotImplementedError

    def update_if_pending(self, candidate: CandidateFact) -> CandidateFact:
        raise NotImplementedError

    def replace_if_current(
        self,
        candidate: CandidateFact,
        *,
        expected: CandidateFact,
    ) -> bool:
        raise NotImplementedError

    def list(self, *, project_id: str | None = None, pending_only: bool = False) -> list[CandidateFact]:
        raise NotImplementedError


class InMemoryCandidateStore(CandidateStore):
    def __init__(self) -> None:
        self._facts: dict[str, CandidateFact] = {}
        self._lock = RLock()

    def add(self, candidate: CandidateFact) -> CandidateFact:
        return self.add_many([candidate])[0]

    def add_many(self, candidates: list[CandidateFact]) -> list[CandidateFact]:
        with self._lock:
            candidate_ids = [candidate.id for candidate in candidates]
            duplicate_ids = _duplicate_ids(candidate_ids)
            if duplicate_ids:
                raise ContractError(
                    f"Duplicate CandidateFact ids in batch: {', '.join(duplicate_ids)}"
                )
            existing_ids = sorted(
                candidate_id for candidate_id in candidate_ids if candidate_id in self._facts
            )
            if existing_ids:
                raise ContractError(f"Duplicate CandidateFact id: {existing_ids[0]}")
            self._facts.update({candidate.id: candidate for candidate in candidates})
            return candidates

    def get(self, candidate_id: str) -> CandidateFact:
        with self._lock:
            try:
                return self._facts[candidate_id]
            except KeyError as exc:
                raise ContractError(f"CandidateFact not found: {candidate_id}") from exc

    def update(self, candidate: CandidateFact) -> CandidateFact:
        with self._lock:
            if candidate.id not in self._facts:
                raise ContractError(f"CandidateFact not found: {candidate.id}")
            self._facts[candidate.id] = candidate
            return candidate

    def update_if_pending(self, candidate: CandidateFact) -> CandidateFact:
        with self._lock:
            current = self.get(candidate.id)
            if current.review.status != "pending":
                raise ContractError(
                    f"CandidateFact {candidate.id} is already reviewed: {current.review.status}"
                )
            self._facts[candidate.id] = candidate
            return candidate

    def replace_if_current(
        self,
        candidate: CandidateFact,
        *,
        expected: CandidateFact,
    ) -> bool:
        with self._lock:
            current = self.get(candidate.id)
            if current != expected:
                return False
            self._facts[candidate.id] = candidate
            return True

    def list(self, *, project_id: str | None = None, pending_only: bool = False) -> list[CandidateFact]:
        with self._lock:
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
        return self.add_many([candidate])[0]

    def add_many(self, candidates: list[CandidateFact]) -> list[CandidateFact]:
        candidate_ids = [candidate.id for candidate in candidates]
        duplicate_ids = _duplicate_ids(candidate_ids)
        if duplicate_ids:
            raise ContractError(
                f"Duplicate CandidateFact ids in batch: {', '.join(duplicate_ids)}"
            )
        if not candidates:
            return []
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                existing_ids = self._existing_ids(candidate_ids)
                if existing_ids:
                    raise ContractError(f"Duplicate CandidateFact id: {existing_ids[0]}")
                self._connection.executemany(
                    """
                    INSERT INTO candidate_facts
                    (id, project_id, review_status, candidate_status, created_at, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [self._row_values(candidate) for candidate in candidates],
                )
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
            return candidates

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

    def update_if_pending(self, candidate: CandidateFact) -> CandidateFact:
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                cursor = self._connection.execute(
                    """
                    UPDATE candidate_facts
                    SET project_id = ?, review_status = ?, candidate_status = ?,
                        created_at = ?, payload_json = ?
                    WHERE id = ? AND review_status = 'pending'
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
                if cursor.rowcount != 1:
                    current = self._connection.execute(
                        "SELECT review_status FROM candidate_facts WHERE id = ?",
                        (candidate.id,),
                    ).fetchone()
                    if current is None:
                        raise ContractError(f"CandidateFact not found: {candidate.id}")
                    raise ContractError(
                        f"CandidateFact {candidate.id} is already reviewed: "
                        f"{current['review_status']}"
                    )
                self._connection.commit()
                return candidate
            except Exception:
                self._connection.rollback()
                raise

    def replace_if_current(
        self,
        candidate: CandidateFact,
        *,
        expected: CandidateFact,
    ) -> bool:
        with self._lock:
            cursor = self._connection.execute(
                """
                UPDATE candidate_facts
                SET project_id = ?, review_status = ?, candidate_status = ?,
                    created_at = ?, payload_json = ?
                WHERE id = ? AND payload_json = ?
                """,
                (
                    candidate.project_id,
                    candidate.review.status,
                    candidate.status,
                    candidate.created_at,
                    candidate.model_dump_json(),
                    candidate.id,
                    expected.model_dump_json(),
                ),
            )
            self._connection.commit()
            return cursor.rowcount == 1

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

    def _existing_ids(self, candidate_ids: list[str]) -> list[str]:
        placeholders = ", ".join("?" for _ in candidate_ids)
        rows = self._connection.execute(
            f"SELECT id FROM candidate_facts WHERE id IN ({placeholders}) ORDER BY id",
            candidate_ids,
        ).fetchall()
        return [str(row["id"]) for row in rows]

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


def _duplicate_ids(candidate_ids: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for candidate_id in candidate_ids:
        if candidate_id in seen:
            duplicates.add(candidate_id)
        seen.add(candidate_id)
    return sorted(duplicates)
