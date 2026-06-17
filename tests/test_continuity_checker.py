from storygraph.demo import PROJECT_ID, SCENE_ID, SECRET_ID, build_fantasy_demo_graph
from storygraph.services.context_pack_builder import ContextPackBuilder
from storygraph.services.continuity_checker import RuleBasedContinuityChecker
from storygraph.stores.draft_store import SQLiteDraftStore


def test_knowledge_boundary_violation_is_reported():
    graph = build_fantasy_demo_graph()
    draft_store = SQLiteDraftStore()
    pack = ContextPackBuilder(graph, draft_store).build(project_id=PROJECT_ID, scene_id=SCENE_ID)
    draft = draft_store.create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
        text=f"bell rings early. half black wax seal. Lin Jin suddenly knows {SECRET_ID}.",
        summary="Bad draft.",
    )

    report = RuleBasedContinuityChecker().check(context_pack=pack, draft=draft)

    assert report.status == "needs_revision"
    assert any(issue.issue_type == "knowledge_boundary_violation" for issue in report.issues)

