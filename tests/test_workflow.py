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


def test_scene_generation_workflow_runs_without_canon_pollution():
    graph = build_fantasy_demo_graph()
    draft_store = SQLiteDraftStore()
    workflow = SceneGenerationWorkflow(
        context_builder=ContextPackBuilder(graph, draft_store),
        writer=RuleBasedSceneWriter(draft_store),
        checker=RuleBasedContinuityChecker(),
        extractor=RuleBasedStateExtractor(),
    )

    result = workflow.run(project_id=PROJECT_ID, scene_id=SCENE_ID)

    assert result.context_pack.contract_version == "context_pack_v1"
    assert result.draft.version == 1
    assert result.continuity_report.contract_version == "continuity_report_v1"
    assert result.continuity_report.status == "pass"
    assert result.candidates == []
    assert not any(
        relation.properties.get("candidate_fact_id") for relation in graph.relationships.values()
    )


def test_scene_generation_workflow_persists_completed_run_checkpoint():
    graph = build_fantasy_demo_graph()
    draft_store = SQLiteDraftStore()
    workflow_store = SQLiteWorkflowStore()
    workflow = SceneGenerationWorkflow(
        context_builder=ContextPackBuilder(graph, draft_store),
        writer=RuleBasedSceneWriter(draft_store),
        checker=RuleBasedContinuityChecker(),
        extractor=RuleBasedStateExtractor(),
        workflow_store=workflow_store,
    )

    result = workflow.run(project_id=PROJECT_ID, scene_id=SCENE_ID)
    stored = workflow_store.get(result.workflow_run.id)

    assert stored.contract_version == "workflow_run_v1"
    assert stored.status == "completed"
    assert stored.current_step == "END"
    assert stored.review_payload.contract_version == "review_payload_v1"
    assert stored.review_payload.status == "none"
    assert [step.status for step in stored.steps] == [
        "completed",
        "completed",
        "completed",
        "completed",
        "skipped",
    ]


def test_scene_generation_workflow_records_review_payload_when_candidates_exist():
    graph = build_fantasy_demo_graph()
    draft_store = SQLiteDraftStore()
    workflow_store = SQLiteWorkflowStore()
    review_service = ReviewService(InMemoryCandidateStore(), graph)
    workflow = SceneGenerationWorkflow(
        context_builder=ContextPackBuilder(graph, draft_store),
        writer=FactMarkerSceneWriter(draft_store),
        checker=RuleBasedContinuityChecker(),
        extractor=RuleBasedStateExtractor(),
        workflow_store=workflow_store,
        review_service=review_service,
    )

    result = workflow.run(project_id=PROJECT_ID, scene_id=SCENE_ID)
    stored = workflow_store.get(result.workflow_run.id)

    assert stored.status == "awaiting_review"
    assert stored.current_step == "human_review"
    assert stored.review_payload.contract_version == "review_payload_v1"
    assert stored.review_payload.status == "pending"
    assert stored.review_payload.source_draft_id == result.draft.id
    assert stored.review_payload.candidate_ids == [result.candidates[0].id]
    assert review_service.pending(project_id=PROJECT_ID)[0].id == result.candidates[0].id
    assert not any(
        relation.properties.get("candidate_fact_id") for relation in graph.relationships.values()
    )


def test_scene_generation_workflow_needs_revision_does_not_extract_state():
    graph = build_fantasy_demo_graph()
    draft_store = SQLiteDraftStore()
    workflow_store = SQLiteWorkflowStore()
    review_service = ReviewService(InMemoryCandidateStore(), graph)
    workflow = SceneGenerationWorkflow(
        context_builder=ContextPackBuilder(graph, draft_store),
        writer=NeedsRevisionSceneWriter(draft_store),
        checker=RuleBasedContinuityChecker(),
        extractor=RuleBasedStateExtractor(),
        workflow_store=workflow_store,
        review_service=review_service,
    )

    result = workflow.run(project_id=PROJECT_ID, scene_id=SCENE_ID)
    stored = workflow_store.get(result.workflow_run.id)

    assert result.continuity_report.status == "needs_revision"
    assert result.candidates == []
    assert stored.status == "needs_revision"
    assert review_service.pending(project_id=PROJECT_ID) == []


def test_scene_generation_workflow_resume_review_after_human_decision():
    graph = build_fantasy_demo_graph()
    draft_store = SQLiteDraftStore()
    workflow_store = SQLiteWorkflowStore()
    review_service = ReviewService(InMemoryCandidateStore(), graph)
    workflow = SceneGenerationWorkflow(
        context_builder=ContextPackBuilder(graph, draft_store),
        writer=FactMarkerSceneWriter(draft_store),
        checker=RuleBasedContinuityChecker(),
        extractor=RuleBasedStateExtractor(),
        workflow_store=workflow_store,
        review_service=review_service,
    )
    result = workflow.run(project_id=PROJECT_ID, scene_id=SCENE_ID)

    still_waiting = workflow.resume_review(result.workflow_run.id)
    assert still_waiting.status == "awaiting_review"

    review_service.reject(result.candidates[0].id, reviewer="author", note="Not canon.")
    completed = workflow.resume_review(result.workflow_run.id)
    completed_again = workflow.resume_review(result.workflow_run.id)

    assert completed.status == "completed"
    assert completed.current_step == "END"
    assert completed.review_payload.status == "none"
    assert completed_again == completed
    assert not any(
        relation.properties.get("candidate_fact_id") for relation in graph.relationships.values()
    )


class FactMarkerSceneWriter(RuleBasedSceneWriter):
    def draft(self, context_pack):
        marker = (
            f"[[fact:id=fact_workflow_review;fact_type=ItemState;subject={ITEM_ID};"
            f"relation=LOCATED_AT;object={LOCATION_ID};confidence=0.95]]"
        )
        return DraftResult(
            text=f"bell rings early. half black wax seal. {marker}",
            summary="Workflow review payload draft.",
            self_check=["Generated a test CandidateFact marker."],
        )


class NeedsRevisionSceneWriter(RuleBasedSceneWriter):
    def draft(self, context_pack):
        marker = (
            f"[[fact:id=fact_should_not_extract;fact_type=ItemState;subject={ITEM_ID};"
            f"relation=LOCATED_AT;object={LOCATION_ID};confidence=0.95]]"
        )
        return DraftResult(
            text=f"bell rings early. {marker}",
            summary="Missing required element while containing a marker.",
            self_check=["This should require revision before extraction."],
        )
