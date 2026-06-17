"""SQLite-backed draft store."""

from __future__ import annotations

import sqlite3
from threading import RLock
from pathlib import Path

from storygraph.core.ids import new_id
from storygraph.core.time import utc_now
from storygraph.models.draft import Draft


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
                  version INTEGER NOT NULL,
                  text TEXT NOT NULL,
                  summary TEXT,
                  discarded INTEGER NOT NULL DEFAULT 0,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                )
                """
            )
            self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_drafts_scene ON drafts(project_id, scene_id, version)"
            )
            self._connection.commit()

    def create_draft(
        self,
        *,
        project_id: str,
        scene_id: str,
        text: str,
        summary: str | None = None,
        draft_id: str | None = None,
    ) -> Draft:
        with self._lock:
            version = self._next_version(project_id, scene_id)
            now = utc_now()
            draft = Draft(
                id=draft_id or new_id("draft"),
                project_id=project_id,
                scene_id=scene_id,
                version=version,
                text=text,
                summary=summary,
                discarded=False,
                created_at=now,
                updated_at=now,
            )
            self._connection.execute(
                """
                INSERT INTO drafts
                (id, project_id, scene_id, version, text, summary, discarded, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft.id,
                    draft.project_id,
                    draft.scene_id,
                    draft.version,
                    draft.text,
                    draft.summary,
                    int(draft.discarded),
                    draft.created_at,
                    draft.updated_at,
                ),
            )
            self._connection.commit()
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
            row = self._connection.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
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

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _next_version(self, project_id: str, scene_id: str) -> int:
        row = self._connection.execute(
            "SELECT MAX(version) AS max_version FROM drafts WHERE project_id = ? AND scene_id = ?",
            (project_id, scene_id),
        ).fetchone()
        return int(row["max_version"] or 0) + 1

    @staticmethod
    def _row_to_draft(row: sqlite3.Row) -> Draft:
        return Draft(
            id=row["id"],
            project_id=row["project_id"],
            scene_id=row["scene_id"],
            version=row["version"],
            text=row["text"],
            summary=row["summary"],
            discarded=bool(row["discarded"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
