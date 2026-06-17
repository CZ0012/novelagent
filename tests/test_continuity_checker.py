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


def test_missing_required_element_is_reported():
    graph = build_fantasy_demo_graph()
    draft_store = SQLiteDraftStore()
    pack = ContextPackBuilder(graph, draft_store).build(project_id=PROJECT_ID, scene_id=SCENE_ID)
    draft = draft_store.create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
        text="bell rings early, but the physical clue is absent.",
        summary="Incomplete draft.",
    )

    report = RuleBasedContinuityChecker().check(context_pack=pack, draft=draft)

    assert report.status == "needs_revision"
    assert any(issue.issue_type == "missing_required_element" for issue in report.issues)


def test_must_not_violate_blocks_report():
    graph = build_fantasy_demo_graph()
    draft_store = SQLiteDraftStore()
    pack = ContextPackBuilder(graph, draft_store).build(project_id=PROJECT_ID, scene_id=SCENE_ID)
    draft = draft_store.create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
        text="bell rings early. half black wax seal. Lin Jin learns secret_lineage.",
        summary="Blocked draft.",
    )

    report = RuleBasedContinuityChecker().check(context_pack=pack, draft=draft)

    assert report.status == "blocked"
    assert any(
        issue.issue_type == "unsupported_new_fact" and issue.severity == "critical"
        for issue in report.issues
    )


def test_banned_style_pattern_is_reported_as_style_drift():
    graph = build_fantasy_demo_graph()
    draft_store = SQLiteDraftStore()
    pack = ContextPackBuilder(graph, draft_store).build(project_id=PROJECT_ID, scene_id=SCENE_ID)
    draft = draft_store.create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
        text=(
            "bell rings early. half black wax seal. "
            "An omniscient explanation tells the reader everything."
        ),
        summary="Style drift draft.",
    )

    report = RuleBasedContinuityChecker().check(context_pack=pack, draft=draft)

    assert report.status == "needs_revision"
    assert "style_constraint" in report.checked_dimensions
    assert any(issue.issue_type == "style_drift" for issue in report.issues)


def test_clean_draft_passes_continuity_check():
    graph = build_fantasy_demo_graph()
    draft_store = SQLiteDraftStore()
    pack = ContextPackBuilder(graph, draft_store).build(project_id=PROJECT_ID, scene_id=SCENE_ID)
    draft = draft_store.create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
        text="bell rings early. half black wax seal. Lin Jin keeps the truth out of reach.",
        summary="Clean draft.",
    )

    report = RuleBasedContinuityChecker().check(context_pack=pack, draft=draft)

    assert report.status == "pass"
    assert report.issues == []
    assert {"knowledge_boundary", "timeline", "location_state", "world_rule", "foreshadowing"}.issubset(
        set(report.checked_dimensions)
    )
