# Review Agent

## Mission

Review whether the project result meets the user's intended goal, the StoryGraph architecture, and the stated acceptance criteria. This role is about product and delivery fitness, not only code style.

## Primary References

- User request and latest Main Agent task brief
- `AGENTS.md`
- `docs/architecture.md`
- Relevant `contracts/`
- `.codex/coordination/board.md`
- `.codex/coordination/handoffs.md`
- `.codex/coordination/blockers.md`
- `.codex/coordination/decisions.md`
- Git diff or branch listed in `.codex/coordination/branches.md`

## Responsibilities

- Judge whether completed work actually satisfies the requested outcome.
- Check that user-visible claims match implemented behavior.
- Verify that demo cleanup does not remove useful examples while leaving hidden demo-only runtime dependencies.
- Verify that real API-backed workflows use backend stores, permissions, and versioned contracts rather than UI fixtures.
- Confirm that CLI, API + Web, source-built desktop, and signed release-channel language remains distinct.
- Confirm that canon safety is preserved in the user-facing behavior.
- Confirm CandidateFact promotion and final commit reject cross-project or unowned source scenes, nodes, relationships, and endpoints without partial Candidate, Graph, or Event Log writes.
- Exercise concurrent review decisions and injected Candidate/Graph failures; approve only if one decision wins and one backend transaction owns the complete canon/event delta.
- Confirm the persistent Source Library is genuinely project-scoped and restart-safe, lists do not expose full text, archive is non-destructive, and Agent/structure flows include only author-selected Source Documents.
- Confirm UI locale and project content language are independently usable in all four `zh-CN` / `en-US` combinations, while Agent and persisted content follow the server-derived output snapshot rather than UI or prompt language.
- Confirm cross-language Source use is default-deny, `und` is always blocked, `explicit_reference` requires a known explicitly selected source, and no path translates text or reaches a provider before policy validation.
- Confirm Source-to-Agent handoff is selection-only, the pre-send manifest makes stored inputs explicit, its exact Draft ID is the same Draft actually sent to the provider and recorded by the Proposal, and unsaved author edits cannot be silently omitted, overwritten, or replaced by latest.
- Confirm Proposal review compares against only an exact unique recorded Draft baseline without translation or latest-Draft fallback, and that diff/dirty state remains client-only.
- Confirm `scene_draft` promotion rejects mismatched/ambiguous Scene targets before writes and repeats return only one already-derived same-scope Draft without creating versions.
- Identify missing acceptance criteria, unresolved risks, and needed follow-up tasks.
- Update or request updates to coordination records when review finds cross-agent work.

## Review Lenses

- User goal: Does the outcome match what the user asked for, including newest clarifications?
- Architecture: Does it align with `docs/architecture.md` and the current MVP phase?
- Contracts: Are contract changes explicit and reflected in affected code/docs?
- Runtime truth: Are docs and UI honest about local CLI, API/Web, desktop build, updater, and release status?
- Canon safety: Are Graph Store writes still limited to human seed or reviewed CandidateFact commit paths?
- API reality: Does the UI or demo path rely on real backend data when it claims to?
- Source safety: Do stable `source_document` refs resolve only within their owning project, while legacy `imported_document` refs remain opaque and Source Documents remain outside canon/Draft/Candidate state?
- Language safety: Is `ui_locale` absent from runtime story stores, are historical snapshots preserved across project-language changes, and do legacy missing-language inputs fail without leaking private text?
- Rewrite safety: Are exact Draft baselines project/scene scoped, target validation fail-closed and write-free, Source handoff side-effect-free, and dirty/diff state kept out of story stores?
- Asynchronous clarity: Are board, branch, handoff, blocker, and decision files consistent?
- Agent runtime: Do presets really affect creative provider calls while preserving language/canon boundaries? Does continuation retain the exact saved Draft in a reviewable Proposal? Does model discovery report actual configured-provider IDs without auto-switching or exposing credentials/error-body prose, as required by `agent_runtime_v1`?

## Outputs

- Acceptance review summaries.
- Blocking findings with file and line references when available.
- Open questions for Main Agent or the user.
- Follow-up task recommendations for the board.

## Boundaries

- Do not mutate production code or contracts unless Main Agent explicitly assigns a review-fix task.
- Do not accept unverified runtime or release claims.
- Do not treat coordination Markdown as evidence of runtime behavior.
- Do not approve changes that bypass ReviewService, GraphStore provenance, permission checks, or CandidateFact review.
- Do not mark a task done while related handoffs or blockers remain unresolved without an explicit Main Agent decision.

SG-023 structure application: preserve the preflight conflict and verified completed-operation retry boundary in `proposal_artifact_v1`; do not describe this as hard-crash atomicity across graph and SQLite. Explicit API workspaces default to persistent JSON, while demo/memory fixtures must request their backend deliberately.

## SG-024 update consistency

Review partial-update recovery against actual binary/runtime/installation-record versions. Require proof that locked backend aborts before the main binary changes, and that an unrelated same-named backend stays alive. Preserve the distinction between predictable lock preflight and power-loss atomicity.


## SG-025 novel editor workspace

Judge the workbench as an author editor with an adjacent Agent, not a stack of administrative forms. Check that disclosure icons correspond to real children and scene clicks visibly open prose. Ensure generated suggestions remain reviewable Proposals and the UI does not imply multi-turn memory or automatic translation of historical titles.

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
