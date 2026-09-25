"""SQLite-backed draft store."""

from __future__ import annotations

import sqlite3
import json
from threading import RLock
from pathlib import Path

from storygraph.core.ids import new_id
from storygraph.core.errors import ContractError
from storygraph.core.time import utc_now
from storygraph.models.draft import Draft
from storygraph.models.project import OutputLanguage


class SQLiteDraftStore:
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
                CREATE TABLE IF NOT EXISTS drafts (
                  id TEXT PRIMARY KEY,
                  project_id TEXT NOT NULL,
                  scene_id TEXT NOT NULL,
                  content_language TEXT,
                  version INTEGER NOT NULL,
                  text TEXT NOT NULL,
                  summary TEXT,
                  discarded INTEGER NOT NULL DEFAULT 0,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                )
                """
            )
            self._ensure_column("drafts", "content_language", "TEXT")
            self._ensure_column("drafts", "provenance_json", "TEXT")
            self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_drafts_scene ON drafts(project_id, scene_id, version)"
            )
            self._connection.commit()

    def create_draft(
        self,
        *,
        project_id: str,
        scene_id: str,
        content_language: OutputLanguage,
        text: str,
        summary: str | None = None,
        draft_id: str | None = None,
        provenance: dict | None = None,
    ) -> Draft:
        with self._lock:
            version = self._next_version(project_id, scene_id)
            now = utc_now()
            draft = Draft(
                id=draft_id or new_id("draft"),
                project_id=project_id,
                scene_id=scene_id,
                content_language=content_language,
                version=version,
                text=text,
                summary=summary,
                provenance=provenance,
                discarded=False,
                created_at=now,
                updated_at=now,
            )
            self._insert(draft)
            self._connection.commit()
            return draft

    def _insert(self, draft: Draft) -> None:
        self._connection.execute(
            """
                INSERT INTO drafts
                (id, project_id, scene_id, content_language, version, text, summary, discarded, created_at, updated_at, provenance_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
            (
                draft.id,
                draft.project_id,
                draft.scene_id,
                draft.content_language,
                draft.version,
                draft.text,
                draft.summary,
                int(draft.discarded),
                draft.created_at,
                draft.updated_at,
                json.dumps(draft.provenance, ensure_ascii=False) if draft.provenance else None,
            ),
        )

    def create_initial_batch(self, drafts: list[Draft]) -> list[Draft]:
        """Atomic, repeatable first drafts for newly reviewed structure only."""
        with self._lock:
            results = []
            missing = []
            for draft in drafts:
                try:
                    existing = self.get_draft(draft.id)
                except KeyError:
                    existing = None
                if existing is not None:
                    if (
                        existing.project_id != draft.project_id
                        or existing.scene_id != draft.scene_id
                        or existing.provenance != draft.provenance
                        or existing.content_language != draft.content_language
                    ):
                        raise ContractError("Composition Draft identity conflict.")
                    results.append(existing)
                else:
                    if self.list_versions(draft.project_id, draft.scene_id):
                        raise ContractError("A new scene already has an unrelated Draft.")
                    missing.append(draft)
                    results.append(draft)
            try:
                for draft in missing:
                    self._insert(draft)
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
            return results

    def adopt_source_if_current(self, draft: Draft, expected_current_draft_id: str | None) -> Draft:
        """Compare current Draft and persist exact source provenance under one lock."""
        with self._lock:
            try:
                existing = self.get_draft(draft.id)
            except KeyError:
                existing = None
            if existing:
                if (
                    existing.project_id != draft.project_id
                    or existing.scene_id != draft.scene_id
                    or existing.provenance != draft.provenance
                ):
                    raise ContractError("Source adoption identity conflict.")
                return existing
            current = self.latest_for_scene(draft.project_id, draft.scene_id)
            if (current.id if current else None) != expected_current_draft_id:
                raise ContractError(
                    "The current Draft changed; reload before adopting source text."
                )
            draft = draft.model_copy(
                update={"version": self._next_version(draft.project_id, draft.scene_id)}
            )
            try:
                self._insert(draft)
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
            return draft

    def update_draft(self, draft_id: str, *, text: str, summary: str | None = None) -> Draft:
        with self._lock:
            draft = self.get_draft(draft_id)
            now = utc_now()
            self._connection.execute(
                "UPDATE drafts SET text = ?, summary = ?, updated_at = ? WHERE id = ?",
                (text, summary if summary is not None else draft.summary, now, draft_id),
            )
            self._connection.commit()
            return self.get_draft(draft_id)

    def get_draft(self, draft_id: str) -> Draft:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM drafts WHERE id = ?", (draft_id,)
            ).fetchone()
            if row is None:
                raise KeyError(draft_id)
            return self._row_to_draft(row)

    def latest_for_scene(self, project_id: str, scene_id: str) -> Draft | None:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT * FROM drafts
                WHERE project_id = ? AND scene_id = ? AND discarded = 0
                ORDER BY version DESC
                LIMIT 1
                """,
                (project_id, scene_id),
            ).fetchone()
            return self._row_to_draft(row) if row else None

    def list_versions(self, project_id: str, scene_id: str) -> list[Draft]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM drafts
                WHERE project_id = ? AND scene_id = ?
                ORDER BY version ASC
                """,
                (project_id, scene_id),
            ).fetchall()
            return [self._row_to_draft(row) for row in rows]

    def mark_discarded(self, draft_id: str) -> Draft:
        with self._lock:
            now = utc_now()
            self._connection.execute(
                "UPDATE drafts SET discarded = 1, updated_at = ? WHERE id = ?",
                (now, draft_id),
            )
            self._connection.commit()
            return self.get_draft(draft_id)

    def delete_if_unchanged(self, draft: Draft) -> bool:
        """Delete only the exact persisted Draft supplied by its creating operation."""
        with self._lock:
            cursor = self._connection.execute(
                """
                DELETE FROM drafts
                WHERE id = ?
                  AND project_id = ?
                  AND scene_id = ?
                  AND content_language IS ?
                  AND version = ?
                  AND text = ?
                  AND summary IS ?
                  AND discarded = ?
                  AND created_at = ?
                  AND updated_at = ?
                  AND provenance_json IS ?
                """,
                (
                    draft.id,
                    draft.project_id,
                    draft.scene_id,
                    draft.content_language,
                    draft.version,
                    draft.text,
                    draft.summary,
                    int(draft.discarded),
                    draft.created_at,
                    draft.updated_at,
                    json.dumps(draft.provenance, ensure_ascii=False) if draft.provenance else None,
                ),
            )
            self._connection.commit()
            return cursor.rowcount == 1

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _next_version(self, project_id: str, scene_id: str) -> int:
        row = self._connection.execute(
            "SELECT MAX(version) AS max_version FROM drafts WHERE project_id = ? AND scene_id = ?",
            (project_id, scene_id),
        ).fetchone()
        return int(row["max_version"] or 0) + 1

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        columns = {
            row["name"]
            for row in self._connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in columns:
            self._connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    @staticmethod
    def _row_to_draft(row: sqlite3.Row) -> Draft:
        return Draft(
            id=row["id"],
            project_id=row["project_id"],
            scene_id=row["scene_id"],
            content_language=row["content_language"],
            version=row["version"],
            text=row["text"],
            summary=row["summary"],
            provenance=json.loads(row["provenance_json"]) if row["provenance_json"] else None,
            discarded=bool(row["discarded"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
