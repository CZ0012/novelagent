"""Demo fixture for the minimum fantasy scenario from the architecture document."""

from __future__ import annotations

from typing import Any

from storygraph.localization import load_demo_locale
from storygraph.stores.memory_graph import InMemoryGraphStore


PROJECT_ID = "project_fantasy_demo"
SCENE_ID = "scene_003"
CHAPTER_ID = "chapter_001"
POV_CHARACTER_ID = "character_linj"
LOCATION_ID = "location_old_bell_tower"
SECRET_ID = "secret_lineage"
ITEM_ID = "item_black_seal_half"


def build_fantasy_demo_graph(locale: str | None = None) -> InMemoryGraphStore:
    text = load_demo_locale(locale)
    graph = InMemoryGraphStore()
    graph.seed_canon_node(
        node_id=PROJECT_ID,
        node_type="Project",
        properties=_section(text, "project"),
    )
    graph.seed_canon_node(
        node_id=CHAPTER_ID,
        node_type="Chapter",
        properties={
            "project_id": PROJECT_ID,
            "volume_index": 1,
            "chapter_index": 1,
            **_section(text, "chapter"),
        },
    )
    graph.seed_canon_node(
        node_id=POV_CHARACTER_ID,
        node_type="Character",
        properties=_section(text, "characters", POV_CHARACTER_ID),
    )
    graph.seed_canon_node(
        node_id="character_helianya",
        node_type="Character",
        properties=_section(text, "characters", "character_helianya"),
    )
    graph.seed_canon_node(
        node_id="organization_silver_crow",
        node_type="Organization",
        properties=_section(text, "organization"),
    )
    graph.seed_canon_node(
        node_id=LOCATION_ID,
        node_type="Location",
        properties=_section(text, "location"),
    )
    graph.seed_canon_node(
        node_id=ITEM_ID,
        node_type="Item",
        properties=_section(text, "item"),
    )
    graph.seed_canon_node(
        node_id=SECRET_ID,
        node_type="Secret",
        properties=_section(text, "secret"),
    )
    graph.seed_canon_node(
        node_id="foreshadowing_early_bell",
        node_type="Foreshadowing",
        properties={
            "seed_scene_id": SCENE_ID,
            "payoff_scene_id": "scene_005",
            **_section(text, "foreshadowing"),
        },
    )
    graph.seed_canon_node(
        node_id="worldrule_secret_reveals",
        node_type="WorldRule",
        properties=_section(text, "world_rule"),
    )
    graph.seed_canon_node(
        node_id=SCENE_ID,
        node_type="Scene",
        properties={
            "project_id": PROJECT_ID,
            "chapter_id": CHAPTER_ID,
            "scene_index": 3,
            "pov_character_id": POV_CHARACTER_ID,
            "location_id": LOCATION_ID,
            "required_characters": [POV_CHARACTER_ID, "character_helianya"],
            **_section(text, "scene"),
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
        properties=_section(text, "relations", "rel_linj_knows_helianya"),
    )
    graph.seed_canon_relation(
        relation_id="rel_foreshadowing_points_to_secret",
        relation_type="POINTS_TO",
        source_id="foreshadowing_early_bell",
        target_id=SECRET_ID,
    )
    return graph


def _section(payload: dict[str, Any], *keys: str) -> dict[str, Any]:
    current: Any = payload
    for key in keys:
        current = current[key]
    return dict(current)
