"""Versioned local Writer disclosure settings, sharing Proposal Store transactions."""
from __future__ import annotations
import json
from storygraph.core.errors import ContractError
from storygraph.core.time import utc_now


class SQLiteWriterVisibilityStore:
    def __init__(self, proposals):
        self._connection = proposals._connection
        self._lock = proposals._lock
        with self._lock, self._connection:
            self._connection.execute("CREATE TABLE IF NOT EXISTS writer_visibility_policies (project_id TEXT NOT NULL, scope_key TEXT NOT NULL, version INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(project_id,scope_key,version))")

    @staticmethod
    def _scope(scene_id):
        return "project" if scene_id is None else "scene:" + scene_id

    def get(self, project_id, scene_id=None):
        with self._lock:
            row = self._connection.execute("SELECT payload FROM writer_visibility_policies WHERE project_id=? AND scope_key=? ORDER BY version DESC LIMIT 1", (project_id, self._scope(scene_id))).fetchone()
            return json.loads(row[0]) if row else None

    def effective(self, project_id, scene_id):
        override = self.get(project_id, scene_id)
        if override is not None and override["spec"] is not None:
            return override
        default = self.get(project_id)
        return default if default and default["spec"] is not None else None

    def history(self, project_id, scene_id=None):
        with self._lock:
            return [json.loads(row[0]) for row in self._connection.execute("SELECT payload FROM writer_visibility_policies WHERE project_id=? AND scope_key=? ORDER BY version", (project_id, self._scope(scene_id)))]

    def save(self, *, project_id, scene_id, expected_version, spec, source_context_sha256, configured_by="author"):
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                current = self.get(project_id, scene_id)
                version = current["version"] if current else 0
                if expected_version != version:
                    raise ContractError("writer_visibility_stale_version")
                record = {"contract_version": "writer_visibility_v1", "project_id": project_id, "scene_id": scene_id, "version": version + 1, "spec": spec, "source_context_sha256": source_context_sha256, "configured_by": configured_by, "configured_at": utc_now()}
                self._connection.execute("INSERT INTO writer_visibility_policies VALUES (?,?,?,?)", (project_id, self._scope(scene_id), version + 1, json.dumps(record, ensure_ascii=False)))
                self._connection.commit()
                return record
            except Exception:
                self._connection.rollback()
                raise
