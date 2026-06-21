# Candidate Fact Contract v1

## Purpose

`candidate_fact_v1` defines the output of state extraction and the input to human canon review.

A Candidate Fact is not canon. It is a proposed state change with evidence, confidence, and review status.

## Producers And Consumers

- Primary producer: Canon Agent state extraction flow.
- Primary consumers: Canon Agent review flow, Graph Agent, QA Agent, Director.
- Related contracts: `graph_store_v1`, `continuity_report_v1`, `review_payload_v1`, `workflow_run_v1`.

## Required Top-Level Fields

- `contract_version`: must be `candidate_fact_v1`
- `id`
- `project_id`
- `fact_type`
- `subject_id`
- `relation`
- `object_id`
- `value`
- `source_scene_id`
- `source_draft_id`
- `source_span`
- `confidence`
- `status`
- `rationale`
- `evidence`
- `proposed_graph_patch`
- `review`
- `created_at`

## Fact Type Guidance

Common v1 `fact_type` values:

- `CharacterState`
- `CharacterRelationship`
- `KnowledgeBoundary`
- `SecretReveal`
- `LocationState`
- `ItemState`
- `OrganizationState`
- `EventOccurrence`
- `CausalLink`
- `ForeshadowingSeed`
- `ForeshadowingPayoff`
- `WorldRule`
- `StyleObservation`

## Source Span

`source_span` must identify where the evidence came from.

Minimum fields:

- `start_offset`
- `end_offset`
- `quote`

The quote should be short and only long enough for review.

## Evidence

Each evidence item should include:

- `kind`: `draft_text`, `context_pack`, `graph_fact`, `author_instruction`, or `proposal_artifact`
- `ref`
- `note`

`proposal_artifact` evidence is supporting provenance only. It must not replace
the required `source_scene_id`, `source_draft_id`, or `source_span` taken from a
real Draft Store source.

## Proposed Graph Patch

`proposed_graph_patch` describes the intended graph mutation without executing it.

Minimum fields:

- `operation`: `create_node`, `update_node`, `create_relation`, `update_relation`, or `none`
- `target`
- `properties`
- `source_ref`

## Review

Before human review:

- `review.status` should be `pending`
- `review.reviewer` should be null
- `review.reviewed_at` should be null

After human review:

- `review.status` must be `accepted`, `edited`, `rejected`, or `deferred`
- `review.note` should explain the decision

## Status Values

Allowed v1 candidate statuses:

- `DRAFT_FACT`
- `HYPOTHESIS`
- `CONFLICT`
- `ACCEPTED_FOR_CANON`
- `REJECTED`
- `DEFERRED`
- `DEPRECATED`

Only the canon commit path may turn an accepted candidate into `CANON` graph state.

## Workflow Review Pause Integration

`ReviewPayload.candidate_ids` from `review_payload_v1` must reference `CandidateFact.id` values.

A workflow pause with `ReviewPayload.status = pending` is not a review decision and must not mutate canon. Canon commit still requires an explicit `ReviewService` human action.

Accepted or edited candidates require reviewer identity, review timestamp, rationale/provenance, and an event log entry before they become canon graph state. Rejected or deferred candidates must not mutate canon.

Current review API routes governed by this integration:

- `GET /projects/{project_id}/facts/pending`
- `POST /projects/{project_id}/facts/{fact_id}/accept`
- `POST /projects/{project_id}/facts/{fact_id}/edit-accept`
- `POST /projects/{project_id}/facts/{fact_id}/reject`
- `POST /projects/{project_id}/facts/{fact_id}/defer`

## Confidence Rules

- `confidence` must be between `0.0` and `1.0`.
- High confidence does not bypass review.
- Low confidence facts should remain `HYPOTHESIS` or `DEFERRED` unless the author accepts them.

## Invariants

- A candidate must cite a source scene and source draft.
- A candidate must not rely only on model inference unless marked `HYPOTHESIS`.
- A candidate must not modify the Graph Store directly.
- A candidate that conflicts with canon must be marked `CONFLICT`.
- Accepted candidates must keep the original evidence even if edited before commit.

## Minimal Example

```json
{
  "contract_version": "candidate_fact_v1",
  "id": "fact_001",
  "project_id": "project_001",
  "fact_type": "ItemState",
  "subject_id": "item_black_seal_half",
  "relation": "LOCATED_AT",
  "object_id": "location_old_bell_tower",
  "value": null,
  "source_scene_id": "scene_014",
  "source_draft_id": "draft_014_v3",
  "source_span": {
    "start_offset": 1204,
    "end_offset": 1242,
    "quote": "He found half of a black wax seal beneath the bell frame."
  },
  "confidence": 0.95,
  "status": "DRAFT_FACT",
  "rationale": "The draft explicitly places the item at the scene location.",
  "evidence": [],
  "proposed_graph_patch": {
    "operation": "create_relation",
    "target": "item_black_seal_half -> LOCATED_AT -> location_old_bell_tower",
    "properties": {},
    "source_ref": "draft_014_v3"
  },
  "review": {
    "status": "pending",
    "reviewer": null,
    "reviewed_at": null,
    "note": null
  },
  "created_at": "2026-06-17T00:00:00Z"
}
```
