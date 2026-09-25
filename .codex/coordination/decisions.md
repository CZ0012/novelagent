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

## ADR-0008: Use Exact Provenance And Explicit Targets For Reviewable Rewrites

Date: 2026-08-09

Status: accepted

Decision:

StoryGraph review flows resolve persisted provenance exactly instead of guessing
from whichever Draft or Source happens to be current. A Source-to-Agent handoff
selects only the stable Source Document ID in transient client state. A Proposal
diff uses the selected Proposal version's one unique Draft source ref; no ref is
reported as no baseline and multiple refs are reported as ambiguous, with no
fallback to the latest Draft.

The client keeps pane dimensions, diff presentation, and unsaved editor state as
UI-only state. It blocks Agent sends that would omit or replace unsaved Draft
text, and blocks Proposal lifecycle or navigation actions while Proposal edits
are dirty. Scene-draft promotion always carries an explicit request Scene,
validates any Proposal Scene target before writing, and reuses one
already-derived same-project/same-scene Draft for repeat-safe responses.

When the current workbench includes a saved Draft, it pins the manifest record
with `included_draft_id`. The backend/provider Draft and resulting Proposal
Draft source ref use that same scoped id; latest-Draft fallback is legacy
no-id compatibility only.

Rationale:

Authors need to see exactly which saved text an Agent used and exactly what will
change before accepting a rewrite. Stable refs, visible input manifests, dirty
guards, and explicit targets prevent silent latest-version substitution,
cross-scene writes, and accidental loss of local edits while preserving the
Proposal Workspace as a non-canon review layer.

Constraints:

Source-to-Agent navigation does not copy source text, call a provider, create an
artifact, or change cross-language policy. Resizable Source pane preferences are
versioned local UI dimensions only and contain no story data. Diff output is not
persisted or translated. Promotion target, scope, language, version, and derived
Draft checks occur before story-store writes; synchronous cross-store failure is
compensated so a rejected request leaves no new Draft or derived ref. Proposal
acceptance or Draft promotion never writes CandidateFact, Graph Store canon, or
canon Event Log. Rich-document import and long-document chunking remain separate
future work.

## 2026-09-13 — SG-023B Agent runtime preferences and continuation

Reusable Agent presets are workspace-local author settings, with immutable built-ins and bounded custom System prompt text. Selection is a default for subsequent creative calls and is frozen per service; extraction/structure/continuity logic does not receive these style preferences. Existing settings requests preserve omitted provider/credential/preset values. Audit markers store only stable preset ID plus prompt SHA256.

A new `continue_scene` mode requires the exact saved Draft ID. The provider sees a bounded ending excerpt; the server appends validated continuation text to the complete original Draft in a separate scene-draft Proposal. Review and promotion remain explicit existing operations. Model discovery uses only the configured generic provider's actual model-list results and never changes the saved model automatically. Error bodies and connection reasons are excluded from surfaced diagnostics because third-party responses can echo private inputs.

## 2026-09-13 — SG-023 author UX and persistence boundaries

Use four everyday writing tabs with an optional tools/review inspector. Web catalogs must not import another locale at runtime; desktop native strings use separate JSON catalogs. UI locale remains independent from story output language and author content. Explicit settings select a persistent empty graph by default; memory/demo behavior must be requested explicitly in such workspaces. Structure application preflights predictable conflicts and verifies completed derived refs on retries, without claiming hard-crash transactions across graph and SQLite. A real authorized chapter was tested in an isolated ignored workspace through third-party identifiers from the configured endpoint, without changing the author's original model configuration or accepting generated canon.

## 2026-09-13 — SG-024 prevent partial desktop updates

The identified NSIS copy order allowed a new shell with an old locked backend. Require pre-install checks before any application binary copy; use exact installation-path backend cleanup and a bounded exclusive-write probe, so old updater clients also benefit. Native prepare/cancel commands gate managed backend restarts and preserve termination failure. Web downloads first and protects unsaved author text before prepare/install. Runtime backend version uses read-only health metadata with legacy OpenAPI fallback; unknown and mismatch remain explicit. Software repair/release never changes local author workspaces or their provider settings.


## SG-025 — Editor-first collaboration and historical titles

Keep the existing backend contracts and unique parent editor state while moving Agent interaction beside prose. Chapters disclose child scenes; scene leaves open the editor. Generated changes retain Proposal review and exact-Draft comparison. Known genre enums localize for display, but persisted author titles are edited only through explicit metadata saves. New structure generation and first application validate language, including short headings; verified completed applications retain retry compatibility. No automatic model retry or historical content translation.

## SG-026 — Explicit repair rather than hidden title translation

Known graph model labels are UI-localized. Historical chapter/scene titles and planning summaries are author data: an explicit metadata-only generation creates a narrow canon_patch for review, then a separate apply preserves original node IDs and relationships. New structure-language validation also covers timeline_position. Update readiness retries transient sharing locks only; diagnostics and delivery do not stop the author application.

## SG-027 — Actual manuscript rather than blank outline forms

Chapter selection projects saved scene prose, and empty planned scenes receive explicit source-adoption/writing/generation choices. Preview/Edit keep one Draft state. Exact UTF-16 range plus pinned saved Draft supports repeated-text revision. Red/green review stays client-only and does not mutate story content. New chapter/volume generation is a strict reviewed composition proposal; volume grouping uses existing Chapter.volume_index and readable metadata. Source adoption preserves original text with explicit range/language/freshness checks, never inventing links from legacy opaque import refs.

## SG-028 execution boundary

Protocol compatibility is explicit: default legacy Chat Completions remains stable; Responses and Anthropic Messages are selected by saved endpoint profiles and tested independently. A role may inherit the default or use an explicit profile/model; failures never silently fall back or trigger another paid call. Responses transport support does not imply enabling remote built-in tools, conversation storage or autonomous canon writes. Preserve the author's current exact model identifier in live tests; no substitution.
