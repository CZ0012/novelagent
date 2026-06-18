# Workflow Run Contract v1

## Purpose

`workflow_run_v1` defines the persisted state of a StoryGraph workflow run.

The MVP stores LangGraph-shaped checkpoints locally so scene generation can be inspected, paused for human review, and resumed. This contract is the boundary for API, CLI, workbench, and future LangGraph runtime integration.

## Producers And Consumers

- Primary producer: Director / workflow orchestrator.
- Primary consumers: API run endpoints, CLI/workbench run panels, Canon Agent review flow, QA Agent.
- Related contracts: `review_payload_v1`, `context_pack_v1`, `continuity_report_v1`, `candidate_fact_v1`.

## Governed API Routes

- `POST /projects/{project_id}/scenes/{scene_id}/runs/scene-generation`
- `GET /projects/{project_id}/runs`
- `GET /runs/{run_id}`
- `GET /runs/{run_id}/events`
- `POST /runs/{run_id}/resume-review`

## Required Top-Level Fields

- `contract_version`: must be `workflow_run_v1`
- `id`
- `workflow_name`
- `project_id`
- `scene_id`
- `status`
- `current_step`
- `steps`
- `review_payload`
- `created_at`
- `updated_at`

## Workflow Names

The only required v1 workflow name is:

- `scene_generation`

Future v1-compatible workflows may add names without changing the shape if they preserve the run and review invariants below.

## Run Status Values

Allowed v1 statuses:

- `running`: a workflow is actively executing.
- `awaiting_review`: the workflow is paused on human review and must not continue automatically.
- `needs_revision`: QA found issues that should be fixed before extraction or review.
- `completed`: the workflow ended successfully.
- `blocked`: required context, canon, or infrastructure was missing.
- `failed`: execution failed unexpectedly.

`current_step` may use `END` as the terminal marker after successful completion.

## Step Fields

Each `steps` item must include:

- `name`
- `status`
- `started_at`
- `completed_at`
- `artifact_refs`
- `message`

Allowed step statuses:

- `pending`
- `running`
- `completed`
- `skipped`
- `failed`

## Required Scene Generation Steps

The v1 `scene_generation` workflow should expose these step names in order:

- `build_context`
- `write_draft`
- `check_continuity`
- `extract_state`
- `human_review`

## Review Payload

`review_payload` must follow `review_payload_v1`.

When a run has `status = awaiting_review`, `review_payload.status` must be `pending` and must reference the candidate facts that require author decisions.

## Invariants

- Workflow state is operational state, not canon.
- A workflow run must not directly mutate graph canon.
- `needs_revision` and `blocked` runs must not proceed to state extraction.
- State extraction may only produce `CandidateFact` records.
- `awaiting_review` must pause until every referenced candidate has a non-pending review decision.
- Completing a review pause must not imply every candidate was accepted; it only means every candidate was decided.
- Every artifact reference must be a stable ID or contract reference, not embedded full prose.

## Minimal Example

```json
{
  "contract_version": "workflow_run_v1",
  "id": "run_001",
  "workflow_name": "scene_generation",
  "project_id": "project_001",
  "scene_id": "scene_014",
  "status": "awaiting_review",
  "current_step": "human_review",
  "steps": [
    {
      "name": "build_context",
      "status": "completed",
      "started_at": "2026-06-17T00:00:00Z",
      "completed_at": "2026-06-17T00:00:01Z",
      "artifact_refs": {"context_pack_id": "context_scene_014"},
      "message": null
    },
    {
      "name": "human_review",
      "status": "pending",
      "started_at": null,
      "completed_at": null,
      "artifact_refs": {},
      "message": null
    }
  ],
  "review_payload": {
    "contract_version": "review_payload_v1",
    "status": "pending",
    "candidate_ids": ["fact_001"],
    "source_draft_id": "draft_014_v3",
    "note": "State extraction produced CandidateFact records awaiting review."
  },
  "created_at": "2026-06-17T00:00:00Z",
  "updated_at": "2026-06-17T00:00:04Z"
}
```
