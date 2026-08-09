# Coordination Decisions

This file records durable decisions about how Codex agents collaborate in this repository. It should not replace `docs/architecture.md` or `contracts/`.

## ADR-0001: Use Governance-Oriented Codex Development Agents

Date: 2026-06-21

Status: accepted

Decision:

The active Codex development roster is Main Agent, Review Agent, Check Agent, Front Agent, Contract Agent, and temporary Creation Agents. Older feature-module subagent files are retired. Product/runtime contract names such as Context Agent, Writing Agent, Canon Agent, Graph Agent, and QA Agent may remain in contracts as StoryGraph workflow module names, but they are not the current Codex development roster.

Rationale:

The project has moved from architecture setup into MVP implementation. The main coordination need is now planning, contract discipline, UI/API integration, verification, and async handoffs rather than one standing subagent per story workflow module.

## ADR-0002: Use Local Markdown Files For Async Agent State

Date: 2026-06-21

Status: accepted

Decision:

Agents use `.codex/coordination/board.md`, `handoffs.md`, `blockers.md`, `branches.md`, and `decisions.md` to communicate local asynchronous work state.

Rationale:

Frontend, backend, contract, and review work can progress on different timelines. Local Markdown files make ownership, blockers, and handoffs visible without treating chat history as the only source of coordination truth.

Constraints:

Coordination files must not contain secrets, API keys, private manuscript text, draft prose, runtime canon, workflow state, imported documents, or project settings.

## ADR-0003: Use Git Branches To Show Async Workstreams

Date: 2026-06-21

Status: accepted

Decision:

Use local git branches, preferably named `codex/sg-123-short-scope`, to show independent workstreams. Record branch ownership, scope, and review state in `.codex/coordination/branches.md`.

Rationale:

Branch visibility lets agents inspect diffs, compare implementations, and hand off work without blending unrelated changes into a single hidden working tree.

Constraints:

Branches may remain local unless the user asks for push or pull request work. Agents must not force-reset, discard user changes, or use git operations to bypass unresolved contract, review, or canon-safety concerns.

## ADR-0004: Use Proposal Artifacts As The Non-Canon Collaboration Layer

Date: 2026-06-21

Status: accepted

Decision:

StoryGraph will introduce `proposal_artifact_v1` and a Proposal Store for reviewable, versioned collaboration artifacts such as scene draft proposals, fact draft proposals, scene rebuild plans, canon patch proposals, and outline drafts. Agents and authors may revise these artifacts iteratively, but proposal artifacts are not canon, not current scene drafts, and not CandidateFacts until an explicit backend promotion/review action occurs.

Rationale:

The canon safety rule "agents must not directly mutate canon" should not mean "agents cannot work on mutable collaboration material." Long-form writing needs a protected workspace where Agent-generated and author-edited material can be shaped before it becomes accepted prose, pending facts, or reviewed canon changes.

Constraints:

Proposal artifacts must keep project scope, source refs, provenance, version history, status, and review decisions. They must not directly mutate Graph Store, Draft Store, Candidate Store, Event Log, workflow checkpoints, or frontend-only state. Promotion into existing stores must be explicit, permission-gated, and routed through existing backend boundaries.

## ADR-0005: Proposal Evidence Is Supporting CandidateFact Provenance Only

Date: 2026-06-21

Status: accepted

Decision:

`candidate_fact_v1` may use `proposal_artifact` as an evidence kind only as supporting provenance. A CandidateFact still requires a real Draft Store `source_draft_id`, `source_scene_id`, and `source_span`.

Rationale:

Authors need fact-draft collaboration before committing candidates, but proposal body should not become the sole primary evidence for canon-affecting facts.

Constraints:

`fact_draft` promotion must be explicit, require `full` permission, require an accepted proposal version, and submit pending CandidateFacts through ReviewService. Graph Store canon writes remain limited to human seed APIs or CandidateFact accept/edit-accept review paths.

## ADR-0006: Use A Project-Scoped Source Store For Persistent Imported Materials

Date: 2026-08-09

Status: accepted

Decision:

StoryGraph uses `source_document_v1` and a local Source Store for persistent imported TXT, Markdown, and DOCX materials. Source Documents have stable server IDs, normalized project-relative paths, the original-file `checksum_sha256`, client-extracted text, extraction state, provenance, and timestamps. The initial Source Store persists text + metadata JSON, not original file bytes. Import, archive, Agent discussion, and structure analysis require at least `read_generate`; list/detail require read permission.

New persistent Proposal Artifact refs use `kind = source_document` and the stable Source Document ID. Existing optional note/quote/source-span fields may carry bounded review context, but never full text. Existing `imported_document` refs remain valid opaque legacy provenance and are not reinterpreted as Source Store IDs. This decision does not change `proposal_artifact_v1` fields or `candidate_fact_v1`.

Rationale:

Browser-memory imports disappear on restart and require clients to resend private text to Agent routes. A backend-owned, project-scoped Source Store provides durable retrieval and trustworthy provenance while keeping source material outside canon and outside draft/candidate review state.

Constraints:

Source lists never return `extracted_text`; same-project detail may. Cross-project, failed, or archived Source Documents must not reach Agent/structure prompts. Structure analysis resolves one ready Source Document from the route ID; Agent discussion resolves only the explicitly selected `source_document_ids`. Source import/read/archive cannot create Drafts, proposals, CandidateFacts, graph writes, canon events, style samples, vector records, or workflow checkpoints. A Source Document cannot replace the real Draft Store `source_draft_id` required by `candidate_fact_v1`. Archive is non-destructive and v1 has no delete route.

## ADR-0007: Separate UI Locale, Project Language, And Source Language

Date: 2026-08-09

Status: accepted

Decision:

StoryGraph uses `language_policy_v1`. Local `ui_locale` supports `zh-CN` and
`en-US`, defaults to `zh-CN`, and remains a versioned Web/Tauri client preference
outside all story and canon stores. `Project.language` retains its existing field
name and is the authoritative `zh-CN` or `en-US` language for project content.
The backend derives and freezes `output_language` from it for each generation or
workflow operation.

Source Documents carry their own valid canonical BCP 47 language tag or `und`.
`und` is never eligible for Agent or structure prompts. Cross-language reference
is rejected by default and requires explicit source selection/input plus
`cross_language_policy = explicit_reference`; persistent sources use stable IDs,
while legacy inline/text payloads remain compatibility-only. It never translates
the source or changes output language. Legacy inline Agent sources and legacy
text structure requests must supply a valid source language or fail validation
with `422`.

Rationale:

A localized application must allow Chinese UI with English fiction and English
UI with Chinese fiction without mixing display labels into persisted project
data. Immutable output snapshots also keep historical artifacts and resumed
workflows deterministic when an author changes project language.

Constraints:

Project-language changes are provenance-bearing and future-only. They do not
translate, rewrite, relabel, or delete existing sources, drafts, proposals, style
samples, candidates, graph data, or workflow history. Language validation and
cross-language rejection occur before any private text reaches a model provider,
and errors or coordination records must not contain private source or draft text.
