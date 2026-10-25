"""Bounded background planning jobs; API actions remain explicit and scope checked."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from threading import Event

from fastapi import HTTPException

from storygraph.core.agent_config import AgentPermissionLevel, settings_for_task
from storygraph.core.errors import ContractError, GraphStoreError
from storygraph.models.longform import LongformApplyRequest
from storygraph.models.planning_run import PlanningRunControl, PlanningRunRequest, PlanningRunResume
from storygraph.services.planning_run import PlanningExecution, PlanningRunService
from storygraph.stores.planning_run_store import SQLitePlanningRunStore


def register_planning_run_routes(
    app, *, graph, settings, proposals, require_permission, require_llm,
    provider_factory, persist_snapshot,
):
    from storygraph.services.book_bundle import apply_book_bundle

    runs = SQLitePlanningRunStore(proposals)
    closing = Event()

    def execution(task):
        if closing.is_set():
            raise GraphStoreError("planning_shutdown", "Planning backend is stopping.")
        require_permission(AgentPermissionLevel.READ_GENERATE)
        runtime = settings_for_task(settings, task)
        require_llm(runtime)
        identity = {
            "endpoint": runtime.llm_base_url, "model_execution": runtime.model_execution,
            "thinking_mode": getattr(runtime, "llm_thinking_mode", "provider_default"),
            "json_mode": runtime.llm_json_mode,
            "preset": runtime.agent_preset.model_dump(),
        }
        fingerprint = hashlib.sha256(json.dumps(identity, ensure_ascii=False,
                                                 sort_keys=True).encode()).hexdigest()
        return PlanningExecution(
            provider=provider_factory(runtime), model=runtime.llm_model,
            agent_preset=runtime.agent_preset, model_execution=runtime.model_execution,
            configuration_fingerprint=fingerprint,
        )

    service = PlanningRunService(graph=graph, proposals=proposals, runs=runs,
                                 provider_factory=execution)
    service.recover_interrupted()
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="storygraph-planning")
    app.state.planning_run_service = service
    app.state.planning_run_store = runs
    app.state.planning_futures = {}

    def dispatch(run):
        payload = {"run": run.model_dump(mode="json")}
        app.state.planning_futures[run.id] = executor.submit(service.execute, run.id)
        return payload

    def close_planning_executor():
        # An already running external call can finish its checkpoint. It must not
        # be duplicated automatically by another application instance.
        closing.set()
        for run_id in tuple(app.state.planning_futures):
            for _ in range(3):
                try:
                    run = runs.get(run_id)
                    if run.status not in {"queued", "running"}:
                        break
                    service.stop(run.project_id, run_id,
                                 PlanningRunControl(expected_version=run.version))
                    break
                except GraphStoreError:
                    continue
        executor.shutdown(wait=False, cancel_futures=True)

    app.state.close_planning_executor = close_planning_executor

    def failure(exc):
        if isinstance(exc, HTTPException):
            return exc
        if isinstance(exc, GraphStoreError) and exc.category == "not_found":
            return HTTPException(404, detail="Planning run is unavailable in this project.")
        if isinstance(exc, (ContractError, GraphStoreError, ValueError, KeyError)):
            category = "planning_run_invalid"
            if isinstance(exc, GraphStoreError) and exc.category.startswith(("planning_", "longform_")):
                category = exc.category
            return HTTPException(409, detail={"category": category,
                "message": "Planning input is stale, incomplete or requires an explicit recovery choice."})
        return HTTPException(500, detail={"category": "planning_run_failed",
                                          "message": "Planning could not continue; inspect its saved status."})

    @app.post("/projects/{project_id}/planning-runs")
    def create_run(project_id: str, request: PlanningRunRequest):
        require_permission(AgentPermissionLevel.READ_GENERATE)
        try:
            return dispatch(service.create(project_id, request))
        except Exception as exc:
            raise failure(exc) from None

    @app.get("/projects/{project_id}/planning-runs")
    def list_runs(project_id: str):
        require_permission(AgentPermissionLevel.READ_ONLY)
        try:
            return {"runs": [run.model_dump(mode="json") for run in service.list(project_id)]}
        except Exception as exc:
            raise failure(exc) from None

    @app.get("/projects/{project_id}/planning-runs/{run_id}")
    def get_run(project_id: str, run_id: str):
        require_permission(AgentPermissionLevel.READ_ONLY)
        try:
            return {"run": service.get(project_id, run_id).model_dump(mode="json")}
        except Exception as exc:
            raise failure(exc) from None

    @app.post("/projects/{project_id}/planning-runs/{run_id}/stop")
    def stop_run(project_id: str, run_id: str, request: PlanningRunControl):
        require_permission(AgentPermissionLevel.READ_GENERATE)
        try:
            return {"run": service.stop(project_id, run_id, request).model_dump(mode="json")}
        except Exception as exc:
            raise failure(exc) from None

    @app.post("/projects/{project_id}/planning-runs/{run_id}/copy-blueprint")
    def copy_blueprint(project_id: str, run_id: str, request: PlanningRunControl):
        require_permission(AgentPermissionLevel.READ_GENERATE)
        try:
            return {"proposal": service.copy_blueprint(project_id, run_id, request).model_dump(mode="json")}
        except Exception as exc:
            raise failure(exc) from None

    @app.post("/projects/{project_id}/planning-runs/{run_id}/resume")
    def resume_run(project_id: str, run_id: str, request: PlanningRunResume):
        require_permission(AgentPermissionLevel.READ_GENERATE)
        try:
            return dispatch(service.resume(project_id, run_id, request))
        except Exception as exc:
            raise failure(exc) from None

    @app.get("/projects/{project_id}/planning-runs/{run_id}/reviews/{review_id}")
    def get_review(project_id: str, run_id: str, review_id: str):
        require_permission(AgentPermissionLevel.READ_ONLY)
        try:
            return service.review(project_id, run_id, review_id)
        except Exception as exc:
            raise failure(exc) from None

    @app.post("/projects/{project_id}/proposals/{proposal_id}/apply/longform-book")
    def apply_book(project_id: str, proposal_id: str, request: LongformApplyRequest):
        require_permission(AgentPermissionLevel.FULL)
        try:
            return apply_book_bundle(
                graph=graph, proposals=proposals, runs=runs, project_id=project_id,
                proposal_id=proposal_id, request=request, persist_snapshot=persist_snapshot,
            )
        except Exception as exc:
            raise failure(exc) from None
