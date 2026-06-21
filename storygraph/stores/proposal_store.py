"""Proposal Artifact persistence."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import RLock
from typing import Literal, Protocol

from storygraph.core.errors import ContractError
from storygraph.core.time import utc_now
from storygraph.models.proposal import (
    ProposalArtifact,
    ProposalBodyFormat,
    ProposalCreatedVia,
    ProposalProvenance,
    ProposalRef,
    ProposalReviewDecision,
)


TERMINAL_PROPOSAL_STATUSES = {"accepted", "rejected"}


class ProposalStore(Protocol):
    def create(self, proposal: ProposalArtifact) -> ProposalArtifact:
        raise NotImplementedError

    def get(self, proposal_id: str, *, version: int | None = None) -> ProposalArtifact:
        raise NotImplementedError

    def history(self, proposal_id: str) -> list[ProposalArtifact]:
        raise NotImplementedError

    def list(
        self,
        *,
        project_id: str | None = None,
        status: str | None = None,
        artifact_type: str | None = None,
    ) -> list[ProposalArtifact]:
        raise NotImplementedError


class SQLiteProposalStore(ProposalStore):
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
                CREATE TABLE IF NOT EXISTS proposal_artifacts (
                  id TEXT NOT NULL,
                  version INTEGER NOT NULL,
                  project_id TEXT NOT NULL,
                  artifact_type TEXT NOT NULL,
                  status TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  payload_json TEXT NOT NULL,
                  PRIMARY KEY (id, version)
                )
                """
            )
            self._connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_proposal_artifacts_project
                ON proposal_artifacts(project_id, status, artifact_type, updated_at, id)
                """
            )
            self._connection.commit()

    def create(self, proposal: ProposalArtifact) -> ProposalArtifact:
        if proposal.version != 1:
            raise ContractError("New ProposalArtifact records must start at version 1")
        with self._lock:
            if self._exists(proposal.id):
                raise ContractError(f"Duplicate ProposalArtifact id: {proposal.id}")
            self._insert(proposal)
            self._connection.commit()
            return proposal

    def get(self, proposal_id: str, *, version: int | None = None) -> ProposalArtifact:
        with self._lock:
            if version is None:
                row = self._connection.execute(
                    """
                    SELECT payload_json FROM proposal_artifacts
                    WHERE id = ?
                    ORDER BY version DESC
                    LIMIT 1
                    """,
                    (proposal_id,),
                ).fetchone()
            else:
                row = self._connection.execute(
                    """
                    SELECT payload_json FROM proposal_artifacts
                    WHERE id = ? AND version = ?
                    """,
                    (proposal_id, version),
                ).fetchone()
            if row is None:
                raise ContractError(f"ProposalArtifact not found: {proposal_id}")
            return ProposalArtifact.model_validate_json(row["payload_json"])

    def history(self, proposal_id: str) -> list[ProposalArtifact]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT payload_json FROM proposal_artifacts
                WHERE id = ?
                ORDER BY version ASC
                """,
                (proposal_id,),
            ).fetchall()
            if not rows:
                raise ContractError(f"ProposalArtifact not found: {proposal_id}")
            return [ProposalArtifact.model_validate_json(row["payload_json"]) for row in rows]

    def list(
        self,
        *,
        project_id: str | None = None,
        status: str | None = None,
        artifact_type: str | None = None,
    ) -> list[ProposalArtifact]:
        query = """
            SELECT p.payload_json FROM proposal_artifacts p
            INNER JOIN (
              SELECT id, MAX(version) AS latest_version
              FROM proposal_artifacts
              GROUP BY id
            ) latest
              ON p.id = latest.id AND p.version = latest.latest_version
        """
        clauses: list[str] = []
        params: list[str] = []
        if project_id:
            clauses.append("p.project_id = ?")
            params.append(project_id)
        if status:
            clauses.append("p.status = ?")
            params.append(status)
        if artifact_type:
            clauses.append("p.artifact_type = ?")
            params.append(artifact_type)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY p.updated_at DESC, p.id ASC"
        with self._lock:
            rows = self._connection.execute(query, params).fetchall()
            return [ProposalArtifact.model_validate_json(row["payload_json"]) for row in rows]

    def revise(
        self,
        proposal_id: str,
        *,
        actor: str,
        created_via: ProposalCreatedVia = "manual",
        title: str | None = None,
        body: str | None = None,
        body_format: ProposalBodyFormat | None = None,
        target_refs: list[ProposalRef] | None = None,
        source_refs: list[ProposalRef] | None = None,
        note: str | None = None,
        expected_version: int | None = None,
        status: Literal["agent_revised", "author_revised"] = "author_revised",
    ) -> ProposalArtifact:
        with self._lock:
            latest = self.get(proposal_id)
            self._ensure_writable(latest, expected_version=expected_version)
            now = utc_now()
            proposal = ProposalArtifact.model_validate(
                {
                    **latest.model_dump(),
                    "title": title if title is not None else latest.title,
                    "body": body if body is not None else latest.body,
                    "body_format": body_format if body_format is not None else latest.body_format,
                    "target_refs": target_refs if target_refs is not None else latest.target_refs,
                    "source_refs": source_refs if source_refs is not None else latest.source_refs,
                    "provenance": ProposalProvenance(
                        created_by=actor,
                        created_via=created_via,
                        workflow_run_id=latest.provenance.workflow_run_id,
                        model_ref=latest.provenance.model_ref,
                        note=note,
                    ),
                    "version": latest.version + 1,
                    "status": status,
                    "review_decision": ProposalReviewDecision(),
                    "updated_at": now,
                }
            )
            self._insert(proposal)
            self._connection.commit()
            return proposal

    def mark_ready(
        self,
        proposal_id: str,
        *,
        actor: str,
        note: str | None = None,
        expected_version: int | None = None,
    ) -> ProposalArtifact:
        with self._lock:
            latest = self.get(proposal_id)
            self._ensure_writable(latest, expected_version=expected_version)
            now = utc_now()
            proposal = ProposalArtifact.model_validate(
                {
                    **latest.model_dump(),
                    "provenance": ProposalProvenance(
                        created_by=actor,
                        created_via="manual",
                        workflow_run_id=latest.provenance.workflow_run_id,
                        model_ref=latest.provenance.model_ref,
                        note=note,
                    ),
                    "version": latest.version + 1,
                    "status": "ready_for_review",
                    "review_decision": ProposalReviewDecision(),
                    "updated_at": now,
                }
            )
            self._insert(proposal)
            self._connection.commit()
            return proposal

    def review(
        self,
        proposal_id: str,
        *,
        decision: Literal["accepted", "rejected"],
        reviewer: str,
        note: str | None = None,
        expected_version: int | None = None,
    ) -> ProposalArtifact:
        with self._lock:
            latest = self.get(proposal_id)
            self._ensure_writable(latest, expected_version=expected_version)
            now = utc_now()
            proposal = ProposalArtifact.model_validate(
                {
                    **latest.model_dump(),
                    "provenance": ProposalProvenance(
                        created_by=reviewer,
                        created_via="manual",
                        workflow_run_id=latest.provenance.workflow_run_id,
                        model_ref=latest.provenance.model_ref,
                        note=note,
                    ),
                    "version": latest.version + 1,
                    "status": decision,
                    "review_decision": ProposalReviewDecision(
                        status=decision,
                        reviewer=reviewer,
                        reviewed_at=now,
                        note=note,
                    ),
                    "updated_at": now,
                }
            )
            self._insert(proposal)
            self._connection.commit()
            return proposal

    def record_derived_ref(
        self,
        proposal_id: str,
        *,
        derived_ref: ProposalRef,
        actor: str,
        note: str | None = None,
        expected_version: int | None = None,
    ) -> ProposalArtifact:
        with self._lock:
            latest = self.get(proposal_id)
            if expected_version is not None and latest.version != expected_version:
                raise ContractError(
                    "Stale ProposalArtifact version: "
                    f"expected {expected_version}, got {latest.version}"
                )
            if latest.status == "rejected":
                raise ContractError(f"Rejected ProposalArtifact cannot derive refs: {latest.id}")
            now = utc_now()
            proposal = ProposalArtifact.model_validate(
                {
                    **latest.model_dump(),
                    "provenance": ProposalProvenance(
                        created_by=actor,
                        created_via="api",
                        workflow_run_id=latest.provenance.workflow_run_id,
                        model_ref=latest.provenance.model_ref,
                        note=note,
                    ),
                    "version": latest.version + 1,
                    "derived_refs": [*latest.derived_refs, derived_ref],
                    "updated_at": now,
                }
            )
            self._insert(proposal)
            self._connection.commit()
            return proposal

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _ensure_writable(
        self,
        latest: ProposalArtifact,
        *,
        expected_version: int | None,
    ) -> None:
        if expected_version is not None and latest.version != expected_version:
            raise ContractError(
                f"Stale ProposalArtifact version: expected {expected_version}, got {latest.version}"
            )
        if latest.status in TERMINAL_PROPOSAL_STATUSES:
            raise ContractError(f"ProposalArtifact is already {latest.status}: {latest.id}")

    def _exists(self, proposal_id: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM proposal_artifacts WHERE id = ? LIMIT 1",
            (proposal_id,),
        ).fetchone()
        return row is not None

    def _insert(self, proposal: ProposalArtifact) -> None:
        self._connection.execute(
            """
            INSERT INTO proposal_artifacts
            (id, version, project_id, artifact_type, status, created_at, updated_at, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                proposal.id,
                proposal.version,
                proposal.project_id,
                proposal.artifact_type,
                proposal.status,
                proposal.created_at,
                proposal.updated_at,
                proposal.model_dump_json(),
            ),
        )
