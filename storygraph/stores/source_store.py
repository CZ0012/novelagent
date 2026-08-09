"""SQLite persistence for project-scoped imported source documents."""

from __future__ import annotations

import sqlite3
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import RLock
from typing import Protocol

from storygraph.core.errors import ContractError
from storygraph.core.time import utc_now
from storygraph.models.source import SourceDocument, SourceDocumentSummary


@dataclass(frozen=True, slots=True)
class SourceStoreWriteResult:
    document: SourceDocument
    created: bool
    updated: bool


class SourceStore(Protocol):
    def create_or_get(self, document: SourceDocument) -> SourceStoreWriteResult:
        raise NotImplementedError

    def get(self, *, project_id: str, source_id: str) -> SourceDocument:
        raise NotImplementedError

    def list(
        self,
        *,
        project_id: str,
        include_archived: bool = False,
    ) -> list[SourceDocumentSummary]:
        raise NotImplementedError

    def archive(self, *, project_id: str, source_id: str) -> SourceDocument:
        raise NotImplementedError

    def update_language(
        self,
        *,
        project_id: str,
        source_id: str,
        language: str,
        expected_updated_at: str,
    ) -> SourceDocument:
        raise NotImplementedError


class SQLiteSourceDocumentStore(SourceStore):
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
                CREATE TABLE IF NOT EXISTS source_documents (
                  project_id TEXT NOT NULL,
                  id TEXT NOT NULL,
                  relative_path TEXT NOT NULL,
                  normalized_path TEXT NOT NULL,
                  checksum_sha256 TEXT NOT NULL,
                  extraction_status TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  payload_json TEXT NOT NULL,
                  PRIMARY KEY (project_id, id),
                  UNIQUE (project_id, normalized_path, checksum_sha256)
                )
                """
            )
            self._connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_source_documents_project
                ON source_documents(project_id, extraction_status, updated_at, id)
                """
            )
            self._connection.commit()

    def create_or_get(self, document: SourceDocument) -> SourceStoreWriteResult:
        normalized_path = normalize_source_path(document.relative_path)
        with self._lock:
            existing = self._get_by_import_key(
                project_id=document.project_id,
                normalized_path=normalized_path,
                checksum_sha256=document.checksum_sha256,
            )
            if existing is not None:
                recovered = self._retry_document(existing=existing, incoming=document)
                if recovered is not None:
                    self._update(recovered, normalized_path=normalized_path)
                    self._connection.commit()
                    return SourceStoreWriteResult(
                        document=recovered,
                        created=False,
                        updated=True,
                    )
                return SourceStoreWriteResult(
                    document=existing,
                    created=False,
                    updated=False,
                )

            if self._id_exists(project_id=document.project_id, source_id=document.id):
                raise ContractError(
                    f"Duplicate SourceDocument id in project {document.project_id}: {document.id}"
                )

            try:
                self._insert(document, normalized_path=normalized_path)
                self._connection.commit()
            except sqlite3.IntegrityError as exc:
                self._connection.rollback()
                concurrent = self._get_by_import_key(
                    project_id=document.project_id,
                    normalized_path=normalized_path,
                    checksum_sha256=document.checksum_sha256,
                )
                if concurrent is not None:
                    recovered = self._retry_document(existing=concurrent, incoming=document)
                    if recovered is not None:
                        self._update(recovered, normalized_path=normalized_path)
                        self._connection.commit()
                        return SourceStoreWriteResult(
                            document=recovered,
                            created=False,
                            updated=True,
                        )
                    return SourceStoreWriteResult(
                        document=concurrent,
                        created=False,
                        updated=False,
                    )
                raise ContractError(f"Could not persist SourceDocument: {document.id}") from exc
            return SourceStoreWriteResult(document=document, created=True, updated=False)

    @staticmethod
    def _retry_document(
        *,
        existing: SourceDocument,
        incoming: SourceDocument,
    ) -> SourceDocument | None:
        recovers_failed = (
            existing.extraction_status == "failed"
            and incoming.extraction_status == "ready"
        )
        restores_archived = (
            existing.extraction_status == "archived"
            and incoming.extraction_status == "ready"
        )
        if not (recovers_failed or restores_archived):
            return None
        return SourceDocument.model_validate(
            {
                **incoming.model_dump(),
                "id": existing.id,
                "created_at": existing.created_at,
                "updated_at": incoming.updated_at or utc_now(),
            }
        )

    def get(self, *, project_id: str, source_id: str) -> SourceDocument:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT payload_json FROM source_documents
                WHERE project_id = ? AND id = ?
                """,
                (project_id, source_id),
            ).fetchone()
            if row is None:
                raise ContractError(f"SourceDocument not found: {source_id}")
            return SourceDocument.model_validate_json(row["payload_json"])

    def list(
        self,
        *,
        project_id: str,
        include_archived: bool = False,
    ) -> list[SourceDocumentSummary]:
        query = """
            SELECT payload_json FROM source_documents
            WHERE project_id = ?
        """
        params: list[str] = [project_id]
        if not include_archived:
            query += " AND extraction_status != ?"
            params.append("archived")
        query += " ORDER BY relative_path COLLATE NOCASE ASC, id ASC"
        with self._lock:
            rows = self._connection.execute(query, params).fetchall()
        return [
            SourceDocument.model_validate_json(row["payload_json"]).to_summary()
            for row in rows
        ]

    def archive(self, *, project_id: str, source_id: str) -> SourceDocument:
        with self._lock:
            document = self.get(project_id=project_id, source_id=source_id)
            if document.extraction_status == "archived":
                return document
            archived = SourceDocument.model_validate(
                {
                    **document.model_dump(),
                    "extraction_status": "archived",
                    "updated_at": utc_now(),
                }
            )
            self._update(
                archived,
                normalized_path=normalize_source_path(archived.relative_path),
            )
            self._connection.commit()
            return archived

    def update_language(
        self,
        *,
        project_id: str,
        source_id: str,
        language: str,
        expected_updated_at: str,
    ) -> SourceDocument:
        with self._lock:
            document = self.get(project_id=project_id, source_id=source_id)
            if document.updated_at != expected_updated_at:
                raise ContractError(
                    "SourceDocument changed since it was loaded; refresh and retry."
                )
            if document.language == language:
                return document
            updated = SourceDocument.model_validate(
                {
                    **document.model_dump(),
                    "language": language,
                    "updated_at": _next_updated_at(document.updated_at),
                }
            )
            self._update(
                updated,
                normalized_path=normalize_source_path(updated.relative_path),
            )
            self._connection.commit()
            return updated

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _get_by_import_key(
        self,
        *,
        project_id: str,
        normalized_path: str,
        checksum_sha256: str,
    ) -> SourceDocument | None:
        row = self._connection.execute(
            """
            SELECT payload_json FROM source_documents
            WHERE project_id = ? AND normalized_path = ? AND checksum_sha256 = ?
            """,
            (project_id, normalized_path, checksum_sha256),
        ).fetchone()
        if row is None:
            return None
        return SourceDocument.model_validate_json(row["payload_json"])

    def _id_exists(self, *, project_id: str, source_id: str) -> bool:
        row = self._connection.execute(
            """
            SELECT 1 FROM source_documents
            WHERE project_id = ? AND id = ?
            """,
            (project_id, source_id),
        ).fetchone()
        return row is not None

    def _insert(self, document: SourceDocument, *, normalized_path: str) -> None:
        self._connection.execute(
            """
            INSERT INTO source_documents
            (project_id, id, relative_path, normalized_path, checksum_sha256, extraction_status,
             created_at, updated_at, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document.project_id,
                document.id,
                document.relative_path,
                normalized_path,
                document.checksum_sha256,
                document.extraction_status,
                document.created_at,
                document.updated_at,
                document.model_dump_json(),
            ),
        )

    def _update(self, document: SourceDocument, *, normalized_path: str) -> None:
        self._connection.execute(
            """
            UPDATE source_documents
            SET relative_path = ?, normalized_path = ?, checksum_sha256 = ?, extraction_status = ?,
                updated_at = ?, payload_json = ?
            WHERE project_id = ? AND id = ?
            """,
            (
                document.relative_path,
                normalized_path,
                document.checksum_sha256,
                document.extraction_status,
                document.updated_at,
                document.model_dump_json(),
                document.project_id,
                document.id,
            ),
        )


def normalize_source_path(relative_path: str) -> str:
    normalized = unicodedata.normalize("NFC", relative_path.strip().replace("\\", "/"))
    if not normalized or normalized.startswith("/"):
        raise ContractError("SourceDocument relative_path must be relative")
    if len(normalized) >= 2 and normalized[1] == ":":
        raise ContractError("SourceDocument relative_path must not contain a drive prefix")
    raw_parts = normalized.split("/")
    if any(part in {".", ".."} for part in raw_parts):
        raise ContractError("SourceDocument relative_path must remain inside the source root")
    parts = [part for part in raw_parts if part]
    if not parts:
        raise ContractError("SourceDocument relative_path must be relative")
    return "/".join(parts).casefold()


# Compatibility name for early SG-018 callers; new integrations should use the explicit class name.
SQLiteSourceStore = SQLiteSourceDocumentStore


def _next_updated_at(previous: str) -> str:
    current = utc_now()
    if current > previous:
        return current
    parsed = datetime.fromisoformat(previous.replace("Z", "+00:00"))
    return (parsed.astimezone(UTC) + timedelta(seconds=1)).isoformat().replace(
        "+00:00", "Z"
    )
