# Context Pack Contract v1

Applied long-form local plan identifiers and Proposal provenance remain stored
unchanged. Scene semantic-review/extraction snapshots use the same distinction
as Context Pack planning: actual CAUSES/SEEDED_IN/PAID_OFF_IN edges supply scoped
semantics; local declarations expose missing/mismatched links rather than being
treated as graph IDs. This does not waive actual entity, hierarchy, style or
previous-scene reference validation, and does not make a planned event realized.

## Project-aware default budget

`ContextPackBuilder.build(target_tokens=None)` resolves the context target without
writing project/canon data: protected/approved-longform AUTO starts at 8,000
tokens for a Project with `require_semantic_review` or an approved
`longform_blueprint_id`, and uses the existing fixed 4,000 otherwise. The returned `budget.target_tokens` is the resolved positive
integer, never null. Stored/historical explicit budgets are not rewritten.
Any explicit positive integer, including 4,000, remains a hard target and is
never silently raised. Invalid booleans, zero or negative values reject.

Only omitted/null protected AUTO may grow. From the same graph-guarded source
and provenance snapshot, estimate essential context after excluding only the
existing optional examples/prior-Draft-summary fields. If it exceeds 8,000,
select `ceil((essential_estimate+256)/2000)*2000`, capped at 16,000, and apply the
normal budget policy to the original full context. There is no new source read,
inferred fact, model call or P0 removal. Normal packs stay at 8,000; an essential
pack still larger than 16,000 fails closed at that cap. Explicit 8,000 or 4,000
NEVER expands. This bounded AUTO selection is not a higher provider/output limit;
the actual selected target is visible in the pack before any drafting request.

`POST /projects/{project_id}/scenes/{scene_id}/context-pack` accepts an optional
`{target_tokens?:positive_integer|null}` body. No body, `{}` and null select the
project default; explicit 4,000 stays explicit. CLI `build-context` also defaults
to project resolution; `--target-tokens` explicitly overrides it. Writing,
discussion, workflow and semantic-review paths that omit a target use this same
builder policy. No provider/model selection or paid retry behavior changes.

Protected canon, knowledge, typed state, approved scene plan and author style
remain protected at every selected target. Bounded AUTO accommodates rich normal
projects; it does not truncate P0 data or guarantee every scene fits. Any
overflow still produces critical `context_budget_exceeded` and blocks complete
scene drafting before provider invocation. Token counts remain conservative
estimates rather than vendor-tokenizer or whole-request limits.

## Purpose

`context_pack_v1` defines the compact scene-specific context handed to the Writing Agent. It is the main protection against dumping the whole novel into the prompt.

A Context Pack is built from canon graph state, draft metadata, style samples, and explicit author intent.

## Producers And Consumers

- Primary producer: Context Agent.
- Primary consumer: Writing Agent.
- Secondary consumers: QA Agent and Director.
- Related contracts: `graph_store_v1`, `style_sample_store_v1`,
  `continuity_report_v1`, `language_policy_v1`.

## Required Top-Level Fields

- `contract_version`: must be `context_pack_v1`
- `project_id`
- `output_language`: server-derived `zh-CN` or `en-US` snapshot from the owning
  `Project.language`
- `scene_id`
- `chapter_id`
- `pov_character_id`
- `location_id`
- `timeline_position`
- `scene_goal`
- `conflict`
- optional additive `scene_plan` (absent/null for legacy scenes without planning data)
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
- `missing_context`
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

Writing Context Packs query these boundaries at scene entry. A revelation or
suspicion first acquired during the current Scene is not opening knowledge;
explicit reviewed initial-knowledge edges and prior reachable knowledge are
preserved. Matching knowledge-family entries in active_relationships must obey
the same entry boundary instead of leaking a through-scene SUSPECTS edge.

## Approved Scene Plan

`scene_plan` carries semantic author-approved planning metadata with
`semantics = approved_plan_not_realized_facts`. It is not realized canon state,
proof a predecessor was written, or a literal phrase list. Optional fields are
`planned_outcome`, `emotional_turn`, and positive integer `target_length`.
Missing fields are not guessed, copied from prose or written back to Graph Store.

`causal_preconditions` contains at most 30 DIRECT incoming CANON CAUSES edges
marked `planning_only = true`, each with exact stable source Scene ID, relation
ID and optional approved source `planned_summary`/`planned_outcome`. No full-book
recursion, imported prose or inferred predecessor is permitted. Existing local
plan-ID lists are not resolved by title or treated as runtime graph IDs; declared
missing relation counts become critical gaps. Every endpoint and relation must
belong to the requested project before its text can enter the pack.

`foreshadowing_actions` contains at most 30 direct planning-only SEEDED_IN or
PAID_OFF_IN links to the exact current Scene. Each includes stable Foreshadowing
ID, relation ID, action (`seed`/`payoff`), clue text and
`do_not_reveal_payoff`. A seed never includes hidden payoff text. A payoff may
include its approved `planned_payoff` plus up to 30 exact referenced seed Scene
IDs, themselves planning metadata rather than proof of realized setup. Missing,
foreign, malformed or oversized fields/links produce explicit critical gaps;
full drafting must stop rather than invent a prerequisite or silently truncate.

These plan fields are protected P0 context. Budget trimming may drop soft style
examples and optional previous Draft summary, but must preserve the complete
selected scene plan and report an over-budget critical gap when necessary.
Nothing is copied into must_include: prose remains stylistically free while
working toward the approved beats, target ending and length budget. Existing
Draft summaries remain explicitly noncanon evidence with their Draft refs; this
plan projection introduces no additional Draft/Source reads or canon writes.

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

## Missing Context

`missing_context` reports canon or draft context that the Context Agent expected but could not retrieve.

Each item should include:

- `kind`: short machine-readable category such as `missing_node`, `missing_scene_field`, `missing_draft`, `project_mismatch`, or `incomplete_graph_context`
- `ref`: the missing or conflicting field, node ID, scene ID, or draft ref
- `severity`: `low`, `medium`, `high`, or `critical`
- `message`: human-readable gap description
- `source`: optional scene or context source that exposed the gap

Missing context is a report, not invented canon. A Context Pack may still be emitted with empty strings or empty lists in the affected fields so the Director, Writing Agent, API, or CLI can show the gap and block or ask for human clarification.

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

- `output_language` follows `language_policy_v1`. It is frozen when the pack is
  built, is not a UI locale, and cannot be overridden by an author instruction
  or selected source.
- The Context Pack must not contain full chapters.
- The Context Pack must not promote draft facts to canon.
- Hard constraints must be explicit in `must_not_violate`.
- IDs must be stable graph or draft IDs, not display names only.
- If a required canon fact is missing, the Context Agent must report the gap instead of inventing it.
- Critical `missing_context` items should block drafting until the author or Director supplies canon or revises the scene plan.
- Retrieved style samples are soft guidance unless promoted to explicit style constraints by explicit author action.
- `provenance.style_sample_refs` are refs into the style sample store, not graph canon refs.

## Minimal Example

```json
{
  "contract_version": "context_pack_v1",
  "project_id": "project_001",
  "output_language": "en-US",
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
  "missing_context": [],
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

## SG-029 project style and protected context

Context Pack adds `canon_entities`, a scoped structured registry resolving character/location/secret IDs to names and facts. It contains no Draft or Source prose. Missing/foreign canon cannot be replaced with guesses. Project.style_profile_id resolves only a same-project CANON StyleProfile; its fields form the style defaults, with explicit scene overrides. style_constraints adds nullable profile_id/profile_sha256 and rubric (string array), preserving legacy packs. The approved project voice outranks generic runtime presets and examples while remaining subordinate to canon and language rules.

Token estimation counts Han characters conservatively instead of applying the English four-character estimate. Budget trimming removes examples and prior draft summaries before protected canon, knowledge, rules, linked clues and style. If protected context still exceeds the target, emit critical context_budget_exceeded and block full drafting; do not silently remove WorldRules to claim a budget fit.

## SG-030 scene-time state and corrections

ContextPack adds temporal_states projections for explicitly tracked Character/Item slots. `at_scene_start=true` excludes assertions made during the current scene. Resolved typed values override baseline/descriptive arc text; unknown/ambiguous tracked slots are critical context gaps. Legacy entities with no explicit baseline or assertion history do not acquire guessed state slots. Item retrieval uses explicit scene references/names or ownership resolved at scene entry; future ownership alone must not reveal the item. A guarded local graph read keeps each context build internally consistent.

Semantic scene evidence uses the same entry projection from a frozen graph and includes only the used prior assertion references, excluding future/superseded raw assertion text. Plan review excludes explicitly superseded state records while retaining all history in the canon fingerprint. Explicit history routes keep the old audit evidence available.
