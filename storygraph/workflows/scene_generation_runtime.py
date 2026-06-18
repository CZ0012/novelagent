"""Scene generation workflow runtimes.

The local runtime is the dependency-free default. The LangGraph runtime uses a
real StateGraph when the optional `langgraph` extra is installed, while still
persisting the public `workflow_run_v1` contract through SQLiteWorkflowStore.
"""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3
from pathlib import Path
from typing import Any, Literal, Protocol, TypedDict

from storygraph.core.ids import new_id
from storygraph.core.time import utc_now
from storygraph.models.candidate import CandidateFact
from storygraph.models.context import ContextPack
from storygraph.models.continuity import ContinuityReport
from storygraph.models.draft import Draft
from storygraph.models.workflow import ReviewPayload, WorkflowRun, WorkflowStep
from storygraph.services.context_pack_builder import ContextPackBuilder
from storygraph.services.continuity_checker import RuleBasedContinuityChecker
from storygraph.services.review_service import ReviewService
from storygraph.services.scene_writer import RuleBasedSceneWriter
from storygraph.services.state_extraction import RuleBasedStateExtractor
from storygraph.stores.workflow_store import SQLiteWorkflowStore
from storygraph.workflows.types import SceneRunResult


WorkflowRuntimeKind = Literal["local", "langgraph"]


@dataclass(frozen=True)
class SceneGenerationServices:
    context_builder: ContextPackBuilder
    writer: RuleBasedSceneWriter
    checker: RuleBasedContinuityChecker
    extractor: RuleBasedStateExtractor
    workflow_store: SQLiteWorkflowStore | None = None
    review_service: ReviewService | None = None


class SceneGenerationRuntime(Protocol):
    runtime_kind: str

    def run(self, *, project_id: str, scene_id: str) -> SceneRunResult:
        ...

    def resume_review(self, run_id: str) -> WorkflowRun:
        ...

    def close(self) -> None:
        ...


class LocalSceneGenerationRuntime:
    runtime_kind = "local"

    def __init__(self, services: SceneGenerationServices) -> None:
        self.context_builder = services.context_builder
        self.writer = services.writer
        self.checker = services.checker
        self.extractor = services.extractor
        self.workflow_store = services.workflow_store
        self.review_service = services.review_service

    def run(self, *, project_id: str, scene_id: str) -> SceneRunResult:
        run = self._start_run(project_id=project_id, scene_id=scene_id)
        try:
            context_pack = self.context_builder.build(project_id=project_id, scene_id=scene_id)
        except Exception as exc:
            self._fail_run(run, current_step="build_context", exc=exc)
            raise
        run = self._complete_step(
            run,
            "build_context",
            artifact_refs={"context_pack_id": f"context_{scene_id}"},
        )
        try:
            draft = self.writer.write_and_save(context_pack)
        except Exception as exc:
            self._fail_run(run, current_step="write_draft", exc=exc)
            raise
        run = self._complete_step(run, "write_draft", artifact_refs={"draft_id": draft.id})
        try:
            report = self.checker.check(context_pack=context_pack, draft=draft)
        except Exception as exc:
            self._fail_run(run, current_step="check_continuity", exc=exc)
            raise
        run = self._complete_step(
            run,
            "check_continuity",
            artifact_refs={"draft_id": draft.id, "report_status": report.status},
        )
        candidates: list[CandidateFact] = []
        if report.status == "blocked":
            run = self._finish_run(run, status="blocked", current_step="check_continuity")
        elif report.status == "needs_revision":
            run = self._finish_run(run, status="needs_revision", current_step="check_continuity")
        else:
            try:
                candidates = self.extractor.extract(project_id=project_id, draft=draft)
                if candidates and self.review_service:
                    candidates = self.review_service.submit(candidates)
            except Exception as exc:
                self._fail_run(run, current_step="extract_state", exc=exc)
                raise
            run = self._complete_step(
                run,
                "extract_state",
                artifact_refs={"candidate_ids": [candidate.id for candidate in candidates]},
            )
            run = self._finish_after_extraction(run, candidates=candidates, draft=draft)
        return SceneRunResult(
            context_pack=context_pack,
            draft=draft,
            continuity_report=report,
            candidates=candidates,
            workflow_run=run,
        )

    def _fail_run(self, run: WorkflowRun, *, current_step: str, exc: Exception) -> WorkflowRun:
        now = utc_now()
        steps = []
        failed_seen = False
        for step in run.steps:
            if step.name == current_step:
                failed_seen = True
                steps.append(
                    step.model_copy(
                        update={
                            "status": "failed",
                            "started_at": step.started_at or now,
                            "completed_at": now,
                            "message": f"{type(exc).__name__}: {exc}",
                        }
                    )
                )
            elif failed_seen and step.status == "pending":
                steps.append(step.model_copy(update={"status": "skipped", "completed_at": now}))
            else:
                steps.append(step)
        return self._save(
            run.model_copy(
                update={
                    "status": "failed",
                    "current_step": current_step,
                    "steps": steps,
                    "updated_at": now,
                }
            )
        )

    def resume_review(self, run_id: str) -> WorkflowRun:
        if not self.workflow_store:
            raise RuntimeError("resume_review requires a workflow store")
        if not self.review_service:
            raise RuntimeError("resume_review requires a review service")
        run = self.workflow_store.get(run_id)
        if run.status != "awaiting_review":
            return run
        candidates = [
            self.review_service.candidate_store.get(candidate_id)
            for candidate_id in run.review_payload.candidate_ids
        ]
        if any(candidate.review.status == "pending" for candidate in candidates):
            return run
        return self._finish_run(
            run,
            status="completed",
            current_step="END",
            review_payload=run.review_payload.model_copy(
                update={"status": "none", "note": "Human review completed."}
            ),
        )

    def _start_run(self, *, project_id: str, scene_id: str) -> WorkflowRun:
        now = utc_now()
        run = WorkflowRun(
            id=new_id("run"),
            workflow_name="scene_generation",
            project_id=project_id,
            scene_id=scene_id,
            status="running",
            current_step="build_context",
            steps=[
                WorkflowStep(name="build_context", status="pending"),
                WorkflowStep(name="write_draft", status="pending"),
                WorkflowStep(name="check_continuity", status="pending"),
                WorkflowStep(name="extract_state", status="pending"),
                WorkflowStep(name="human_review", status="pending"),
            ],
            created_at=now,
            updated_at=now,
        )
        return self._save(run)

    def _complete_step(
        self,
        run: WorkflowRun,
        name: str,
        *,
        artifact_refs: dict | None = None,
    ) -> WorkflowRun:
        now = utc_now()
        steps = []
        next_pending_seen = False
        current_step = run.current_step
        for step in run.steps:
            if step.name == name:
                steps.append(
                    step.model_copy(
                        update={
                            "status": "completed",
                            "started_at": step.started_at or now,
                            "completed_at": now,
                            "artifact_refs": artifact_refs or {},
                        }
                    )
                )
            elif not next_pending_seen and step.status == "pending":
                next_pending_seen = True
                current_step = step.name
                steps.append(step)
            else:
                steps.append(step)
        return self._save(
            run.model_copy(update={"steps": steps, "current_step": current_step, "updated_at": now})
        )

    def _finish_after_extraction(
        self,
        run: WorkflowRun,
        *,
        candidates: list[CandidateFact],
        draft: Draft,
    ) -> WorkflowRun:
        if candidates:
            return self._finish_run(
                run,
                status="awaiting_review",
                current_step="human_review",
                review_payload=ReviewPayload(
                    status="pending",
                    candidate_ids=[candidate.id for candidate in candidates],
                    source_draft_id=draft.id,
                    note="State extraction produced CandidateFact records awaiting review.",
                ),
            )
        return self._finish_run(run, status="completed", current_step="END")

    def _finish_run(
        self,
        run: WorkflowRun,
        *,
        status: str,
        current_step: str,
        review_payload: ReviewPayload | None = None,
    ) -> WorkflowRun:
        now = utc_now()
        steps = []
        for step in run.steps:
            if status == "completed" and step.name == "human_review" and step.status == "pending":
                step_status = "completed" if run.review_payload.status == "pending" else "skipped"
                steps.append(step.model_copy(update={"status": step_status, "completed_at": now}))
            elif status == "needs_revision" and step.name in {"extract_state", "human_review"}:
                steps.append(step.model_copy(update={"status": "skipped", "completed_at": now}))
            elif status == "blocked" and step.status == "pending":
                steps.append(step.model_copy(update={"status": "skipped", "completed_at": now}))
            else:
                steps.append(step)
        return self._save(
            run.model_copy(
                update={
                    "status": status,
                    "current_step": current_step,
                    "steps": steps,
                    "review_payload": review_payload or run.review_payload,
                    "updated_at": now,
                }
            )
        )

    def _save(self, run: WorkflowRun) -> WorkflowRun:
        if self.workflow_store:
            return self.workflow_store.save(run)
        return run

    def close(self) -> None:
        return None


class SceneGenerationState(TypedDict, total=False):
    project_id: str
    scene_id: str
    run: dict[str, Any]
    context_pack: dict[str, Any]
    draft: dict[str, Any]
    continuity_report: dict[str, Any]
    candidates: list[dict[str, Any]]


class LangGraphSceneGenerationRuntime(LocalSceneGenerationRuntime):
    runtime_kind = "langgraph"

    def __init__(
        self,
        services: SceneGenerationServices,
        *,
        checkpoint_path: str | Path | None = None,
        checkpointer: Any | None = None,
    ) -> None:
        super().__init__(services)
        self._checkpoint_connection: sqlite3.Connection | None = None
        self._checkpointer = checkpointer or self._open_checkpointer(checkpoint_path)
        self._app = self._build_graph(checkpointer)

    def run(self, *, project_id: str, scene_id: str) -> SceneRunResult:
        run = self._start_run(project_id=project_id, scene_id=scene_id)
        state = self._app.invoke(
            {
                "project_id": project_id,
                "scene_id": scene_id,
                "run": run.model_dump(),
                "candidates": [],
            },
            config={"configurable": {"thread_id": run.id}},
        )
        return SceneRunResult(
            context_pack=ContextPack.model_validate(state["context_pack"]),
            draft=Draft.model_validate(state["draft"]),
            continuity_report=ContinuityReport.model_validate(state["continuity_report"]),
            candidates=[
                CandidateFact.model_validate(candidate)
                for candidate in state.get("candidates", [])
            ],
            workflow_run=WorkflowRun.model_validate(state["run"]),
        )

    def resume_review(self, run_id: str) -> WorkflowRun:
        if not self.workflow_store:
            raise RuntimeError("resume_review requires a workflow store")
        if not self.review_service:
            raise RuntimeError("resume_review requires a review service")
        run = self.workflow_store.get(run_id)
        if run.status != "awaiting_review":
            return run
        candidates = [
            self.review_service.candidate_store.get(candidate_id)
            for candidate_id in run.review_payload.candidate_ids
        ]
        if any(candidate.review.status == "pending" for candidate in candidates):
            return run
        try:
            from langgraph.types import Command
        except ImportError as exc:
            raise RuntimeError(
                "LangGraph runtime requires the optional 'langgraph' dependency."
            ) from exc
        state = self._app.invoke(
            Command(resume={"review_complete": True}),
            config={"configurable": {"thread_id": run_id}},
        )
        return WorkflowRun.model_validate(state["run"])

    def _build_graph(self, checkpointer: Any | None):
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError as exc:
            raise RuntimeError(
                "LangGraph runtime requires the optional 'langgraph' dependency. "
                "Install with `python -m pip install 'langgraph>=0.2'` or use "
                "STORYGRAPH_WORKFLOW_RUNTIME=local."
            ) from exc

        graph = StateGraph(SceneGenerationState)
        graph.add_node("build_context", self._lg_build_context)
        graph.add_node("write_draft", self._lg_write_draft)
        graph.add_node("check_continuity", self._lg_check_continuity)
        graph.add_node("extract_state", self._lg_extract_state)
        graph.add_node("finish_blocked", self._lg_finish_blocked)
        graph.add_node("finish_needs_revision", self._lg_finish_needs_revision)
        graph.add_node("finish_after_extraction", self._lg_finish_after_extraction)
        graph.add_node("human_review", self._lg_human_review)

        graph.add_edge(START, "build_context")
        graph.add_edge("build_context", "write_draft")
        graph.add_edge("write_draft", "check_continuity")
        graph.add_conditional_edges(
            "check_continuity",
            self._lg_route_after_check,
            {
                "blocked": "finish_blocked",
                "needs_revision": "finish_needs_revision",
                "pass": "extract_state",
            },
        )
        graph.add_edge("extract_state", "finish_after_extraction")
        graph.add_conditional_edges(
            "finish_after_extraction",
            self._lg_route_after_extraction,
            {
                "awaiting_review": "human_review",
                "done": END,
            },
        )
        graph.add_edge("finish_blocked", END)
        graph.add_edge("finish_needs_revision", END)
        graph.add_edge("human_review", END)
        return graph.compile(checkpointer=self._checkpointer)

    def _open_checkpointer(self, checkpoint_path: str | Path | None) -> Any:
        if checkpoint_path is None:
            try:
                from langgraph.checkpoint.memory import InMemorySaver
            except ImportError as exc:
                raise RuntimeError(
                    "LangGraph runtime requires the optional 'langgraph' dependency."
                ) from exc
            return InMemorySaver()
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
        except ImportError as exc:
            raise RuntimeError(
                "Persistent LangGraph checkpoints require `langgraph-checkpoint-sqlite`. "
                "Install the project with the `langgraph` extra or use "
                "STORYGRAPH_WORKFLOW_RUNTIME=local."
            ) from exc
        path = Path(checkpoint_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._checkpoint_connection = sqlite3.connect(str(path), check_same_thread=False)
        checkpointer = SqliteSaver(self._checkpoint_connection)
        checkpointer.setup()
        return checkpointer

    def _lg_build_context(self, state: SceneGenerationState) -> SceneGenerationState:
        run = WorkflowRun.model_validate(state["run"])
        try:
            context_pack = self.context_builder.build(
                project_id=state["project_id"],
                scene_id=state["scene_id"],
            )
        except Exception as exc:
            self._fail_run(run, current_step="build_context", exc=exc)
            raise
        run = self._complete_step(
            run,
            "build_context",
            artifact_refs={"context_pack_id": f"context_{state['scene_id']}"},
        )
        return {"run": run.model_dump(), "context_pack": context_pack.model_dump()}

    def _lg_write_draft(self, state: SceneGenerationState) -> SceneGenerationState:
        run = WorkflowRun.model_validate(state["run"])
        context_pack = ContextPack.model_validate(state["context_pack"])
        try:
            draft = self.writer.write_and_save(context_pack)
        except Exception as exc:
            self._fail_run(run, current_step="write_draft", exc=exc)
            raise
        run = self._complete_step(run, "write_draft", artifact_refs={"draft_id": draft.id})
        return {"run": run.model_dump(), "draft": draft.model_dump()}

    def _lg_check_continuity(self, state: SceneGenerationState) -> SceneGenerationState:
        run = WorkflowRun.model_validate(state["run"])
        context_pack = ContextPack.model_validate(state["context_pack"])
        draft = Draft.model_validate(state["draft"])
        try:
            report = self.checker.check(context_pack=context_pack, draft=draft)
        except Exception as exc:
            self._fail_run(run, current_step="check_continuity", exc=exc)
            raise
        run = self._complete_step(
            run,
            "check_continuity",
            artifact_refs={"draft_id": draft.id, "report_status": report.status},
        )
        return {"run": run.model_dump(), "continuity_report": report.model_dump()}

    def _lg_extract_state(self, state: SceneGenerationState) -> SceneGenerationState:
        run = WorkflowRun.model_validate(state["run"])
        draft = Draft.model_validate(state["draft"])
        try:
            candidates = self.extractor.extract(project_id=state["project_id"], draft=draft)
            if candidates and self.review_service:
                candidates = self.review_service.submit(candidates)
        except Exception as exc:
            self._fail_run(run, current_step="extract_state", exc=exc)
            raise
        run = self._complete_step(
            run,
            "extract_state",
            artifact_refs={"candidate_ids": [candidate.id for candidate in candidates]},
        )
        return {
            "run": run.model_dump(),
            "candidates": [candidate.model_dump() for candidate in candidates],
        }

    def _lg_finish_blocked(self, state: SceneGenerationState) -> SceneGenerationState:
        run = self._finish_run(
            WorkflowRun.model_validate(state["run"]),
            status="blocked",
            current_step="check_continuity",
        )
        return {"run": run.model_dump()}

    def _lg_finish_needs_revision(self, state: SceneGenerationState) -> SceneGenerationState:
        run = self._finish_run(
            WorkflowRun.model_validate(state["run"]),
            status="needs_revision",
            current_step="check_continuity",
        )
        return {"run": run.model_dump()}

    def _lg_finish_after_extraction(self, state: SceneGenerationState) -> SceneGenerationState:
        candidates = [
            CandidateFact.model_validate(candidate)
            for candidate in state.get("candidates", [])
        ]
        run = self._finish_after_extraction(
            WorkflowRun.model_validate(state["run"]),
            candidates=candidates,
            draft=Draft.model_validate(state["draft"]),
        )
        return {"run": run.model_dump()}

    def _lg_human_review(self, state: SceneGenerationState) -> SceneGenerationState:
        run = WorkflowRun.model_validate(state["run"])
        try:
            from langgraph.types import interrupt
        except ImportError as exc:
            raise RuntimeError(
                "LangGraph runtime requires the optional 'langgraph' dependency."
            ) from exc
        interrupt(run.review_payload.model_dump())
        completed = self._finish_run(
            run,
            status="completed",
            current_step="END",
            review_payload=run.review_payload.model_copy(
                update={"status": "none", "note": "Human review completed."}
            ),
        )
        return {"run": completed.model_dump()}

    def _lg_route_after_check(self, state: SceneGenerationState) -> str:
        report = ContinuityReport.model_validate(state["continuity_report"])
        if report.status == "blocked":
            return "blocked"
        if report.status == "needs_revision":
            return "needs_revision"
        return "pass"

    def _lg_route_after_extraction(self, state: SceneGenerationState) -> str:
        run = WorkflowRun.model_validate(state["run"])
        if run.status == "awaiting_review":
            return "awaiting_review"
        return "done"

    def close(self) -> None:
        if self._checkpoint_connection is not None:
            self._checkpoint_connection.close()
            self._checkpoint_connection = None


def create_scene_generation_runtime(
    *,
    kind: str,
    services: SceneGenerationServices,
    checkpoint_path: str | Path | None = None,
) -> SceneGenerationRuntime:
    normalized = kind.lower()
    if normalized == "local":
        return LocalSceneGenerationRuntime(services)
    if normalized == "langgraph":
        return LangGraphSceneGenerationRuntime(
            services,
            checkpoint_path=checkpoint_path,
        )
    raise ValueError(f"Unknown workflow runtime: {kind}")
