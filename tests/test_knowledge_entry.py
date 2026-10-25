"""Knowledge acquired during a scene cannot become opening knowledge."""

import json

import pytest

from storygraph.core.errors import ContractError
from storygraph.services.canon_snapshot import build_canon_snapshot
from storygraph.services.context_pack_builder import ContextPackBuilder
from storygraph.stores.graph_neo4j import Neo4jGraphStore
from storygraph.stores.memory_graph import InMemoryGraphStore


@pytest.fixture
def graph():
    store = InMemoryGraphStore()
    for ref, kind, props in [
        ("p", "Project", {"language": "zh-CN"}),
        ("hero", "Character", {"project_id": "p", "name": "林烬"}),
        ("secret", "Secret", {"project_id": "p", "description": "失落王朝的身世"}),
        ("baseline", "Secret", {"project_id": "p", "description": "主角原本知道的门路"}),
        ("chapter", "Chapter", {"project_id": "p"}),
        ("place", "Location", {"project_id": "p", "name": "钟楼"}),
        *[(f"s{i}", "Scene", {"project_id": "p", "chapter_id": "chapter",
            "pov_character_id": "hero", "required_characters": ["hero"], "location_id": "place",
            "goal": "查明身份的线索", "conflict": "证人拒绝开口", "timeline_position": f"第{i}日"}) for i in range(1, 4)],
    ]:
        store.seed_canon_node(node_id=ref, node_type=kind, properties=props)
    for i in (1, 2):
        store.seed_canon_relation(relation_id=f"next{i}", relation_type="NEXT_SCENE", source_id=f"s{i}",
            target_id=f"s{i+1}", properties={"project_id": "p"})
    store.seed_canon_relation(relation_id="initial_knowledge", relation_type="KNOWS_SECRET",
        source_id="hero", target_id="baseline", properties={"project_id": "p", "initial_knowledge": True})
    return store


def reveal(graph, kind="KNOWS_SECRET", **properties):
    return graph.seed_canon_relation(relation_id="revelation", relation_type=kind,
        source_id="hero", target_id="secret",
        properties={"project_id": "p", "valid_from_scene": "s2", **properties})


def test_early_unknown_reveal_entry_unknown_through_known_later_known(graph):
    reveal(graph)
    assert "secret" not in graph.get_character_knowledge("hero", scene_id="s1", at_scene_start=True).knows
    entry = graph.get_character_knowledge("hero", scene_id="s2", at_scene_start=True)
    assert "secret" in entry.does_not_know and "revelation" not in entry.source_refs
    assert "secret" in graph.get_character_knowledge("hero", scene_id="s2").knows
    assert "secret" in graph.get_character_knowledge("hero", scene_id="s3", at_scene_start=True).knows
    assert "baseline" in entry.knows and "initial_knowledge" in entry.source_refs


@pytest.mark.parametrize("kind,field", [("BELIEVES_FALSELY", "falsely_believes"),
    ("SUSPECTS", "suspects"), ("HIDES_FROM", "hides")])
def test_all_knowledge_families_use_the_same_entry_boundary(graph, kind, field):
    reveal(graph, kind)
    assert "secret" not in getattr(graph.get_character_knowledge("hero", scene_id="s2", at_scene_start=True), field)
    assert "secret" in getattr(graph.get_character_knowledge("hero", scene_id="s2"), field)


def test_valid_until_boundary_remains_active_at_scene_entry(graph):
    graph.seed_canon_relation(relation_id="until_reveal", relation_type="KNOWS_SECRET", source_id="hero",
        target_id="secret", properties={"project_id": "p", "valid_until_scene": "s2"})
    assert "secret" in graph.get_character_knowledge("hero", scene_id="s2", at_scene_start=True).knows
    assert "secret" in graph.get_character_knowledge("hero", scene_id="s2").knows
    assert "secret" not in graph.get_character_knowledge("hero", scene_id="s3", at_scene_start=True).knows


def test_cross_project_scene_and_missing_entry_scene_rejected(graph):
    graph.seed_canon_node(node_id="q", node_type="Project", properties={"language": "zh-CN"})
    graph.seed_canon_node(node_id="foreign_scene", node_type="Scene", properties={"project_id": "q"})
    with pytest.raises(ContractError, match="Character project"):
        graph.get_character_knowledge("hero", scene_id="foreign_scene", at_scene_start=True)
    with pytest.raises(ContractError, match="exact Scene"):
        graph.get_character_knowledge("hero", at_scene_start=True)


def test_context_builder_and_scene_review_use_entry_knowledge_and_hide_inactive_edges(graph):
    reveal(graph, description="FUTURE_KNOWLEDGE_EDGE_SENTINEL")
    for scene, known in (("s1", False), ("s2", False), ("s3", True)):
        pack = ContextPackBuilder(graph).build(project_id="p", scene_id=scene, target_tokens=12000)
        assert ("secret" in pack.knowledge_boundaries[0].knows) == known
        snapshot = build_canon_snapshot(graph, project_id="p", scene_id=scene)
        hero = json.loads(next(fact.text for fact in snapshot.facts if fact.id == "hero"))
        boundary = hero["knowledge_at_scene_entry"]
        assert boundary["scene_id"] == scene and boundary["at_scene_start"] is True
        assert ("secret" in boundary["knows"]) == known
        assert ("revelation" in {fact.id for fact in snapshot.facts}) == known
        assert ("FUTURE_KNOWLEDGE_EDGE_SENTINEL" in snapshot.model_dump_json()) == known
        assert snapshot.complete


def test_current_scene_suspecting_edge_is_not_leaked_as_active_relationship(graph):
    reveal(graph, "SUSPECTS")
    pack = ContextPackBuilder(graph).build(project_id="p", scene_id="s2", target_tokens=12000)
    assert pack.knowledge_boundaries[0].suspects == []
    assert not any("SUSPECTS" in relation for relation in pack.active_relationships)


def test_neo4j_read_projection_forwards_entry_flag_with_memory_parity(graph):
    reveal(graph)
    backend = object.__new__(Neo4jGraphStore)
    backend._snapshot = lambda: graph
    for entry in (False, True):
        expected = graph.get_character_knowledge("hero", scene_id="s2", at_scene_start=entry)
        assert backend.get_character_knowledge("hero", scene_id="s2", at_scene_start=entry) == expected
    with pytest.raises(ContractError):
        backend.get_character_knowledge("hero", at_scene_start=True)
