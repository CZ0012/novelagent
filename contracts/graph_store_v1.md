# Graph Store Contract v1

## Purpose

`graph_store_v1` defines the backend-neutral contract for the canon graph. It is the stable boundary between graph implementation work, context building, canon review, and continuity checking.

The Graph Store represents structured narrative state. It must not store full draft prose.

## Producers And Consumers

- Primary producer: Canon Agent after human review.
- Primary consumers: Context Agent, QA Agent, Director, future API and CLI layers.
- Related contracts: `candidate_fact_v1`, `context_pack_v1`, `continuity_report_v1`.

## Canon Principles

- `CANON` data is authoritative.
- `DRAFT_FACT`, `HYPOTHESIS`, `CONFLICT`, and `DEPRECATED` data may be stored only when clearly separated from canon reads.
- Automatic agents must not promote candidate data to canon.
- Every write requires provenance.
- Every canon mutation must be recoverable through an event log.

## Core Node Labels

Minimum v1 labels:

- `Project`
- `Character`
- `Organization`
- `Location`
- `Item`
- `Event`
- `Scene`
- `Chapter`
- `Secret`
- `Foreshadowing`
- `WorldRule`
- `StyleProfile`

## Core Edge Labels

Minimum v1 relationship families:

- Character relationships: `KNOWS`, `LOVES`, `HATES`, `LOYAL_TO`, `BETRAYED`, `FAMILY_OF`, `MENTOR_OF`, `RIVAL_OF`
- Knowledge boundaries: `KNOWS_SECRET`, `BELIEVES_FALSELY`, `SUSPECTS`, `HIDES_FROM`
- Spatial and ownership state: `LOCATED_AT`, `CONTROLS`, `OWNED_BY`, `PART_OF`
- Events and causality: `CAUSES`, `CONSEQUENCE_OF`, `PARTICIPATED_IN`, `OCCURRED_AT`, `OCCURRED_IN_SCENE`
- Foreshadowing: `SEEDED_IN`, `POINTS_TO`, `PAID_OFF_IN`
- Story structure: `HAS_CHAPTER`, `HAS_SCENE`, `NEXT_SCENE`

## Required Metadata

Every node and edge returned by the Graph Store must include:

- `id`
- `type`
- `status`
- `created_at`
- `updated_at`
- `source_ref`

Canon-changing writes must also include:

- `event_id`
- `reviewer`
- `reviewed_at`
- `rationale`

## Status Values

Allowed v1 fact states:

- `CANON`
- `DRAFT_FACT`
- `HYPOTHESIS`
- `CONFLICT`
- `DEPRECATED`
- `STYLE_SAMPLE`

Default status for automated extraction is `DRAFT_FACT`.

## Required Read Operations

### `get_node`

Returns one graph node by stable ID.

### `query_neighbors`

Returns adjacent nodes and relationships for a source node, filtered by edge labels, node labels, status, and hop limit.

### `query_scene_context`

Returns canon state needed to build a Context Pack for one scene:

- POV character state
- required character states
- active relationships
- location state
- relevant world rules
- knowledge boundaries
- unresolved foreshadowing
- previous scene outcome

### `get_character_knowledge`

Returns what a character knows, does not know, falsely believes, suspects, or hides at a specific scene or timeline position.

### `get_unresolved_foreshadowing`

Returns foreshadowing items that are seeded but not paid off, optionally filtered by character, location, chapter, or importance.

## Required Write Operations

### `create_node`

Creates a non-conflicting node in a non-canon status unless the caller is an approved canon commit path.

### `update_node`

Updates node properties with provenance and event logging.

### `create_relation`

Creates a relationship between existing nodes with edge metadata.

### `seed_canon_node`

Creates a `CANON` node from an explicit human-authored seed action. This is for project setup and story-bible entry, not automated extraction.

Required provenance:

- `source_ref`
- `reviewer`
- `rationale`

### `seed_canon_relation`

Creates a `CANON` relationship from an explicit human-authored seed action after verifying both endpoints exist as canon nodes.

Required provenance:

- `source_ref`
- `reviewer`
- `rationale`

### `update_relation`

Updates relationship properties such as strength, public status, private status, or last changed scene.

### `commit_candidate_fact`

Applies an accepted `CandidateFact` or edited candidate fact as canon. This operation must be reachable only through the human review path.

### `record_event`

Records the append-only event log entry for every canon mutation.

## Query Invariants

- Canon reads must exclude non-canon states unless the caller explicitly asks for them.
- Reads should be deterministic: stable ordering by relevance, timeline, then ID.
- Hop limits must be explicit.
- No operation may infer new facts unless the result is marked as a hypothesis outside canon.

## Write Invariants

- No write may omit provenance.
- No automated write may create `CANON` status directly.
- Human-authored seed operations may create `CANON` only when the action includes reviewer, rationale, source reference, and an event log entry.
- Generated drafts, summaries, and model hypotheses must still use `CandidateFact`; they may not use seed operations to bypass review.
- A rejected candidate must not be deleted if it is needed for audit history; mark it rejected or deprecated in the review layer.
- Graph writes must be idempotent where a request ID or event ID is supplied.

## Human Seed API Surface

The v1 author seed surface includes:

- `POST /projects/{project_id}/characters`
- `POST /projects/{project_id}/locations`
- `POST /projects/{project_id}/relations`

These routes are explicit human canon-entry paths. They must not create pending `CandidateFact` records.

## Error Categories

Required v1 error categories:

- `not_found`
- `duplicate_id`
- `invalid_status_transition`
- `missing_provenance`
- `canon_write_forbidden`
- `conflict_detected`
- `backend_unavailable`

## Open Decisions

- Final backend choice may be Neo4j first with an optional Kuzu backend.
- Exact API method names may change during implementation, but the semantics above should remain stable for v1.
