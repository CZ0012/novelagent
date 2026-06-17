from storygraph.demo import PROJECT_ID, SCENE_ID, SECRET_ID, build_fantasy_demo_graph
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

