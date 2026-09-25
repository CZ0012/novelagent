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
