import json
import sqlite3

import pytest

from storygraph.core.errors import ContractError
from storygraph.core.time import utc_now
from storygraph.models.workflow import WorkflowRun, WorkflowStep
from storygraph.stores.workflow_store import SQLiteWorkflowStore


def test_sqlite_workflow_store_round_trip(tmp_path):
    store_path = tmp_path / "workflow.sqlite"
    now = utc_now()
    run = WorkflowRun(
        id="run_persisted",
        workflow_name="scene_generation",
        project_id="project_001",
        output_language="zh-CN",
        scene_id="scene_001",
        status="running",
        current_step="build_context",
        steps=[WorkflowStep(name="build_context", status="running", started_at=now)],
        created_at=now,
        updated_at=now,
    )

    first = SQLiteWorkflowStore(store_path)
    first.save(run)
    second = SQLiteWorkflowStore(store_path)

    assert second.get("run_persisted") == run
    assert second.list(project_id="project_001")[0] == run


def test_sqlite_workflow_store_missing_run_raises_contract_error():
    store = SQLiteWorkflowStore()

    try:
        store.get("missing")
    except ContractError as exc:
        assert "WorkflowRun not found" in str(exc)
    else:
        raise AssertionError("Expected missing WorkflowRun to raise ContractError")


def test_workflow_run_language_snapshot_is_immutable(tmp_path):
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    now = utc_now()
    run = WorkflowRun(
        id="run_frozen",
        workflow_name="scene_generation",
        project_id="project_001",
        output_language="zh-CN",
        status="running",
        created_at=now,
        updated_at=now,
    )
    store.save(run)

    with pytest.raises(ContractError, match="output_language is immutable"):
        store.save(run.model_copy(update={"output_language": "en-US"}))
    with pytest.raises(ContractError, match="output_language is immutable"):
        store.save(run.model_copy(update={"output_language": None}))


def test_legacy_workflow_run_remains_unlabeled_until_explicitly_frozen(tmp_path):
    path = tmp_path / "legacy-workflow.sqlite"
    now = utc_now()
    payload = {
        "id": "run_legacy",
        "workflow_name": "scene_generation",
        "project_id": "project_001",
        "scene_id": "scene_001",
        "status": "running",
        "steps": [],
        "created_at": now,
        "updated_at": now,
    }
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE workflow_runs (
          id TEXT PRIMARY KEY, workflow_name TEXT NOT NULL, project_id TEXT NOT NULL,
          scene_id TEXT, status TEXT NOT NULL, current_step TEXT, created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL, payload_json TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "INSERT INTO workflow_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            payload["id"],
            payload["workflow_name"],
            payload["project_id"],
            payload["scene_id"],
            payload["status"],
            None,
            now,
            now,
            json.dumps(payload),
        ),
    )
    connection.commit()
    connection.close()

    store = SQLiteWorkflowStore(path)
    legacy = store.get("run_legacy")
    assert legacy.output_language is None
    assert legacy.language_inferred is True
    assert store.save(legacy).output_language is None

    frozen = store.save(
        legacy.model_copy(update={"output_language": "en-US", "language_inferred": False})
    )
    assert frozen.output_language == "en-US"
    with pytest.raises(ContractError, match="output_language is immutable"):
        store.save(frozen.model_copy(update={"output_language": "zh-CN"}))
