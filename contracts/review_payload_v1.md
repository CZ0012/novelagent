# Review Payload Contract v1

## Purpose

`review_payload_v1` defines the human-review pause payload emitted by a workflow after state extraction produces candidate facts.

A Review Payload is not a canon write request by itself. It tells the author or workbench which `CandidateFact` records need a decision before the workflow can complete.

## Producers And Consumers

- Primary producer: Scene generation workflow after successful state extraction.
- Primary consumers: Director, Canon Agent review flow, API/workbench run panels.
- Related contracts: `workflow_run_v1`, `candidate_fact_v1`, `graph_store_v1`.

## Required Top-Level Fields

- `contract_version`: must be `review_payload_v1`
- `status`
- `candidate_ids`
- `source_draft_id`
- `note`

## Status Values

Allowed v1 statuses:

- `none`: no active human-review pause is waiting on this payload.
- `pending`: one or more candidates require human review.

## Candidate References

`candidate_ids` must contain stable `CandidateFact.id` values.

When `status` is `pending`:

- `candidate_ids` should not be empty.
- `source_draft_id` should identify the draft that produced the candidates.
- every referenced candidate must remain non-canon until reviewed.

When `status` is `none`, consumers must not treat `candidate_ids` as pending work even if historical IDs are retained for audit context.

## Invariants

- A Review Payload must not contain draft prose.
- A Review Payload must not duplicate full candidate records; use `candidate_ids`.
- A pending payload must not mutate the Graph Store.
- A workflow may resume from review only after all referenced candidates leave `review.status = pending`.
- Accepting or editing candidates must go through the Canon Agent review flow and `GraphStore.commit_candidate_fact`.
- Rejecting or deferring candidates must preserve audit history.

## Minimal Example

```json
{
  "contract_version": "review_payload_v1",
  "status": "pending",
  "candidate_ids": ["fact_001", "fact_002"],
  "source_draft_id": "draft_014_v3",
  "note": "State extraction produced CandidateFact records awaiting review."
}
```
