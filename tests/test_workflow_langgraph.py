import importlib.util

import pytest
from fastapi.testclient import TestClient

from apps.api.main import create_app
from storygraph.core.config import StoryGraphSettings
from storygraph.demo import ITEM_ID, LOCATION_ID, PROJECT_ID, SCENE_ID, build_fantasy_demo_graph
from storygraph.services import (
    ContextPackBuilder,
    ReviewService,
    RuleBasedContinuityChecker,
    RuleBasedSceneWriter,
    RuleBasedStateExtractor,
)
from storygraph.services.scene_writer import DraftResult
from storygraph.stores.candidate_store import InMemoryCandidateStore
from storygraph.stores.draft_store import SQLiteDraftStore
from storygraph.stores.workflow_store import SQLiteWorkflowStore
from storygraph.workflows import SceneGenerationWorkflow


pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("langgraph") is None,
    reason="LangGraph optional dependency is not installed",
)


def test_langgraph_scene_generation_persists_workflow_projection(tmp_path):
    graph = build_fantasy_demo_graph()
    draft_store = SQLiteDraftStore()
    workflow_store = SQLiteWorkflowStore()
    workflow = SceneGenerationWorkflow(
        context_builder=ContextPackBuilder(graph, draft_store),
        writer=RuleBasedSceneWriter(draft_store),
        checker=RuleBasedContinuityChecker(),
        extractor=RuleBasedStateExtractor(),
        workflow_store=workflow_store,
        runtime_kind="langgraph",
        checkpoint_path=str(tmp_path / "langgraph.sqlite"),
    )

    try:
        result = workflow.run(project_id=PROJECT_ID, scene_id=SCENE_ID)
    finally:
        workflow.close()

    stored = workflow_store.get(result.workflow_run.id)
    assert stored.status == "completed"
    assert stored.current_step == "END"
    assert [step.status for step in stored.steps] == [
        "completed",
        "completed",
        "completed",
        "completed",
        "skipped",
    ]


def test_langgraph_review_interrupt_resumes_across_runtime_instances(tmp_path):
    graph = build_fantasy_demo_graph()
    draft_store = SQLiteDraftStore()
    candidate_store = InMemoryCandidateStore()
    workflow_store = SQLiteWorkflowStore()
    review_service = ReviewService(candidate_store, graph)
    checkpoint_path = tmp_path / "langgraph.sqlite"

    first_workflow = _langgraph_workflow(
        graph=graph,
        draft_store=draft_store,
        workflow_store=workflow_store,
        review_service=review_service,
        checkpoint_path=checkpoint_path,
    )
    try:
        result = first_workflow.run(project_id=PROJECT_ID, scene_id=SCENE_ID)
    finally:
        first_workflow.close()

    assert result.workflow_run.status == "awaiting_review"
    assert result.workflow_run.review_payload.status == "pending"
    assert result.candidates[0].review.status == "pending"

    review_service.reject(result.candidates[0].id, reviewer="author", note="Not canon.")
    second_workflow = _langgraph_workflow(
        graph=graph,
        draft_store=draft_store,
        workflow_store=workflow_store,
        review_service=review_service,
        checkpoint_path=checkpoint_path,
    )
    try:
        completed = second_workflow.resume_review(result.workflow_run.id)
    finally:
        second_workflow.close()

    assert completed.status == "completed"
    assert completed.current_step == "END"
    assert completed.review_payload.status == "none"
    assert not any(
        relation.properties.get("candidate_fact_id") for relation in graph.relationships.values()
    )


def test_api_can_use_configured_langgraph_runtime(tmp_path):
    settings = StoryGraphSettings(tmp_path)
    settings.workflow_runtime = "langgraph"
    client = TestClient(create_app(settings))

    health = client.get("/health")
    response = client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/runs/scene-generation")

    assert health.status_code == 200
    assert health.json()["workflow_runtime"] == "langgraph"
    assert response.status_code == 200
    assert response.json()["workflow_run"]["status"] == "completed"
    assert settings.workflow_checkpoint_path.exists()


def _langgraph_workflow(
    *,
    graph,
    draft_store: SQLiteDraftStore,
    workflow_store: SQLiteWorkflowStore,
    review_service: ReviewService,
    checkpoint_path,
) -> SceneGenerationWorkflow:
    return SceneGenerationWorkflow(
        context_builder=ContextPackBuilder(graph, draft_store),
        writer=FactMarkerSceneWriter(draft_store),
        checker=RuleBasedContinuityChecker(),
        extractor=RuleBasedStateExtractor(),
        workflow_store=workflow_store,
        review_service=review_service,
        runtime_kind="langgraph",
        checkpoint_path=str(checkpoint_path),
    )


class FactMarkerSceneWriter(RuleBasedSceneWriter):
    def draft(self, context_pack):
        marker = (
            f"[[fact:id=fact_langgraph_review;fact_type=ItemState;subject={ITEM_ID};"
            f"relation=LOCATED_AT;object={LOCATION_ID};confidence=0.95]]"
        )
        return DraftResult(
            text=f"bell rings early. half black wax seal. {marker}",
            summary="LangGraph review payload draft.",
            self_check=["Generated a test CandidateFact marker."],
        )
