from storygraph.demo import LOCATION_ID, PROJECT_ID, SCENE_ID, SECRET_ID, build_fantasy_demo_graph
from storygraph.services.context_pack_builder import ContextPackBuilder


def test_context_pack_matches_contract_and_knowledge_boundary():
    graph = build_fantasy_demo_graph()
    pack = ContextPackBuilder(graph).build(project_id=PROJECT_ID, scene_id=SCENE_ID)

    assert pack.contract_version == "context_pack_v1"
    assert pack.project_id == PROJECT_ID
    assert pack.scene_id == SCENE_ID
    assert pack.budget.priority_order == ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7"]
    assert any(SECRET_ID in boundary.does_not_know for boundary in pack.knowledge_boundaries)
    assert "full chapter" not in pack.model_dump_json().lower()


def test_context_pack_budget_trims_style_samples_before_hard_context():
    graph = build_fantasy_demo_graph()
    graph.update_node(
        SCENE_ID,
        {
            "retrieved_style_samples": [
                "A long style sample with rhythm and dialogue notes. " * 30,
                "Another long style sample that should be dropped first. " * 30,
            ],
            "style_sample_refs": ["style_sample_001", "style_sample_002"],
        },
        reviewer="author",
        rationale="Add style samples for budget test.",
        source_ref="test_context_pack",
    )

    pack = ContextPackBuilder(graph).build(project_id=PROJECT_ID, scene_id=SCENE_ID, target_tokens=500)

    assert pack.retrieved_style_samples == []
    assert pack.must_include == ["bell rings early", "half black wax seal"]
    assert any(SECRET_ID in boundary.does_not_know for boundary in pack.knowledge_boundaries)
    assert any(item.startswith("P6 dropped style samples") for item in pack.budget.dropped_items)
    assert pack.budget.estimated_tokens <= 500


def test_context_pack_filters_world_rules_and_foreshadowing_by_scene_scope():
    graph = build_fantasy_demo_graph()
    graph.seed_canon_node(
        node_id="worldrule_other_place",
        node_type="WorldRule",
        properties={
            "project_id": PROJECT_ID,
            "location_id": "location_far_city",
            "rule": "Far city laws do not matter in the tower scene.",
            "severity": "medium",
        },
    )
    graph.seed_canon_node(
        node_id="worldrule_tower",
        node_type="WorldRule",
        properties={
            "project_id": PROJECT_ID,
            "location_id": LOCATION_ID,
            "rule": "The tower bell mechanism is sealed after midnight.",
            "severity": "high",
        },
    )
    graph.seed_canon_node(
        node_id="foreshadowing_other_place",
        node_type="Foreshadowing",
        properties={
            "project_id": PROJECT_ID,
            "location_id": "location_far_city",
            "clue_text": "A far city clue.",
            "hidden_meaning": "Not relevant here.",
            "status": "seeded",
        },
    )
    graph.seed_canon_node(
        node_id="foreshadowing_paid",
        node_type="Foreshadowing",
        properties={
            "project_id": PROJECT_ID,
            "location_id": LOCATION_ID,
            "clue_text": "Already resolved clue.",
            "hidden_meaning": "Done.",
            "status": "paid_off",
        },
    )

    pack = ContextPackBuilder(graph).build(project_id=PROJECT_ID, scene_id=SCENE_ID)

    serialized_rules = "\n".join(pack.relevant_world_rules)
    serialized_foreshadowing = "\n".join(pack.unresolved_foreshadowing)
    assert "worldrule_tower" in serialized_rules
    assert "worldrule_other_place" not in serialized_rules
    assert "foreshadowing_other_place" not in serialized_foreshadowing
    assert "foreshadowing_paid" not in serialized_foreshadowing
