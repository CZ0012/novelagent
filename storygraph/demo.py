"""Demo fixture for the minimum fantasy scenario from the architecture document."""

from __future__ import annotations

from storygraph.stores.memory_graph import InMemoryGraphStore


PROJECT_ID = "project_fantasy_demo"
SCENE_ID = "scene_003"
CHAPTER_ID = "chapter_001"
POV_CHARACTER_ID = "character_linj"
LOCATION_ID = "location_old_bell_tower"
SECRET_ID = "secret_lineage"
ITEM_ID = "item_black_seal_half"


def build_fantasy_demo_graph() -> InMemoryGraphStore:
    graph = InMemoryGraphStore()
    graph.seed_canon_node(
        node_id=PROJECT_ID,
        node_type="Project",
        properties={
            "title": "Fantasy Demo",
            "genre": "fantasy",
            "language": "zh-CN",
            "target_length": "demo",
            "narrative_pov": "third-person limited",
        },
    )
    graph.seed_canon_node(
        node_id=CHAPTER_ID,
        node_type="Chapter",
        properties={
            "project_id": PROJECT_ID,
            "volume_index": 1,
            "chapter_index": 1,
            "title": "The Old Bell Tower",
            "status": "planned",
        },
    )
    graph.seed_canon_node(
        node_id=POV_CHARACTER_ID,
        node_type="Character",
        properties={
            "name": "Lin Jin",
            "role": "protagonist",
            "desire": "Find the missing sealed letter.",
            "current_status": "searching",
        },
    )
    graph.seed_canon_node(
        node_id="character_helianya",
        node_type="Character",
        properties={
            "name": "Helian Ya",
            "role": "faction agent",
            "current_status": "secretly protective",
        },
    )
    graph.seed_canon_node(
        node_id="organization_silver_crow",
        node_type="Organization",
        properties={
            "name": "Silver Crow Society",
            "goal": "Control the tower district.",
        },
    )
    graph.seed_canon_node(
        node_id=LOCATION_ID,
        node_type="Location",
        properties={
            "name": "Old Bell Tower",
            "type": "tower",
            "current_status": "controlled by the Silver Crow Society",
        },
    )
    graph.seed_canon_node(
        node_id=ITEM_ID,
        node_type="Item",
        properties={
            "name": "Half Black Wax Seal",
            "type": "clue",
            "current_status": "missing",
        },
    )
    graph.seed_canon_node(
        node_id=SECRET_ID,
        node_type="Secret",
        properties={
            "content": "Lin Jin carries royal blood.",
            "truth_status": "true",
            "reveal_plan": "Do not reveal before scene_005.",
        },
    )
    graph.seed_canon_node(
        node_id="foreshadowing_early_bell",
        node_type="Foreshadowing",
        properties={
            "seed_scene_id": SCENE_ID,
            "payoff_scene_id": "scene_005",
            "clue_text": "The bell rings earlier than expected.",
            "hidden_meaning": "The underground bell array has been activated.",
            "status": "seeded",
            "importance": "high",
        },
    )
    graph.seed_canon_node(
        node_id="worldrule_secret_reveals",
        node_type="WorldRule",
        properties={
            "domain": "knowledge",
            "rule": "Royal lineage secrets require explicit scene-level reveal events.",
            "severity": "high",
        },
    )
    graph.seed_canon_node(
        node_id=SCENE_ID,
        node_type="Scene",
        properties={
            "project_id": PROJECT_ID,
            "chapter_id": CHAPTER_ID,
            "scene_index": 3,
            "title": "The Tower Search",
            "pov_character_id": POV_CHARACTER_ID,
            "location_id": LOCATION_ID,
            "timeline_position": "three days after the capital coup",
            "goal": "search for the missing sealed letter",
            "conflict": "the tower is controlled by a hostile faction",
            "outcome": "Lin Jin finds a physical clue but not the lineage truth.",
            "emotional_turn": "suspicion sharpens into wary resolve",
            "required_characters": [POV_CHARACTER_ID, "character_helianya"],
            "must_include": ["bell rings early", "half black wax seal"],
            "must_not_violate": ["Lin Jin learns secret_lineage"],
            "style_constraints": {
                "pov": "third-person limited",
                "tone": "cold and restrained",
                "dialogue_style": "short lines with subtext",
                "banned_patterns": ["omniscient explanation"],
            },
        },
    )
    graph.seed_canon_relation(
        relation_id="rel_project_chapter_001",
        relation_type="HAS_CHAPTER",
        source_id=PROJECT_ID,
        target_id=CHAPTER_ID,
    )
    graph.seed_canon_relation(
        relation_id="rel_chapter_scene_003",
        relation_type="HAS_SCENE",
        source_id=CHAPTER_ID,
        target_id=SCENE_ID,
    )
    graph.seed_canon_relation(
        relation_id="rel_silver_crow_controls_tower",
        relation_type="CONTROLS",
        source_id="organization_silver_crow",
        target_id=LOCATION_ID,
    )
    graph.seed_canon_relation(
        relation_id="rel_linj_knows_helianya",
        relation_type="KNOWS",
        source_id=POV_CHARACTER_ID,
        target_id="character_helianya",
        properties={"strength": -0.2, "public_status": "uneasy acquaintance"},
    )
    graph.seed_canon_relation(
        relation_id="rel_foreshadowing_points_to_secret",
        relation_type="POINTS_TO",
        source_id="foreshadowing_early_bell",
        target_id=SECRET_ID,
    )
    return graph

