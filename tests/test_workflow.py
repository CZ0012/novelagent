from storygraph.demo import PROJECT_ID, SCENE_ID, build_fantasy_demo_graph
from storygraph.services import (
    ContextPackBuilder,
    RuleBasedContinuityChecker,
    RuleBasedSceneWriter,
    RuleBasedStateExtractor,
)
from storygraph.stores.draft_store import SQLiteDraftStore
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

