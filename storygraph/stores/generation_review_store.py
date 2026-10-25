"""Immutable local semantic review evidence, isolated from canon and prose stores."""

import sqlite3
from pathlib import Path
from threading import RLock

from storygraph.models.generation_review import GenerationReviewReport


class SQLiteGenerationReviewStore:
    def __init__(self, path: str | Path = ":memory:"):
        self._lock = RLock()
        self._connection = sqlite3.connect(str(path), check_same_thread=False)
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS generation_reviews ("
            "id TEXT PRIMARY KEY, project_id TEXT NOT NULL, target_type TEXT NOT NULL, "
            "target_id TEXT NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL)"
        )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS generation_review_target ON generation_reviews "
            "(project_id, target_type, target_id, created_at)"
        )
        self._connection.commit()

    def save(self, report: GenerationReviewReport) -> GenerationReviewReport:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO generation_reviews VALUES (?, ?, ?, ?, ?, ?)",
                (report.id, report.project_id, report.target_type, report.target_id,
                 report.created_at, report.model_dump_json()),
            )
        return report

    def list(self, *, project_id: str, target_type: str, target_id: str):
        with self._lock:
            rows = self._connection.execute(
                "SELECT payload FROM generation_reviews WHERE project_id=? AND target_type=? "
                "AND target_id=? ORDER BY created_at DESC, id DESC LIMIT 50",
                (project_id, target_type, target_id),
            ).fetchall()
        return [GenerationReviewReport.model_validate_json(row[0]) for row in rows]

    def get(self, *, project_id: str, report_id: str):
        with self._lock:
            row = self._connection.execute(
                "SELECT payload FROM generation_reviews WHERE project_id=? AND id=?",
                (project_id, report_id),
            ).fetchone()
        if row is None:
            raise KeyError(report_id)
        return GenerationReviewReport.model_validate_json(row[0])
