"""Planning controls and outputs share the Proposal Store SQLite transaction."""

from storygraph.core.errors import GraphStoreError
from storygraph.core.time import utc_now
from storygraph.models.planning_run import PlanningRun
from storygraph.models.generation_review import GenerationReviewReport


class SQLitePlanningRunStore:
    def __init__(self, proposals):
        self.proposals = proposals
        self._lock = proposals._lock
        self._connection = proposals._connection
        with self._lock:
            self._connection.execute("CREATE TABLE IF NOT EXISTS planning_runs (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, version INTEGER NOT NULL, payload TEXT NOT NULL)")
            self._connection.execute("CREATE TABLE IF NOT EXISTS planning_reports (id TEXT PRIMARY KEY, run_id TEXT NOT NULL, payload TEXT NOT NULL)")
            self._connection.commit()

    def get(self, run_id):
        with self._lock:
            row = self._connection.execute("SELECT payload FROM planning_runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise GraphStoreError("not_found", "Planning run is unavailable.")
            return PlanningRun.model_validate_json(row[0])

    def list(self, project_id):
        with self._lock:
            rows = self._connection.execute("SELECT payload FROM planning_runs WHERE project_id=? ORDER BY rowid DESC", (project_id,)).fetchall()
            return [PlanningRun.model_validate_json(r[0]) for r in rows]

    def all(self):
        with self._lock:
            return [PlanningRun.model_validate_json(row[0]) for row in self._connection.execute("SELECT payload FROM planning_runs")]

    def create(self, run, *, proposal=None):
        with self._lock:
            try:
                if proposal is not None:
                    if self.proposals._exists(proposal.id):
                        raise GraphStoreError("planning_run_invalid", "Planning output identity conflicts.")
                    self.proposals._insert(proposal)
                self._connection.execute("INSERT INTO planning_runs VALUES (?,?,?,?)", (run.id, run.project_id, run.version, run.model_dump_json()))
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
        return run

    def update(self, run, expected_version, *, proposal=None, report=None):
        """CAS output+checkpoint. No separate content store or paid-call replay."""
        with self._lock:
            try:
                current = self.get(run.id)
                if current.version != expected_version or current.project_id != run.project_id:
                    raise GraphStoreError("planning_run_stale", "Planning run changed; refresh it.")
                saved = run.model_copy(update={"version": expected_version+1, "updated_at": utc_now()})
                if proposal is not None:
                    if proposal.version != 1 or self.proposals._exists(proposal.id):
                        raise GraphStoreError("planning_run_invalid", "Planning output identity conflicts.")
                    self.proposals._insert(proposal)
                if report is not None:
                    self._connection.execute("INSERT INTO planning_reports VALUES (?,?,?)", (report.id, run.id, report.model_dump_json()))
                cursor = self._connection.execute("UPDATE planning_runs SET version=?,payload=? WHERE id=? AND version=?", (saved.version, saved.model_dump_json(), run.id, expected_version))
                if cursor.rowcount != 1:
                    raise GraphStoreError("planning_run_stale", "Planning run changed; refresh it.")
                self._connection.commit()
                return saved
            except Exception:
                self._connection.rollback()
                raise

    def report(self, run_id, report_id):
        with self._lock:
            row = self._connection.execute("SELECT payload FROM planning_reports WHERE id=? AND run_id=?", (report_id, run_id)).fetchone()
            if row is None:
                raise GraphStoreError("planning_run_invalid", "Planning review is unavailable.")
            return GenerationReviewReport.model_validate_json(row[0])

    def close(self):
        # Borrowed Proposal connection belongs to its original owner.
        pass
