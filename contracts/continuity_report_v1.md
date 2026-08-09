# Continuity Report Contract v1

## Purpose

`continuity_report_v1` defines how continuity, canon, timeline, knowledge-boundary, and style-adjacent issues are reported.

The report should help revise the smallest necessary part of a draft or plan. It must not rewrite the scene by itself.

## Producers And Consumers

- Primary producer: QA Agent.
- Primary consumers: Director, Writing Agent, Canon Agent, author review flow.
- Related contracts: `context_pack_v1`, `candidate_fact_v1`, `graph_store_v1`,
  `language_policy_v1`.

## Required Top-Level Fields

- `contract_version`: must be `continuity_report_v1`
- `project_id`
- `output_language`: language snapshot of the checked draft or generation run
- `scene_id`
- `draft_id`
- `context_pack_id`
- `status`
- `summary`
- `issues`
- `checked_dimensions`
- `provenance`
- `created_at`

## Status Values

Allowed report statuses:

- `pass`
- `needs_revision`
- `blocked`
- `inconclusive`

## Checked Dimensions

Common v1 dimensions:

- `knowledge_boundary`
- `timeline`
- `location_state`
- `relationship_state`
- `world_rule`
- `foreshadowing`
- `causality`
- `pov`
- `style_constraint`
- `language_consistency`

## Issue Fields

Each issue must include:

- `id`
- `issue_type`
- `severity`
- `description`
- `violated_nodes`
- `evidence`
- `suggestion`
- `blocking`

## Issue Types

Common v1 `issue_type` values:

- `knowledge_boundary_violation`
- `timeline_conflict`
- `location_conflict`
- `relationship_conflict`
- `world_rule_conflict`
- `foreshadowing_mismatch`
- `causal_gap`
- `pov_leak`
- `style_drift`
- `wrong_output_language`
- `mixed_output_language`
- `missing_required_element`
- `unsupported_new_fact`

## Severity Values

Allowed severities:

- `low`
- `medium`
- `high`
- `critical`

`critical` means the draft should not proceed to extraction or canon review until revised.

## Evidence Fields

Each evidence item should include:

- `kind`: `draft_text`, `context_pack`, `graph_fact`, `candidate_fact`, or `author_instruction`
- `ref`
- `quote`
- `note`

Quotes should be short and review-oriented.

## Invariants

- `output_language` is frozen from the checked Draft or WorkflowRun rather than
  the UI locale or current project setting. Generated `summary`, issue
  `description`, evidence `note`, and `suggestion` fields follow that snapshot;
  bounded verbatim evidence quotes may retain their source language.
- Language checks follow `language_policy_v1`. Machine-readable dimensions and
  issue types remain stable identifiers; selected-source quotations and proper
  names are not by themselves mixed-language violations.
- Reports must distinguish canon violations from weak style preferences.
- Reports must identify the smallest likely fix.
- Reports must not mutate drafts, candidates, or graph state.
- `blocked` should be used when required canon or context is missing.
- If a report cites graph state, it must include stable graph IDs.

## Minimal Example

```json
{
  "contract_version": "continuity_report_v1",
  "project_id": "project_001",
  "output_language": "en-US",
  "scene_id": "scene_014",
  "draft_id": "draft_014_v3",
  "context_pack_id": "context_scene_014_v1",
  "status": "needs_revision",
  "summary": "The draft reveals knowledge the POV character should not have yet.",
  "issues": [
    {
      "id": "issue_001",
      "issue_type": "knowledge_boundary_violation",
      "severity": "high",
      "description": "The POV character infers a lineage secret that the Context Pack marks as unknown.",
      "violated_nodes": ["character_linj", "secret_lineage"],
      "evidence": [
        {
          "kind": "draft_text",
          "ref": "draft_014_v3",
          "quote": "He suddenly understood whose blood he carried.",
          "note": "This exceeds the allowed knowledge boundary."
        }
      ],
      "suggestion": "Change the realization into noticing an unexplained reaction to the old royal mark.",
      "blocking": false
    }
  ],
  "checked_dimensions": ["knowledge_boundary", "timeline", "location_state"],
  "provenance": {
    "graph_query_ids": [],
    "context_pack_ref": "context_scene_014_v1"
  },
  "created_at": "2026-06-17T00:00:00Z"
}
```
