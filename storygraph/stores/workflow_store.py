"""SQLite workflow checkpoint store."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import RLock

from storygraph.core.errors import ContractError
from storygraph.models.workflow import WorkflowRun


class SQLiteWorkflowStore:
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
                CREATE TABLE IF NOT EXISTS workflow_runs (
                  id TEXT PRIMARY KEY,
                  workflow_name TEXT NOT NULL,
                  project_id TEXT NOT NULL,
                  output_language TEXT,
                  scene_id TEXT,
                  status TEXT NOT NULL,
                  current_step TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  payload_json TEXT NOT NULL
                )
                """
            )
            self._ensure_column("workflow_runs", "output_language", "TEXT")
            self._connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_workflow_runs_project
                ON workflow_runs(project_id, status, updated_at)
                """
            )
            self._connection.commit()

    def save(self, run: WorkflowRun) -> WorkflowRun:
        with self._lock:
            existing_language = self._stored_output_language(run.id)
            if existing_language is _MISSING and run.output_language is None:
                raise ContractError("New WorkflowRun records require output_language")
            if (
                existing_language is not _MISSING
                and existing_language is not None
                and run.output_language != existing_language
            ):
                raise ContractError("WorkflowRun output_language is immutable")
            cursor = self._connection.execute(
                """
                INSERT INTO workflow_runs
                (id, workflow_name, project_id, output_language, scene_id, status, current_step, created_at, updated_at, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  workflow_name = excluded.workflow_name,
                  project_id = excluded.project_id,
                  output_language = excluded.output_language,
                  scene_id = excluded.scene_id,
                  status = excluded.status,
                  current_step = excluded.current_step,
                  updated_at = excluded.updated_at,
                  payload_json = excluded.payload_json
                WHERE workflow_runs.output_language IS NULL
                   OR workflow_runs.output_language = excluded.output_language
                """,
                (
                    run.id,
                    run.workflow_name,
                    run.project_id,
                    run.output_language,
                    run.scene_id,
                    run.status,
                    run.current_step,
                    run.created_at,
                    run.updated_at,
                    run.model_dump_json(),
                ),
            )
            if cursor.rowcount != 1:
                self._connection.rollback()
                raise ContractError("WorkflowRun output_language is immutable")
            self._connection.commit()
            return run

    def get(self, run_id: str) -> WorkflowRun:
        with self._lock:
            row = self._connection.execute(
                "SELECT payload_json, output_language FROM workflow_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
            if row is None:
                raise ContractError(f"WorkflowRun not found: {run_id}")
            return self._row_to_run(row)

    def list(
        self,
        *,
        project_id: str | None = None,
        status: str | None = None,
    ) -> list[WorkflowRun]:
        query = "SELECT payload_json, output_language FROM workflow_runs"
        clauses: list[str] = []
        params: list[str] = []
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY updated_at DESC, id ASC"
        with self._lock:
            rows = self._connection.execute(query, params).fetchall()
            return [self._row_to_run(row) for row in rows]

    def _stored_output_language(self, run_id: str) -> str | None | object:
        row = self._connection.execute(
            "SELECT output_language FROM workflow_runs WHERE id = ? LIMIT 1",
            (run_id,),
        ).fetchone()
        return _MISSING if row is None else row["output_language"]

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        columns = {
            row["name"]
            for row in self._connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in columns:
            self._connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    @staticmethod
    def _row_to_run(row: sqlite3.Row) -> WorkflowRun:
        payload = json.loads(row["payload_json"])
        if payload.get("output_language") is None and row["output_language"] is not None:
            payload["output_language"] = row["output_language"]
            payload["language_inferred"] = False
        return WorkflowRun.model_validate(payload)

    def close(self) -> None:
        with self._lock:
            self._connection.close()


_MISSING = object()
