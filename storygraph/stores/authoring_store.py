"""Project-scoped, versioned noncanon author collaboration records."""
from __future__ import annotations

import json
import hashlib

from storygraph.core.errors import ContractError


class SQLiteAuthoringStore:
    """Share the Proposal database lifecycle; never touch graph or Draft tables."""

    def __init__(self, proposals):
        self._connection = proposals._connection
        self._lock = proposals._lock
        with self._lock:
            if not hasattr(proposals, "_authoring_active_turns"):
                proposals._authoring_active_turns = {}
            self._active_turns = proposals._authoring_active_turns
        with self._lock, self._connection:
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS authoring_sessions "
                "(project_id TEXT NOT NULL, id TEXT NOT NULL, version INTEGER NOT NULL, "
                "payload TEXT NOT NULL, PRIMARY KEY(project_id,id,version))"
            )
            self._connection.execute("CREATE TABLE IF NOT EXISTS authoring_blobs (sha256 TEXT PRIMARY KEY, payload TEXT NOT NULL)")

    def _blob(self, value):
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        self._connection.execute("INSERT OR IGNORE INTO authoring_blobs VALUES (?,?)", (digest, payload))
        return digest

    def _unblob(self, digest):
        row = self._connection.execute("SELECT payload FROM authoring_blobs WHERE sha256=?", (digest,)).fetchone()
        if row is None:
            raise ContractError("authoring_journal_blob_missing")
        return json.loads(row[0])

    def _full(self, payload):
        value = dict(payload)
        refs = value.pop("_journal_v1", None)
        if refs is not None:
            value["workspace"] = self._unblob(refs["workspace"])
            for kind in ("messages", "proposals"):
                value[kind] = [self._unblob(digest) for digest in refs[kind]]
        return value

    @staticmethod
    def _window(value, message_limit=40, closed_proposal_limit=20):
        value = dict(value)
        messages, proposals = value.get("messages", []), value.get("proposals", [])
        pending = [p for p in proposals if p["status"] == "pending"]
        closed = [p for p in proposals if p["status"] != "pending"]
        chosen = {p["id"] for p in pending + (closed[-closed_proposal_limit:] if closed_proposal_limit else [])}
        value["messages"] = messages[-message_limit:] if message_limit else []
        value["proposals"] = [p for p in proposals if p["id"] in chosen]
        value["history_counts"] = {"messages": len(messages), "proposals": len(proposals)}
        value["history_has_more"] = {"messages": len(messages) > message_limit, "proposals": len(proposals) > len(chosen)}
        return value

    def get(self, project_id, session_id, *, version=None, message_limit=40, closed_proposal_limit=20, full=False):
        if type(message_limit) is not int or not 0 <= message_limit <= 400 or type(closed_proposal_limit) is not int or not 0 <= closed_proposal_limit <= 1000:
            raise ContractError("authoring_invalid_history_window")
        with self._lock:
            query = "SELECT payload FROM authoring_sessions WHERE project_id=? AND id=?"
            args = [project_id, session_id]
            if version is not None:
                query += " AND version=?"
                args.append(version)
            query += " ORDER BY version DESC LIMIT 1"
            row = self._connection.execute(query, args).fetchone()
            if row is None:
                raise ContractError("authoring_session_not_found")
            value = self._full(json.loads(row[0]))
            return value if full else self._window(value, message_limit, closed_proposal_limit)

    def list(self, project_id):
        with self._lock:
            rows = self._connection.execute(
                "SELECT s.payload FROM authoring_sessions s JOIN "
                "(SELECT id, MAX(version) version FROM authoring_sessions WHERE project_id=? GROUP BY id) v "
                "ON s.id=v.id AND s.version=v.version WHERE s.project_id=? ORDER BY s.rowid DESC",
                (project_id, project_id),
            ).fetchall()
            return [self._window(self._full(json.loads(row[0]))) for row in rows]

    def history(self, project_id, session_id):
        with self._lock:
            return [self._window(self._full(json.loads(row[0]))) for row in self._connection.execute(
                "SELECT payload FROM authoring_sessions WHERE project_id=? AND id=? ORDER BY version",
                (project_id, session_id),
            )]

    def journal_page(self, project_id, session_id, *, kind, query="", offset=0, limit=40, status=None):
        if kind not in {"messages", "proposals"} or type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100:
            raise ContractError("authoring_invalid_history_page")
        value = self.get(project_id, session_id, full=True)
        records = [r for r in value[kind] if (status is None or r.get("status") == status)
                   and query.casefold() in (r["content"] if kind == "messages" else json.dumps({k: v for k, v in r.items() if k != "model_execution"}, ensure_ascii=False)).casefold()]
        records.reverse()
        page = records[offset:offset + limit]
        more = offset + len(page) < len(records)
        return {"records": page, "total_matches": len(records), "returned_count": len(page),
                "offset": offset, "more": more, "next_offset": offset + len(page) if more else None,
                "order": "newest_first"}

    def proposal(self, project_id, session_id, proposal_id):
        value = self.get(project_id, session_id, full=True)
        proposal = next((p for p in value["proposals"] if p["id"] == proposal_id), None)
        if proposal is None:
            raise ContractError("authoring_proposal_not_found")
        return proposal

    def save(self, record, *, expected_version):
        """CAS append. Provider work happens outside this short write transaction."""
        payload = record.model_dump(mode="json") if hasattr(record, "model_dump") else record
        project_id, session_id = payload["project_id"], payload["id"]
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                row = self._connection.execute(
                    "SELECT MAX(version) FROM authoring_sessions WHERE project_id=? AND id=?",
                    (project_id, session_id),
                ).fetchone()
                current = row[0] or 0
                if current != expected_version or payload["version"] != expected_version + 1:
                    raise ContractError("authoring_stale_version")
                previous = self.get(project_id, session_id, full=True) if current else {"messages": [], "proposals": []}
                refs = {"workspace": self._blob(payload["workspace"])}
                for kind in ("messages", "proposals"):
                    prior = {r["id"]: r for r in previous[kind]}
                    incoming = {r["id"]: r for r in payload[kind]}
                    if len(incoming) != len(payload[kind]):
                        raise ContractError("authoring_duplicate_journal_identity")
                    if kind == "messages" and any(key in prior and any(prior[key].get(field) != value.get(field) for field in prior[key].keys() | value.keys()) for key, value in incoming.items()):
                        raise ContractError("authoring_message_immutable")
                    prior.update(incoming)
                    refs[kind] = [self._blob(r) for r in prior.values()]
                stored = {k: v for k, v in payload.items() if k not in {"workspace", "messages", "proposals", "history_counts", "history_has_more"}}
                stored["_journal_v1"] = refs
                self._connection.execute("INSERT INTO authoring_sessions VALUES (?,?,?,?)", (
                    project_id, session_id, payload["version"], json.dumps(stored, ensure_ascii=False),
                ))
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
        # Another request may commit after the lock is released. Return this
        # operation's exact committed version, never silently adopt the newer one.
        return self.get(project_id, session_id, version=payload["version"])
