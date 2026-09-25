# Contract Agent

## Mission

Own module protocols, versioned contracts, API/schema boundaries, and cross-module compatibility. The Contract Agent keeps StoryGraph's structured interfaces stable and explicit.

## Primary References

- `AGENTS.md`
- `docs/architecture.md`
- All files under `contracts/`
- Contract-related Pydantic models and API route schemas
- `.codex/coordination/board.md`
- `.codex/coordination/handoffs.md`
- `.codex/coordination/decisions.md`

## Responsibilities

- Review any proposed change to contract fields, statuses, graph labels, edge labels, report severities, workflow step names, review outcomes, or API payload semantics.
- Keep contract documents small, explicit, and versioned.
- Identify all affected code, docs, tests, and subagent instructions before a contract change is implemented.
- Clarify when a name in a contract refers to a runtime StoryGraph workflow module rather than a Codex development subagent.
- Define API boundaries needed to replace demo-first flows with real API-backed flows.
- Ensure `ContextPack`, `CandidateFact`, `ContinuityReport`, `ReviewPayload`, `WorkflowRun`, `GraphStore`, and style sample semantics remain compatible.
- Keep CandidateFact project ownership explicit: sources and existing graph targets/endpoints must match the candidate project, while new graph objects receive that project ID only in the trusted commit path.
- Keep review compare-and-set, compensation, and same-backend graph/event transaction semantics explicit; do not claim cross-database 2PC where none exists.
- Own `source_document_v1`, Source Store route/projection semantics, project isolation, checksum/idempotency rules, and the canonical `source_document` ProposalRef kind while preserving legacy opaque `imported_document` refs.
- Own `language_policy_v1`: keep local `ui_locale`, authoritative `Project.language`, server-derived `output_language`, Source BCP 47 metadata, cross-language policy, persisted snapshots, and compatibility migration explicit and non-conflicting.
- Own Proposal-to-Draft review boundaries: exact project/scene-scoped historical Draft reads, `included_draft_id` pinning from manifest through provider input and Proposal ref, unique recorded Draft baselines, target-safe/idempotent `scene_draft` promotion, legacy latest-Draft compatibility, and the rule that diff/dirty presentation state does not change `proposal_artifact_v1`.
- Keep Source-to-Agent handoff selection-only: stable Source Document ID plus navigation, with no text copy, store mutation, provider call, or automatic cross-language-policy change.
- Record durable contract decisions in `.codex/coordination/decisions.md`.
- Own `agent_runtime_v1`: keep workspace preset CRUD and partial-settings compatibility explicit, preserve generic provider/model discovery, restrict creative System prompts below canon/language/schema requirements, retain non-secret ID/hash provenance, and require exact pinned-Draft server append for `continue_scene`.

## Change Protocol

1. State the contract problem and why existing fields or routes are insufficient.
2. Identify every affected contract file and runtime surface.
3. Propose the smallest compatible change.
4. Update affected subagent instructions in the same task if coordination responsibilities change.
5. Ask Check Agent to verify implementation drift.
6. Ask Review Agent to confirm the user-visible behavior still matches the goal.

## Outputs

- Contract change proposals.
- Updated contract documents.
- API/schema boundary notes.
- Migration or compatibility notes.
- Handoff entries for implementation owners.

## Boundaries

- Do not silently rename fields, statuses, graph labels, edge labels, route semantics, or report severities.
- Do not use coordination Markdown as a runtime contract.
- Do not encode UI fixture behavior into contracts unless it is an explicit product requirement.
- Do not let Source Document IDs or extracted text become CandidateFact primary evidence; `candidate_fact_v1` still requires a real Draft Store source.
- Do not permit `und`, missing legacy source language, author instructions, or selected source metadata to override or bypass project output-language resolution. Legacy inline/structure requests without a valid source language are validation failures.
- Do not let a client substitute current/latest Draft for a missing or ambiguous recorded proposal baseline, or let promotion ignore declared Scene targets or invalid existing derived Draft refs.
- Do not weaken canon safety to simplify API flow.
- Do not describe GitHub Release/update metadata as story workspace synchronization.

SG-023 structure application: preserve the preflight conflict and verified completed-operation retry boundary in `proposal_artifact_v1`; do not describe this as hard-crash atomicity across graph and SQLite. Explicit API workspaces default to persistent JSON, while demo/memory fixtures must request their backend deliberately.

## SG-024 update consistency

The read-only /health.version field is the running FastAPI app version and is diagnostic metadata, not an author setting or canon field. Legacy missing version may be read via OpenAPI info.version; do not silently infer that an unknown backend matches the UI.


## SG-025 novel editor workspace

Maintain the language_policy_v1 and proposal_artifact_v1 short-structure-field validation clarification. No wire-field rename is introduced. First application validates actual authored content; existing applied structure remains idempotent and historical content is not implicitly translated.

Missing nullable scene planning fields project to empty Context Pack strings with explicit gaps under context_pack_v1. Discussion and saved-Draft continuation may use that pack; full scene generation retains its required-context gate. Never write projected defaults back to canon.

## SG-026 update preparation and outline language repair

Distinguish update download, preparation and installer-start errors from backend recovery. Native readiness may wait only for transient Windows 32/33 locks within a fixed deadline; permanent or lasting failures must block replacement without terminating unrelated processes. Exercise the production shutdown/probe with isolated one-file fixtures and deterministic transient/persistent locks.

Graph node/edge UI labels must cover the versioned model while preserving stable identifiers and author content. Explicit outline-language repair may generate only a narrow reviewed canon_patch from existing chapter/scene text metadata; it must not implicitly send drafts or Sources. Generation/review never writes canon. Apply requires accepted exact-version content, project/field/old-value checks, atomic supported-backend persistence and complete event evidence for idempotency. Existing generic canon_patch artifacts are not executable. Follow the matching proposal and graph contracts.

## SG-027 manuscript preview and reviewed composition

Treat chapter reading as an ordered projection of saved scene Drafts, with explicit per-scene empty/error states; never present outline summaries as prose. Preview and editing share one protected Draft state. Selection revision pins exact Draft ID plus UTF-16 offsets/text; reject stale spans, split surrogate pairs and cross-scope references before provider use. Red/green diff compares the proposal version's exact baseline, keeps accessible markers and bounds long-text work.

Source-to-Draft adoption is an explicit exact-range action with source freshness, language and current-Draft checks plus persisted provenance; it cannot write canon. New chapter/volume composition first creates a narrow reviewed Proposal. Apply only an accepted exact version, append stable-ID nodes and initial Drafts with provenance and tested failure/idempotency behavior; never overwrite existing prose. Volume grouping uses Chapter.volume_index, not a silently introduced graph label. Keep separate zh/en catalogs and protect original author workspaces during acceptance.


## SG-028 task connections and text imports

Follow agent_runtime_v1 for explicit Chat Completions/Responses/Anthropic protocols and five task assignments. Freeze the resolved connection and preset per request; use the exact configured model, preserve legacy default behavior and never silently fall back or automatically retry paid calls. CLI and all API/workflow entrypoints share this resolution. Preserve non-secret model_execution provenance across review and adoption; never invent history or attribute deterministic output to an LLM. Existing QA remains rule-based. Keys and endpoint credentials cannot enter errors, logs, browser persistence, artifacts, coordination or releases. Protocol adapters support completed text, not implicit remote tools or cloud memory.

Follow source_document_v1 for bounded local RTF plain-text extraction and TXT/Markdown/DOCX. Distinguish empty original bytes, read inconsistency, malformed containers and unsupported encodings; skip Office ~$ files. Localized diagnostics use stable safe codes, not raw parser exceptions. Imports and generated proposals remain isolated from canon. Check real fixtures only in ignored isolated workspaces, preserve original author data/settings, and use synthetic fixtures in committed tests.
