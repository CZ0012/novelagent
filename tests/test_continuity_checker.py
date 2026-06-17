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
    assert {
        "knowledge_boundary",
        "timeline",
        "location_state",
        "world_rule",
        "foreshadowing",
    }.issubset(set(report.checked_dimensions))


def test_phase5_timeline_location_relationship_and_world_rule_conflicts_are_reported():
    graph = build_fantasy_demo_graph()
    draft_store = SQLiteDraftStore()
    pack = ContextPackBuilder(graph, draft_store).build(project_id=PROJECT_ID, scene_id=SCENE_ID)
    draft = draft_store.create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
        text=(
            "At one day after the capital coup, the scene records location_far_city. "
            "character_linj LOVES character_helianya strength=0.9. "
            "worldrule_secret_reveals does not apply. "
            "Royal lineage secrets unfold without explicit scene-level reveal events. "
            "bell rings early. half black wax seal."
        ),
        summary="State conflicts draft.",
    )

    report = RuleBasedContinuityChecker().check(context_pack=pack, draft=draft)
    issue_types = {issue.issue_type for issue in report.issues}

    assert report.status == "needs_revision"
    assert {
        "timeline_conflict",
        "location_conflict",
        "relationship_conflict",
        "world_rule_conflict",
    }.issubset(issue_types)
    assert {"timeline", "location_state", "relationship_state", "world_rule"}.issubset(
        set(report.checked_dimensions)
    )


def test_phase5_foreshadowing_causality_and_pov_issues_are_reported():
    graph = build_fantasy_demo_graph()
    draft_store = SQLiteDraftStore()
    pack = ContextPackBuilder(graph, draft_store).build(project_id=PROJECT_ID, scene_id=SCENE_ID)
    pack = pack.model_copy(
        update={
            "must_include": ["half black wax seal"],
            "previous_scene_summary": "Lin Jin escaped the tower guard.",
            "unresolved_foreshadowing": [
                "foreshadowing_blue_lantern: blue lantern flickers under the gate"
            ],
        }
    )
    draft = draft_store.create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
        text=(
            "half black wax seal. The rescue works for no reason. "
            "Unbeknownst to character_linj, Helian Ya has resolved foreshadowing_blue_lantern."
        ),
        summary="Narrative continuity gaps.",
    )

    report = RuleBasedContinuityChecker().check(context_pack=pack, draft=draft)
    issue_types = {issue.issue_type for issue in report.issues}

    assert report.status == "needs_revision"
    assert {"foreshadowing_mismatch", "causal_gap", "pov_leak"}.issubset(issue_types)
    assert {"foreshadowing", "causality", "pov"}.issubset(set(report.checked_dimensions))
