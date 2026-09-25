# proposal_artifact_v1

`proposal_artifact_v1` defines non-canon collaboration artifacts used by the
Proposal Workspace. A proposal artifact is where an author and Agent can revise
plans, generated draft text, fact drafts, scene rebuild notes, or proposed canon
patches before any explicit promotion into Draft Store, Candidate Store, or
canon review.

Language semantics follow `language_policy_v1`.

Proposal artifacts are runtime project data. They are not coordination Markdown,
not Draft Store records, not CandidateFact records, and not Graph Store canon.

## Required Fields

```json
{
  "contract_version": "proposal_artifact_v1",
  "id": "proposal_001",
  "project_id": "project_sample",
  "content_language": "zh-CN",
  "artifact_type": "scene_draft",
  "status": "drafting",
  "title": "第二章开场提案",
  "body": "作者与 Agent 正在协作修改的非正典内容。",
  "body_format": "markdown",
  "target_refs": [
    { "kind": "scene", "ref": "scene_opening", "note": "目标场景" }
  ],
  "source_refs": [
    {
      "kind": "source_document",
      "ref": "source_world_notes",
      "note": "持久资料库来源"
    }
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
- `project_structure_draft`

## Content Language

`content_language` is required for new Proposal Artifacts and follows
`language_policy_v1`. For Agent- or workflow-created artifacts it MUST equal the
server-derived `output_language` frozen for that operation. It is project content
metadata, not UI locale or source language.

Changing `Project.language` affects future proposal versions only. Existing
proposal bodies, titles, and language snapshots are never translated, rewritten,
or relabeled. Legacy proposals without this field remain readable only through
the inferred compatibility projection defined by `language_policy_v1`.

A revision that changes `content_language` is a content rewrite, not a metadata
relabel. It MUST atomically supply every proposal-authored natural-language
content field in the new language; in v1 those content fields are `title` and
`body`, so both require complete replacements. Proper names, stable identifiers,
and bounded verbatim source quotations remain subject to the exceptions in
`language_policy_v1`. Any newly generated human-readable ref, provenance, or
review note MUST also follow the version snapshot, while preserved historical
audit text and verbatim quotations are not silently translated. If validation
or persistence of any rewritten field fails, the store MUST create no new
version.

Versions created only to change status, record a review decision, or append
`derived_refs` MUST preserve the previous version's exact `content_language`.
They MUST NOT adopt the project's current language or a request-supplied
different language merely because `Project.language` changed.

A legacy proposal whose `content_language` is absent has unknown historical
language. A compatibility projection may display an inferred value with
`language_inferred = true`, but that value is not a confirmed snapshot. Such a
proposal MUST NOT be made ready, reviewed, accepted, rejected, promoted, or
given derived refs until an explicit content revision atomically supplies a
confirmed `content_language` and complete replacement `title` and `body`.
Supplying only a language tag, performing a state-only transition, or copying
the current `Project.language` MUST NOT convert unknown legacy content into a
confirmed-language version.

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
  `source_document`, `draft`, `scene`, `chapter`, `graph_node`,
  `graph_relation`, `candidate_fact`, `context_pack`, `continuity_report`,
  `workflow_run`, `style_sample`, or `proposal_artifact`.
- `ref`: the stable local id or opaque local ref.
- `note`: optional short note.
- `quote`: optional short excerpt. Do not store full chapters or private
  manuscript passages in refs.
- `source_span`: optional structured location metadata.

All resolvable refs MUST belong to the same `project_id`.

`source_document` is the canonical kind for a persistent Source Store record.
Its `ref` is the stable `SourceDocument.id`; producers may record a short note,
bounded quote, or consumed offsets inside the existing optional fields when
needed for review. Full source text and absolute local paths must not be copied
into a ref.

Legacy `imported_document` refs remain valid opaque provenance for artifacts
created by transient pre-Source-Store clients. They do not resolve to a Source
Document, and new Source Store-backed routes must not emit them. This is a ref
kind clarification only; `proposal_artifact_v1` adds no field and existing
artifacts require no migration.

### Exact Draft Baselines And Client Diff

Proposal version history and existing refs are sufficient to support a
review-time Draft comparison; this contract does not add a diff field or change
the Proposal Artifact shape/version.

For a selected Proposal Artifact version, a client resolves its recorded Draft
baseline from that version's `source_refs` whose `kind` is `draft`:

- One unique referenced Draft id is an exact recorded baseline. The client MAY
  fetch it through
  `GET /projects/{project_id}/scenes/{scene_id}/drafts/{draft_id}` and compute a
  display diff against that exact proposal version.
- Zero referenced Draft ids means the proposal has no recorded Draft baseline.
  The client must say so rather than comparing against the current or latest
  Draft.
- More than one unique referenced Draft id is ambiguous. The client must expose
  that ambiguity and MUST NOT silently choose the current, latest, or first
  Draft.

The exact Draft read requires local read permission and succeeds only when the
Draft's stored `project_id` and `scene_id` both match the route. Missing,
cross-project, and cross-scene ids use the same not-found behavior without
revealing Draft metadata. Historical and discarded Drafts remain readable by
this exact id route because stable proposal provenance may refer to them; the
route never substitutes another or latest version.

When Agent discussion includes a saved Draft, a current client pins that input
with `included_draft_id`. The backend-resolved Draft sent to the provider and
the resulting Proposal version's unique `source_refs[kind = draft]` MUST use
that same id. The visible input manifest is not permission to replace it with a
newer Draft. Invalid or cross-scope pinned ids fail before provider use or
Proposal creation; only legacy clients that omit the additive field retain the
documented latest-Draft compatibility path.

Proposal history, exact Draft responses, and the selected versions are the
persisted inputs. Diff hunks, comparison mode, expanded rows, and unsaved/dirty
editor state are client-only transient presentation state. They MUST NOT be
written into Proposal Store, Draft Store, Source Store, Graph Store, workflow
state, or another story store. A diff compares stored text verbatim and MUST NOT
translate or rewrite either side.

## Provenance

Agent runtime presets and `continue_scene` follow `agent_runtime_v1`.
Continuation retains the complete exact pinned Draft as the Proposal body
prefix, appends only new validated prose, and records that unique Draft source
ref. It does not overwrite the Draft. Generated Proposal notes may include the
selected preset's stable ID and SHA256 instruction hash; full custom System
prompts are not copied into provenance. No Proposal shape change is required.

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
- The request supplies an explicit target `scene_id`.
- The caller has the local permission level required for author-write actions.

Before creating a Draft or recording any derived ref, the backend MUST resolve
the target as follows:

- Collect the distinct non-empty `ref` values from proposal `target_refs` whose
  `kind` is `scene`.
- If the proposal declares one unique Scene target, it MUST equal the request
  `scene_id`.
- If it declares more than one unique Scene target, the proposal is ambiguous
  and cannot be promoted.
- If it declares no Scene target, the explicit request `scene_id` MAY be used
  for compatibility with legacy proposals.
- The resolved request Scene and proposal MUST belong to the route project.

A target mismatch, ambiguity, or out-of-scope Scene is a `409` conflict.
Project, proposal version/status/type/language, Scene target, and existing
derived-ref checks MUST complete before any Draft or derived Proposal version is
written. A rejected attempt creates no Draft and no derived ref.

Draft promotion is idempotent for a proposal that already has exactly one
`derived_refs` entry whose `kind` is `draft`. After the same target and scope
checks, the backend MUST verify that the referenced Draft exists and belongs to
the same project and resolved Scene, then return that same Draft and current
Proposal without creating a Draft or Proposal version. More than one derived
Draft ref is ambiguous; a referenced Draft that is missing, cross-project, or
cross-scene is a `409` conflict rather than permission to create a replacement.
Zero derived Draft refs follows the normal explicit promotion path. The
successful response shape remains `{ "proposal": ..., "draft": ... }`.

For that existing-derived success path, `expected_version` protects only the
initial write attempt. A retry MAY still carry the original pre-derivation
version after its first successful response was lost; once the current Proposal
and its one exact derived Draft pass all status, type, language, target, and
scope checks, the backend returns them instead of rejecting solely as stale.

The initial Draft write and derived-ref write are separate local stores in the
MVP. They are serialized within one running API process. If the derived-ref call
raises synchronously, the backend first checks whether that exact ref was in fact
committed; if so it returns the completed promotion. Otherwise it MUST remove
only the exact unchanged Draft created by that attempt before returning failure,
so the rejected request leaves neither artifact behind. Recovery from a process
or machine crash between the two stores remains a separate reconciliation task;
this limitation does not permit ordinary synchronous errors or concurrent
requests to leave an orphan Draft.

`fact_draft` proposals MAY be promoted to CandidateFact records only when:

- `status` is `accepted`.
- A real Draft Store `source_draft_id` is supplied.
- The source draft belongs to the same project and provides the
  `source_scene_id`, `source_draft_id`, and source span required by
  `candidate_fact_v1`.
- The `fact_draft` body may contain author-editable explicit fact markers that
  the backend parses into CandidateFact records, but those markers must remain
  tied to the supplied real source draft for provenance.
- The proposal is recorded only as supporting evidence/provenance; proposal
  body is not the sole primary source for a CandidateFact.
- The resulting CandidateFact records are submitted to ReviewService as pending
  review items and are not committed to Graph Store.

`project_structure_draft` proposals MAY be applied to official project
structure only when:

- `status` is `accepted`.
- `review_decision.status` is `accepted`.
- The proposal `body_format` is `structured_json`.
- The body contains a bounded JSON object with proposed `chapters` and nested
  `scenes`; it must not contain the full imported manuscript.
- The caller has the local permission level required for author-write actions.
- Applying the proposal may create Chapter and Scene Graph Store nodes with
  author-review provenance, but it must not create CandidateFacts, canon facts,
  characters, locations, world rules, or other story bible nodes in the same
  action.
- The proposal is recorded as provenance for created Chapter/Scene nodes and
  derived refs are recorded back on the proposal.
- Repeating the same apply action for an already-derived proposal MUST be
  idempotent: implementations should return the previously derived Chapter and
  Scene nodes, avoid duplicate Graph Store writes, and reject only when a target
  node id is already owned by unrelated provenance.

## Canon Safety Invariants

- A selected source language never changes `content_language`; cross-language
  sources follow `language_policy_v1` and are never translated automatically.
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

## Structure apply validation and repeat requests

Before applying an accepted project structure, the API checks every proposed Chapter, Scene and expected relationship ID for incompatible existing records, including archived nodes and relation collisions. A predictable target conflict must fail before any graph node, relationship, event or derived reference is created. Applies are serialized within one API process. A fully applied structure may return its original derived nodes on a retry carrying the original expected version only after validating the complete graph structure and recorded derived references; a partial or mismatched structure remains a conflict. This preflight does not provide a cross-store hard-crash transaction guarantee.

For a first application, the API also validates the normalized narrative fields
against the Proposal's confirmed `content_language`, including short headings,
as described in `language_policy_v1`. A language stamp alone is not proof that
the structure body satisfies it. Rejection creates no graph objects, events,
or derived refs and does not modify the Proposal. A previously fully applied
structure that passes the existing scope, provenance, and confirmed-language
checks retains its read-only idempotent retry even if its historical wording
would fail the newer short-field guard. This does not relax the pre-existing
unknown-language review gate. No existing Chapter, Scene, Proposal body, or
language snapshot is automatically rewritten, translated, or relabeled.
