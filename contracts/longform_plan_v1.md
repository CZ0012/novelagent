# Long-form Plan Contract v1

`longform_plan_v1` is a structured JSON subtype of `outline_draft` in the existing
Proposal Store. It plans long-form fiction without generating manuscript prose.
Related boundaries: `proposal_artifact_v1`, `graph_store_v1`,
`language_policy_v1`, `agent_runtime_v1`, and `context_pack_v1`.

## Persisted phases and routes

- `POST /projects/{project_id}/longform/blueprints` accepts
  `{instruction,target_length=500000,volume_count=5,chapters_per_volume=20,scenes_per_chapter=2}`.
  Bounds are 10,000–2,000,000 target characters, 1–12 volumes,
  1–60 chapters per volume, and 1–6 scenes per chapter.
- `POST /projects/{project_id}/longform/expansions` accepts
  `{parent_proposal_id,parent_version,volume_index,chapter_start=1,chapter_count=5,instruction=""}`.
  A batch contains 1–5 consecutive chapters from one volume. Its parent must be
  the exact current accepted and applied blueprint version. Batches proceed in
  reading order, with every preceding planned scene already applied.
- `POST /projects/{project_id}/proposals/{proposal_id}/apply/longform` accepts
  `{expected_version,reviewer,rationale,review_id?}`. Ordinary Proposal acceptance is still
  a separate explicit author action. Applying unaccepted content is forbidden.
- `POST /projects/{project_id}/proposals/{proposal_id}/revise-longform` accepts
  `{expected_version,instruction,mode="full"}`; instruction is nonblank and at most 12,000
  characters. This explicitly generates a NEW alternative Proposal, not a new
  version of the original and never an edit to applied canon.

Generation returns `{proposal,output_language,model_execution}`. Application
returns `{proposal,nodes,relationships,already_applied}`. `longform_invalid`,
`longform_stale`, and `longform_backend_unsupported` are stable error categories.
Shared language guard and safe provider error handling continue to apply.
Known validation failures may additionally return a static `reason_code`, such
as `character_arc_coverage`, `volume_budgets`, `duplicate_identifiers`, or
`output_schema_invalid`. Codes come from a server whitelist and contain no
provider text, private field values, credentials or raw parser diagnostics.

Each generation request makes at most one paid provider call. It resolves the
existing planning connection and selected preset once; no automatic retry,
fallback, whole-book generation loop, or automatic application is implied.
The provider receives explicit cross-field validation rules in addition to JSON
Schema; schema shape alone cannot express global ID namespaces, complete
Character arc coverage, causal volume coverage or exact integer budget vectors.
No provider call reads Draft or Source prose implicitly. The returned artifact
is persisted independently, so completed work survives process restart.

Revision requires an exact current schema-valid, project-scoped, confirmed-
language source with no derived application refs or graph application events.
An applied or partially applied source is rejected before provider use. The
source phase, original request and accepted blueprint parent/version remain
fixed; current canon is explicitly revalidated and its refreshed fingerprint
belongs only to the new alternative. Expansion revisions must still target the
next unapplied batch. Validate the whole revised output with the same schema,
budget, topology, reference, language and clue lifecycle rules. Source, parent
or canon changes during the call fail before a new Proposal is saved. Record
the exact source Proposal ID/version in `source_refs`; preserve expansion parent
lineage. The source Proposal and canon remain unchanged. No silent JSON repair,
automatic retry, application or acceptance is implied.

`mode=targeted` is a bounded explicit minimal-edit revision. The provider sees
the exact current payload, its source schema and an allowlist of existing
natural-language string JSON Pointer paths, rooted at `/blueprint` or
`/expansion`. Its strict response is
`{changes:[{path,before,after}]}`, containing 1–40 distinct paths and at least
one actual change. Every path must be on the allowlist. `before` must equal
either the complete saved string or one exact nonempty substring occurring
exactly once, counting overlapping occurrences. Replace only that whole value
or unique span; preserve its surrounding prefix/suffix. No trimming,
normalization, fuzzy matching or occurrence guessing is allowed. The provider
receives `current_values` keyed by exact allowed paths to avoid index/copy drift.
Copy the source structure and replace only those existing string leaves. No insertion,
deletion, array reordering, IDs, kinds, typed initial-state values, reference
lists, numeric budgets/counts, request or envelope changes are supported. Both
strings are bounded; the complete resulting source model additionally enforces
each original field's bounds and all normal cross-field/language checks. Invalid
paths, duplicates, ambiguous spans and stale before values fail before save.
An exact no-op still validates its path and before text, then leaves the field
untouched; mixed no-op/real patches return `skipped_noop_paths`. An all-no-op
response is rejected without a new Proposal. All unrelated fields and span
surroundings remain identical. `mode=full` preserves the original
whole-payload revision behavior for backward compatibility. Both modes create
a new unapplied Proposal and obey the same version/canon/parent race checks.

## Body envelope

The server constructs `{schema:"longform_plan_v1",phase,project_id,output_language,
graph_snapshot,request,parent_proposal_id,parent_version,blueprint,expansion}`.
`graph_snapshot` is the full-project canon content fingerprint; `request` is the
validated original request. The unused payload and blueprint parent fields are
null. Clients/providers cannot choose the envelope. Original phase, project,
language, graph fingerprint, request and parent reference are immutable across
author revisions. Authored plan content may be revised and revalidated.

`phase=blueprint` contains:

- `synopsis`.
- `world_rules`: unique local `{id,domain,rule}` records.
- `entities`: unique local `{id,kind,name,description}` records, with kinds
  `Character`, `Location`, `Organization`, `Item`, or `Secret`. At least one
  Character and Location are required. Same-kind names are unique.
  An optional typed `initial_state` may specify explicit opening baselines:
  Characters allow `life_status: alive|dead`,
  `physical_state: healthy|injured|healing`, and `location_id` referencing a local
  Location; Items allow `location_id` referencing a local Location and `owner_id`
  referencing a local Character/Organization, or null for explicitly unowned.
  No other keys/kinds or foreign/mistyped references are allowed. All slots are
  optional; omitted slots remain unknown, with no guessed life, health, location
  or owner. Only owner may be explicitly null. Life and physical condition are
  independent slots; validators must not invent unsupported narrative rules.
- `character_arcs`: one per Character, with `character_id`, `initial_state`,
  `desire`, `conflict`, ordered `{volume_index,change}` turning points and
  `final_state`.
- `style_brief`: `{name,pov,tense,tone,sentence_rhythm,diction,dialogue_style,
  banned_patterns,rubric}`. Rubric is 1–20 bounded author-readable strings.
- `volumes`: ordered `{index,title,summary,central_conflict,climax,ending_hook,
  target_length}` records, exactly matching requested volume count.
- `causal_links`: `{id,from_volume,to_volume,cause,effect}`. Causes precede
  effects. Every later volume connects to an earlier volume.
- `foreshadowing`: `{id,clue,payoff,seed_volume,payoff_volume,character_ids}`.
  Local IDs are unique across categories; referenced Characters exist and
  payoff cannot precede seed.

`phase=expansion` contains `{volume_index,chapter_start,chapters}`. Each Chapter
has `{index,title,summary,purpose,target_length,scenes}`. Its local chapter index
is 1-based within its volume. Each Scene has `{id,title,summary,goal,conflict,
outcome,emotional_turn,pov_character_id,location_id,required_characters,
timeline_position,target_length,causal_dependencies,foreshadowing_seed_ids,
foreshadowing_payoff_ids}`. Scene plan IDs are exact server-supplied slots,
e.g. `v01_c001_s01`. POV/required Characters and Location refer to accepted
blueprint local IDs with matching types. All scenes after the opening have
earlier valid scene dependencies; forward/self/out-of-range references fail.

Character budgets partition by integer division, with the remainder assigned
one character at a time to earliest slots. Volume budgets sum exactly to the
book target; chapter budgets partition their volume, and scene budgets their
chapter. Budgets are planning targets, not a claim of generated prose length.

Clues have one planned seed and one planned payoff, in the declared volumes.
Payoff must follow its planned seed. Completing a volume requires placement of
all seeds/payoffs allocated to that volume; cross-batch duplicate placements
are rejected. No manuscript text or arbitrary graph patch is executable here.

## Canon and context boundaries

Generation consumes bounded immutable existing canon and the accepted blueprint.
Expansion also consumes recent saved plan outcomes, never implicit manuscript
prose. Existing canon remains authoritative. The content fingerprint covers the
whole project even when the prompt omits unrelated structural records. Invalid
or truncated canon evidence blocks planning; an empty project lacking existing
story canon is valid input for independent blueprint design.
Clue placements are supplied across all earlier applied batches, separately
from the bounded recent outcomes, so a distant seed is not lost at a batch seam.

First application requires exact accepted Proposal version, frozen project
language, matching current canon fingerprint and active project. It validates
all authored content, topology, IDs, references, budgets and target ownership
before writes. Existing graph IDs or canonical same-kind entity names cannot
be overwritten or silently duplicated. Incoming chapter positions must not
collide with unrelated existing Chapters.
The API additionally requires a fresh passing semantic review of that exact
accepted version. The service's optional `before_apply` enforcement callback
runs under the graph mutation guard after completion-evidence detection and
before any first-application mutation. Pure offline service fixtures may omit
the callback; the product API must provide its review enforcement. Verified
completed retries skip the callback so receipt repair remains possible after
graph persistence changed the review fingerprint. A derived-ref marker alone
cannot authorize this exemption; complete graph/event evidence must validate.

Blueprint application creates reviewed world/entity/Foreshadowing/StyleProfile
nodes with server-derived stable IDs. Character arcs and clue allocations are
explicit planning metadata, not assertions that future events already happened.
Explicit nonempty entity baselines map to graph `properties.initial_state`,
resolving local references to stable graph IDs. Descriptive arc text and future
final states do not become typed current state. Legacy absent/null optional
baselines are omitted from canonical model serialization and graph properties,
preserving existing application body hashes and creation-event evidence. No
migration or default state is invented for already-applied plans.
It sets `Project.style_profile_id`, `longform_blueprint_id`,
`longform_target_length`, and `require_semantic_review=true`. The latter opts
new model-generated prose adoption into fresh semantic-review requirements;
it does not prohibit an author from saving manual Drafts or silently change
legacy projects.

Expansion application creates only new Chapter/Scene nodes, `HAS_CHAPTER`,
`HAS_SCENE`, consecutive `NEXT_SCENE`, planned `CAUSES`, `SEEDED_IN` and
`PAID_OFF_IN` relationships. Plan-specific causal/clue edges carry
`planning_only=true`; they do not assert that unwritten events occurred.
Chapter volume grouping uses `Chapter.volume_index`/`volume_title`; no Volume
node label is introduced. Actual scene metadata includes graph-resolved POV,
Location, required Characters, previous Scene, outcomes, budgets and style ref.
No Draft, CandidateFact or manuscript is created by plan application.

This is an explicit, narrowly reviewed human setup path. Natural-prose facts
still enter canon only through reviewed CandidateFacts. Acceptance, generation,
and Proposal editing alone never mutate canon.

## Persistence and recovery

Only memory/JSON Graph Stores currently support application. Under the shared
graph mutation lock, stage all graph objects, the project marker and full
provenance events in a cloned graph; atomically persist the graph/event snapshot
before publishing it. Every mutation records reviewer, rationale, source
Proposal/content hash and event evidence. Unsupported backends reject before
changes. Synchronous persistence failure publishes no graph/event delta.

After graph persistence, record `graph_node`, `graph_relation`, `canon_event`
and `{kind:"longform_application",ref:proposal.id}` derived refs in SQLite.
This is recoverable staged persistence, not a cross-database transaction. If the
receipt write fails, retry the same accepted content after restart: verify the
complete marker and every expected creation event/object, then repair refs
without repeating graph mutations. Current ID/name equality alone is never
completion evidence. Missing or altered evidence fails closed. Completed retry
preserves later author edits. The UI may use the exact application ref as its
durable completion indicator; backend verification remains authoritative.

Offline acceptance includes a 500,000-character target allocated across five
volumes, 100 Chapters and 200 Scenes, all 20 bounded chapter batches, reference
and budget failures, explicit review gates, concurrent apply, snapshot staleness,
atomic graph failure, restart recovery and missing evidence. These tests prove
the planning workflow and safety boundaries, not literary quality or absolute
absence of plot contradictions.
