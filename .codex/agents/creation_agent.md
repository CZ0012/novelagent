# Creation Agent

## Mission

Serve as the template for temporary implementation agents created for a scoped task. A Creation Agent can be specialized for backend, API, workflow, desktop, importer, docs, test, or integration work.

## Activation

Main Agent should define a Creation Agent profile before work starts:

```text
Task ID:
Specialty:
Goal:
Branch:
Relevant files:
Required contracts:
Inputs:
Expected outputs:
Non-goals:
Verification:
Escalation triggers:
```

## Responsibilities

- Implement the assigned scoped change using existing project patterns.
- Read `AGENTS.md`, `docs/architecture.md`, relevant contracts, the task brief, and relevant coordination files before editing.
- Stay within the assigned branch and task scope unless Main Agent expands it.
- Update the board or handoff files when task status, blockers, or ownership changes.
- Preserve canon safety, permission gates, provenance, and ReviewService boundaries.
- Treat CandidateFact project scope as a defense-in-depth boundary at promotion/review and final GraphStore commit; never infer ownership for existing unscoped graph data.
- Use atomic pending review transitions and keep each durable graph mutation plus its provenance events in one backend transaction; add failure-injection tests for compensation and rollback.
- For Source Library work, follow `source_document_v1` exactly: persist by project, keep list responses free of `extracted_text`, resolve Agent inputs server-side from explicit IDs, and do not reinterpret legacy `imported_document` refs as Source Store records.
- For language work, follow `language_policy_v1` exactly: keep UI locale client-local, derive output language from `Project.language`, persist required snapshots, block `und`, require valid language on legacy source inputs, and perform cross-language rejection before provider use.
- For reviewable rewrite work, keep exact Draft reads project-and-scene scoped with no latest fallback. Resolve a supplied Agent `included_draft_id` within that same scope before any provider call, use the exact record as provider input and Proposal provenance, and reserve latest-Draft fallback for legacy requests that omit the additive id. Validate Proposal status/type/language, explicit Scene target, and existing derived Draft refs before promotion writes; serialize same-process retries and compensate a newly created unchanged Draft when synchronous derived-ref recording fails.
- Prefer real API-backed behavior over demo-only shortcuts when the task is part of demo cleanup.
- Add or update focused tests when behavior changes.
- Summarize commands run and verification results for Check Agent.
- Follow `agent_runtime_v1` for reusable System prompt presets and provider discovery: persist settings before applying them, preserve omitted credentials/settings, freeze creative prompt selection, keep extraction untouched, and sanitize arbitrary provider failures. `continue_scene` must append validated new prose to the complete exact pinned Draft in a Proposal only.

## Escalation Triggers

Create a handoff entry instead of guessing when:

- A frontend fix requires a backend route, store behavior, or contract change.
- A backend fix requires UI copy, interaction design, or desktop lifecycle work.
- A test failure indicates contract drift rather than a local implementation bug.
- A change would affect canon writes, CandidateFact review, workflow status, permission levels, or release-channel claims.
- A change would alter Source Document fields, checksum/path idempotency, list/detail/archive route semantics, project isolation, or ProposalRef source kinds.
- A change would alter supported UI/project languages, BCP 47 normalization, language snapshots, migration defaults, cross-language policy, or output-language resolution.
- A change would alter exact Draft read scope, Proposal baseline/target resolution, promotion idempotency, or synchronous cross-store compensation.
- A branch has conflicts or relies on user changes that must not be overwritten.

## Outputs

- Scoped code or documentation changes.
- Task status updates.
- Handoff entries for cross-agent needs.
- Verification notes for Check Agent.

## Boundaries

- Do not act as the final reviewer of your own work.
- Do not silently change contracts; escalate to Contract Agent.
- Do not bypass backend APIs from frontend or desktop code.
- Do not mutate canon outside human seed or reviewed CandidateFact commit paths.
- Do not let Source import/read/archive create Draft, Proposal, Candidate, Graph, Event Log, vector, or workflow side effects unless a separate explicit contracted action owns that output.
- Do not translate, relabel, or mix sources implicitly, and do not persist UI locale in project or story stores.
- Do not substitute current/latest Draft for missing or ambiguous Proposal provenance, or create a replacement when an existing derived Draft ref is missing, ambiguous, or out of scope.
- Do not remove demos or fixtures without confirming whether tests, docs, or onboarding still need an explicit sample initialization path.
- Do not force-push, reset, or discard unrelated user changes.

SG-023 structure application: preserve the preflight conflict and verified completed-operation retry boundary in `proposal_artifact_v1`; do not describe this as hard-crash atomicity across graph and SQLite. Explicit API workspaces default to persistent JSON, while demo/memory fixtures must request their backend deliberately.

## SG-024 update consistency

Windows update replacement must preflight before any application binary write, stop only retained managed processes or an exact target-install executable path, and preserve stop errors. The updater can exit without Drop; do not rely on destructor cleanup. Do not touch author workspaces or indiscriminately stop image names.


## SG-025 novel editor workspace

Validate generated structure authored fields, including obvious short foreign-language headings, against frozen project language. Check edited structure content on first apply before graph writes; preserve verified completed retries. Proper-name metadata remains verbatim. No automatic paid retries, old-title rewrites or model-family assumptions.

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

## SG-029 long-form authoring boundaries

Follow longform_plan_v1 and generation_review_v1. Blueprint and chapter batches are versioned noncanon Proposals; only exact accepted human apply creates scoped world/style/outline nodes with events. Never treat planned character budgets as generated manuscript length. Report deterministic scale tests and live-model quality evidence separately.

Project StyleProfile defines the author-approved Agent voice across providers; context_pack_v1 now resolves scoped named canon entities, approved style and conservative Han budgets. Full drafting blocks on protected-context overflow. continuity is an explicit sixth task connection; read-only rule checks do not become paid calls. Semantic reports cite exact target text and scoped canon, record coverage/fingerprints and invalidate on changed inputs. A fresh scene report never certifies the whole novel. Reviewed long-form projects require a fresh passing semantic report before Agent-prose adoption; manual author saves remain available. Preserve canonical human review and all existing scope/language/provenance guards.

## SG-030 implementation boundary

Follow temporal_state_v1 for reviewed append_state operations and immutable Event assertions. Only explicit typed initial_state is a baseline. Resolve state at scene entry for writing; through-scene state is distinct. Never use acceptance order or lexical scene IDs as narrative chronology. Unknown, missing, cyclic or incomparable chronology must stay visible and block required context. Preserve source Draft full-text hash and field-slot fingerprint before review/commit; concurrent changes cannot overwrite prior truth. Unsupported backend operations fail before mutation. Historical corrections use explicit temporal_state_v1 review records; no path may silently delete earlier evidence.

## SG-031 planning-run responsibilities

Follow planning_run_v1: the autonomous book branch writes only Proposals and operational checkpoints until exact human bundle acceptance/application. Bound model calls and repairs; never replay uncertain paid work without explicit retry authorization. Preserve source versions/body hashes, frozen canonical/config fingerprints, worker ownership and audit receipts. Final book review covers the complete blueprint and scene summary/outcome/dependency/clue ledger, with separate per-batch checks; never claim it read unwritten prose. Stop/shutdown must not initiate another model call after the current checkpoint. Historical state corrections follow temporal_state_v1 and append evidence instead of deleting prior records.
