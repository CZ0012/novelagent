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
