"""Minimal scene workflow skeleton.

This is intentionally a typed service workflow rather than a set of autonomous chat agents.
It mirrors the LangGraph target shape while remaining runnable without external services.
"""

from __future__ import annotations

from dataclasses import dataclass

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


@dataclass(frozen=True)
class SceneRunResult:
    context_pack: ContextPack
    draft: Draft
    continuity_report: ContinuityReport
    candidates: list[CandidateFact]
    workflow_run: WorkflowRun | None = None


class SceneGenerationWorkflow:
    def __init__(
        self,
        *,
        context_builder: ContextPackBuilder,
        writer: RuleBasedSceneWriter,
        checker: RuleBasedContinuityChecker,
        extractor: RuleBasedStateExtractor,
        workflow_store: SQLiteWorkflowStore | None = None,
        review_service: ReviewService | None = None,
    ) -> None:
        self.context_builder = context_builder
        self.writer = writer
        self.checker = checker
        self.extractor = extractor
        self.workflow_store = workflow_store
        self.review_service = review_service

    def run(self, *, project_id: str, scene_id: str) -> SceneRunResult:
        run = self._start_run(project_id=project_id, scene_id=scene_id)
        context_pack = self.context_builder.build(project_id=project_id, scene_id=scene_id)
        run = self._complete_step(
            run,
            "build_context",
            artifact_refs={"context_pack_id": f"context_{scene_id}"},
        )
        draft = self.writer.write_and_save(context_pack)
        run = self._complete_step(run, "write_draft", artifact_refs={"draft_id": draft.id})
        report = self.checker.check(context_pack=context_pack, draft=draft)
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
            candidates = self.extractor.extract(project_id=project_id, draft=draft)
            if candidates and self.review_service:
                candidates = self.review_service.submit(candidates)
            run = self._complete_step(
                run,
                "extract_state",
                artifact_refs={"candidate_ids": [candidate.id for candidate in candidates]},
            )
            if candidates:
                run = self._finish_run(
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
            else:
                run = self._finish_run(run, status="completed", current_step="END")
        return SceneRunResult(
            context_pack=context_pack,
            draft=draft,
            continuity_report=report,
            candidates=candidates,
            workflow_run=run,
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
        return self._save(run.model_copy(update={"steps": steps, "current_step": current_step, "updated_at": now}))

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
