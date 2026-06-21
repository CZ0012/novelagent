# proposal_artifact_v1

`proposal_artifact_v1` defines non-canon collaboration artifacts used by the
Proposal Workspace. A proposal artifact is where an author and Agent can revise
plans, generated draft text, fact drafts, scene rebuild notes, or proposed canon
patches before any explicit promotion into Draft Store, Candidate Store, or
canon review.

Proposal artifacts are runtime project data. They are not coordination Markdown,
not Draft Store records, not CandidateFact records, and not Graph Store canon.

## Required Fields

```json
{
  "contract_version": "proposal_artifact_v1",
  "id": "proposal_001",
  "project_id": "project_fanxing",
  "artifact_type": "scene_draft",
  "status": "drafting",
  "title": "第二章开场提案",
  "body": "作者与 Agent 正在协作修改的非正典内容。",
  "body_format": "markdown",
  "target_refs": [
    { "kind": "scene", "ref": "scene_opening", "note": "目标场景" }
  ],
  "source_refs": [
    { "kind": "imported_document", "ref": "local_doc:fanxing_chronicle" }
  ],
  "provenance": {
    "created_by": "agent",
    "created_via": "llm",
    "workflow_run_id": "run_001",
    "model_ref": "KouriChat/deepseek-v4-flash",
    "note": "根据作者指令生成初稿。"
  },
  "version": 1,
  "derived_refs": [],
  "review_decision": {
    "status": "none",
    "reviewer": null,
    "reviewed_at": null,
    "note": null
  },
  "created_at": "2026-06-21T00:00:00Z",
  "updated_at": "2026-06-21T00:00:00Z"
}
```

## Artifact Types

`artifact_type` MUST be one of:

- `scene_draft`
- `fact_draft`
- `scene_rebuild`
- `canon_patch`
- `outline_draft`

## Statuses

`status` MUST be one of:

- `drafting`: editable proposal work in progress.
- `agent_revised`: latest version was produced by an Agent revision.
- `author_revised`: latest version was edited by the author.
- `ready_for_review`: author has marked the proposal ready for a decision.
- `accepted`: author accepted the proposal artifact as a non-canon proposal.
- `rejected`: author rejected the proposal artifact.

`accepted` does not mean canon acceptance. A proposal accepted here still needs
an explicit backend promotion action before it can become a scene draft,
CandidateFact, or canon review input.

## Source And Target Refs

`source_refs` records evidence or inputs used to create the proposal.
`target_refs` records the project, chapter, scene, draft, candidate, workflow,
or graph object that the proposal concerns.

Each ref object has:

- `kind`: a stable lower-snake-case kind such as `author_instruction`,
  `imported_document`, `draft`, `scene`, `chapter`, `graph_node`,
  `graph_relation`, `candidate_fact`, `context_pack`, `continuity_report`,
  `workflow_run`, `style_sample`, or `proposal_artifact`.
- `ref`: the stable local id or opaque local ref.
- `note`: optional short note.
- `quote`: optional short excerpt. Do not store full chapters or private
  manuscript passages in refs.
- `source_span`: optional structured location metadata.

All refs MUST belong to the same `project_id` unless the ref is an opaque local
document identifier that is only used as import provenance.

## Provenance

`provenance` records how the current version was created:

- `created_by`: author, Agent, or local system actor.
- `created_via`: one of `manual`, `llm`, `import`, `workflow`, or `api`.
- `workflow_run_id`: optional workflow run id.
- `model_ref`: optional provider/model label without secrets.
- `note`: optional short rationale.

API keys, private provider credentials, and full imported document text MUST NOT
be stored in provenance.

## Versioning

`id` is the stable proposal artifact id. `version` is an integer starting at 1.
Author edits, Agent revisions, submit-review actions, accepts, and rejects
create a new version. Implementations MUST retain version history.

Clients MAY send an expected latest version to prevent stale writes. A stale
write MUST be rejected instead of overwriting a newer version.

## Review Decision

`review_decision.status` MUST be one of:

- `none`
- `accepted`
- `rejected`

When `review_decision.status` is `accepted` or `rejected`, `reviewer` and
`reviewed_at` MUST be present. Review decisions are proposal-level decisions
only; they do not commit canon.

## Derived Refs

`derived_refs` records objects created later by explicit backend actions, such
as Draft Store draft ids, CandidateFact ids, workflow run ids, or canon event
ids. A derived ref is audit metadata, not proof that the proposal itself is
canon.

## Promotion Boundaries

Promotion is always a separate backend action. Accepting a proposal does not
promote it.

`scene_draft` proposals MAY be promoted to Draft Store only when:

- `status` is `accepted`.
- `review_decision.status` is `accepted`.
- The target scene is explicit in the request or proposal refs.
- The caller has the local permission level required for author-write actions.

`fact_draft` proposals MAY be promoted to CandidateFact records only when:

- `status` is `accepted`.
- A real Draft Store `source_draft_id` is supplied.
- The source draft belongs to the same project and provides the
  `source_scene_id`, `source_draft_id`, and source span required by
  `candidate_fact_v1`.
- The proposal is recorded only as supporting evidence/provenance; proposal
  body is not the sole primary source for a CandidateFact.
- The resulting CandidateFact records are submitted to ReviewService as pending
  review items and are not committed to Graph Store.

## Canon Safety Invariants

- Proposal artifacts MUST NOT directly mutate Graph Store canon.
- Proposal artifacts MUST NOT directly create Draft Store or CandidateFact
  records without an explicit promotion endpoint.
- Automated fact extraction from proposal content MUST create CandidateFact
  records only through the candidate/review boundary and must preserve proposal
  source refs.
- Canon writes still require human seed APIs or ReviewService accept/edit-accept
  paths with reviewer, rationale, source reference, timestamp, and event log
  provenance.
- Rejected proposals MUST NOT create drafts, candidates, or graph writes.
- Web and Tauri surfaces MUST use the same backend Proposal Store APIs; desktop
  must not introduce a separate proposal or canon-writing path.
