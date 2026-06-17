# Context Pack Contract v1

## Purpose

`context_pack_v1` defines the compact scene-specific context handed to the Writing Agent. It is the main protection against dumping the whole novel into the prompt.

A Context Pack is built from canon graph state, draft metadata, style samples, and explicit author intent.

## Producers And Consumers

- Primary producer: Context Agent.
- Primary consumer: Writing Agent.
- Secondary consumers: QA Agent and Director.
- Related contracts: `graph_store_v1`, `continuity_report_v1`.

## Required Top-Level Fields

- `contract_version`: must be `context_pack_v1`
- `project_id`
- `scene_id`
- `chapter_id`
- `pov_character_id`
- `location_id`
- `timeline_position`
- `scene_goal`
- `conflict`
- `required_characters`
- `active_relationships`
- `knowledge_boundaries`
- `must_include`
- `must_not_violate`
- `unresolved_foreshadowing`
- `relevant_world_rules`
- `previous_scene_summary`
- `style_constraints`
- `retrieved_style_samples`
- `provenance`
- `budget`

## Knowledge Boundary Item

Each `knowledge_boundaries` item must include:

- `character_id`
- `knows`
- `does_not_know`
- `falsely_believes`
- `suspects`
- `hides`
- `source_refs`

## Style Constraints

`style_constraints` should include:

- `pov`
- `tense`
- `tone`
- `sentence_rhythm`
- `diction`
- `dialogue_style`
- `banned_patterns`

## Provenance

`provenance` must identify the graph queries, draft records, style samples, and author instructions used to build the pack.

Minimum fields:

- `graph_query_ids`
- `draft_refs`
- `style_sample_refs`
- `author_instruction_refs`
- `built_at`

## Budget

`budget` records context sizing decisions.

Minimum fields:

- `target_tokens`
- `estimated_tokens`
- `priority_order`
- `dropped_items`

## Priority Order

The default priority order is:

- `P0`: current scene hard constraints
- `P1`: character knowledge boundaries
- `P2`: current relationships and goals
- `P3`: world rules and location state
- `P4`: unresolved foreshadowing
- `P5`: previous scene result
- `P6`: style samples
- `P7`: long-range background summaries

## Invariants

- The Context Pack must not contain full chapters.
- The Context Pack must not promote draft facts to canon.
- Hard constraints must be explicit in `must_not_violate`.
- IDs must be stable graph or draft IDs, not display names only.
- If a required canon fact is missing, the Context Agent must report the gap instead of inventing it.
- Retrieved style samples are soft guidance unless promoted to explicit style constraints.

## Minimal Example

```json
{
  "contract_version": "context_pack_v1",
  "project_id": "project_001",
  "scene_id": "scene_014",
  "chapter_id": "chapter_007",
  "pov_character_id": "character_linj",
  "location_id": "location_old_bell_tower",
  "timeline_position": "three days after the capital coup",
  "scene_goal": "The POV character searches for the missing sealed letter.",
  "conflict": "The tower is controlled by a hostile faction.",
  "required_characters": ["character_linj", "character_helianya"],
  "active_relationships": ["character_linj distrusts character_helianya"],
  "knowledge_boundaries": [],
  "must_include": ["The bell rings earlier than expected."],
  "must_not_violate": ["The POV character must not learn their true lineage."],
  "unresolved_foreshadowing": [],
  "relevant_world_rules": [],
  "previous_scene_summary": null,
  "style_constraints": {
    "pov": "third-person limited",
    "tense": null,
    "tone": "restrained and cold",
    "sentence_rhythm": null,
    "diction": null,
    "dialogue_style": "short lines with subtext",
    "banned_patterns": []
  },
  "retrieved_style_samples": [],
  "provenance": {
    "graph_query_ids": [],
    "draft_refs": [],
    "style_sample_refs": [],
    "author_instruction_refs": [],
    "built_at": "2026-06-17T00:00:00Z"
  },
  "budget": {
    "target_tokens": 4000,
    "estimated_tokens": 600,
    "priority_order": ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7"],
    "dropped_items": []
  }
}
```
