"""Scene generation workflow facade."""

from __future__ import annotations

from storygraph.models.workflow import WorkflowRun
from storygraph.services.context_pack_builder import ContextPackBuilder
from storygraph.services.continuity_checker import RuleBasedContinuityChecker
from storygraph.services.review_service import ReviewService
from storygraph.services.scene_writer import RuleBasedSceneWriter
from storygraph.services.state_extraction import RuleBasedStateExtractor
from storygraph.stores.workflow_store import SQLiteWorkflowStore
from storygraph.workflows.scene_generation_runtime import (
    SceneGenerationRuntime,
    SceneGenerationServices,
    WorkflowRuntimeKind,
    create_scene_generation_runtime,
)
from storygraph.workflows.types import SceneRunResult


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
        runtime_kind: WorkflowRuntimeKind = "local",
        runtime: SceneGenerationRuntime | None = None,
        checkpoint_path: str | None = None,
    ) -> None:
        services = SceneGenerationServices(
            context_builder=context_builder,
            writer=writer,
            checker=checker,
            extractor=extractor,
            workflow_store=workflow_store,
            review_service=review_service,
        )
        self.runtime = runtime or create_scene_generation_runtime(
            kind=runtime_kind,
            services=services,
            checkpoint_path=checkpoint_path,
        )

    def run(self, *, project_id: str, scene_id: str) -> SceneRunResult:
        return self.runtime.run(project_id=project_id, scene_id=scene_id)

    def resume_review(self, run_id: str) -> WorkflowRun:
        return self.runtime.resume_review(run_id)

    def close(self) -> None:
        self.runtime.close()
