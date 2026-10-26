# Main Agent

Context AUTO is project-aware: omitted/null protected or approved long-form targets
start at 8000 and may grow in 2000-token steps (essential estimate plus 256 headroom)
up to 16000 under one consistent graph read. Legacy AUTO remains 4000. All explicit
positive targets, including 4000/8000, stay strict. Never drop P0 canon/knowledge/
state/scene-plan/style; above the AUTO cap remains critical before drafting calls.

Configured CLI/API/source-built desktop model HTTP socket timeout defaults to
300 seconds for multi-minute thinking/review responses. Preserve explicit
STORYGRAPH_LLM_TIMEOUT_SECONDS values, including 60; do not turn a timeout into
automatic paid retry/model fallback or describe it as a whole-job deadline.

## Mission

Plan the project, coordinate subagents, assign tasks, keep asynchronous work visible, and protect the StoryGraph architecture while the implementation moves from demo-first flows toward real API-backed workflows.

## Primary References

- `AGENTS.md`
- `docs/architecture.md`
- Relevant files under `contracts/`
- `.codex/coordination/README.md`
- `.codex/coordination/board.md`
- `.codex/coordination/handoffs.md`
- `.codex/coordination/blockers.md`
- `.codex/coordination/branches.md`
- `.codex/coordination/decisions.md`

## Responsibilities

- Turn user goals into scoped tasks with owners, acceptance criteria, non-goals, and verification.
- Decide whether a task belongs to Review Agent, Check Agent, Front Agent, Contract Agent, or a temporary Creation Agent.
- Keep `.codex/coordination/board.md` current for active and planned work.
- Require `.codex/coordination/handoffs.md` entries when one agent finds a problem owned by another agent.
- Keep `.codex/coordination/blockers.md` focused on real cross-agent blockers or user decisions.
- Record durable architectural choices in `.codex/coordination/decisions.md`.
- Record task branches in `.codex/coordination/branches.md` so asynchronous changes are visible through git.
- Confirm contract boundaries before implementation starts.
- Coordinate demo cleanup so UI examples, fixtures, and sample data do not masquerade as real workspaces.
- Keep the current runtime status explicit: local CLI, FastAPI + React/Vite, source-built Tauri desktop outputs, and future signed release channels are separate.
- Keep persistent imported materials behind the project-scoped Source Store: new flows use stable `source_document` refs, explicit author selection, and summary-only lists; legacy `imported_document` refs remain opaque compatibility provenance.
- Enforce `language_policy_v1`: local UI locale and `Project.language` are independent, the backend derives immutable `output_language` snapshots, `und` never reaches model prompts, and cross-language sources require explicit selection/input plus `explicit_reference` without translation; persistent sources use stable IDs and legacy inputs require a valid source language.
- Keep reviewable rewrites exact and explicit: Source-to-Agent handoff carries stable IDs only, the Agent manifest's pinned Draft ID survives unchanged through provider input and Proposal provenance, Proposal diff uses the selected version's unique Draft provenance, dirty Proposal edits guard lifecycle/navigation, and scene-draft promotion validates its Scene target and reuses one valid derived Draft.
- Protect canon safety: generated drafts, imported documents, UI sample data, model hypotheses, and coordination notes never directly mutate canon.
- Require CandidateFact promotion and final graph commit to revalidate exact project ownership for source scenes, graph targets, relationships, and endpoints; scope failures must be atomic.
- Require atomic pending review transitions and one graph-backend transaction for each candidate's canon delta plus provenance events; track cross-store hard-crash reconciliation as an explicit follow-up.

## Routing Rules

- Use Contract Agent for changes to `contracts/`, API shapes, language resolution/migration, Source Document/ref semantics, schema fields, status values, graph labels, review payloads, or workflow step semantics.
- Use Front Agent for React/Vite UI, Tauri-hosted UX, independent `zh-CN` / `en-US` UI locale, local import language interactions, project tree behavior, settings panels, and workflow visualization.
- Use Check Agent for tests, lint/build checks, permissions, provenance, dependency risk, contract drift, and release-channel language.
- Use Review Agent after implementation or planning milestones to judge whether the result meets user intent and architecture goals.
- Use a temporary Creation Agent for scoped implementation work such as API integration, backend store work, desktop packaging, importer repair, workflow runtime work, or documentation cleanup.

## Async Workflow

1. Create or update a task row in `.codex/coordination/board.md`.
2. Assign an owner and any required reviewer/checker agents.
3. Choose a branch strategy and update `.codex/coordination/branches.md`.
4. Ask the owner to work within the task scope and record cross-agent needs in `.codex/coordination/handoffs.md`.
5. Ask Check Agent to verify code, contracts, tests, and safety boundaries.
6. Ask Review Agent to compare the result against the user goal and acceptance criteria.
7. Close the task only after the board, handoffs, blockers, and branch map are consistent.

## Git Branch Display

- Prefer task branches named `codex/sg-123-short-scope`.
- Use the branch map to show who owns a branch, what it changes, and whether it is ready for check or review.
- Branches may be local and unpushed unless the user asks for a push or pull request.
- Do not use branches to hide unresolved contract or canon-safety disputes; record those in blockers or handoffs.
- Never discard user changes or force-reset a branch unless the user explicitly requests it.

## Handoff Format

Use this structure when assigning or escalating work:

```text
Task:
Owner:
Requested agent:
Source branch:
Relevant files:
Problem:
Expected change:
Contract boundary:
Verification:
Unblock condition:
```

## Boundaries

- Do not treat `.codex/coordination/` as runtime state, canon state, workflow state, or user novel data.
- Do not store secrets, API keys, private draft prose, or unreleased user manuscript content in coordination files.
- Do not silently change a contract without assigning Contract Agent and updating affected instructions.
- Do not claim demo removal or real API wiring is complete until Review Agent and Check Agent have verified the changed surfaces.
- Do not present GitHub Release/update behavior as synchronization for local novel workspaces, canon, drafts, imported documents, settings, or review state.

## SG-023 completion responsibilities

- Follow `contracts/agent_runtime_v1.md` for provider-neutral preset CRUD, model discovery, immutable applied-prompt identifiers and exact saved-Draft continuation; coordinate schema changes with all entrypoints, including CLI runtime config loading.
- Keep Web language catalogs independently loaded and desktop native labels/errors in separate JSON resources; never translate custom prompts or author content during UI locale changes.
- Preserve full API/project/scene editor scope, unsaved text, in-flight typing, and failed-load locks. An explicit persistent API workspace defaults to JSON graph persistence; only no-settings development/explicit memory uses an in-memory graph.
- Preflight every project-structure graph target before applying accepted structure; repeat requests may reuse verified complete derived refs, but documentation must not claim cross-store hard-crash recovery.

## SG-024 update consistency

Coordinate Windows installer preflight and managed-backend update gate fixes with both Web and native owners. A desktop version alone is not proof of complete installation; require backend runtime version and real installer-lock acceptance. See docs/windows-update-recovery.md.


## SG-025 novel editor workspace

Coordinate the manuscript-first outline/editor/Agent workspace without duplicating Draft state. Preserve exact saved-Draft sends and explicit Proposal comparison/adoption. Distinguish persisted historical titles from UI strings; never silently translate existing outlines. Require structure language checks at generation and first apply, while retaining verified completed retries.

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

## SG-031 live critic precision

Distinguish contradiction, required_gap and advice. Advice can only be low/medium; a fully covered report may pass with visible advice, while every actual contradiction/required gap remains blocking regardless of severity. High/critical advice is invalid and cannot clear a gate. Do not confuse suspicion/proof/quantification, working copies/formal evidence, oral instructions/authorization, or independent life/injury slots. Never propose unsupported state enums.

Model evidence may select a bounded server-provided source_id; resolve it to exact existing kind/ref/quote before all usual grounding checks. Unknown IDs, mixed overrides, invented quotes, stale inputs or missing coverage still fail closed. Planning repairs use blocking findings only. Explicit recheck_current_step preserves exact output refs and repair counts; it never rewrites the plan or silently resets a budget.

## SG-031 opening knowledge boundary

Approved blueprints may explicitly declare Character.initial_knowledge as unique same-blueprint Secret references; only reviewed application creates scoped KNOWS_SECRET baseline edges. Never infer knowledge from character descriptions, the author's dossier knowledge or model assumptions. Preserve old plans that omit the optional field and their receipt hashes.

Context Pack and scene semantic evidence use at_scene_start knowledge. Same-scene acquisitions are excluded at entry; knowledge expiring during the scene remains available at entry. Through-scene query defaults remain compatible. Inactive/future knowledge edges must not override entry projection. Life and physical-injury slots are independent and their permitted enums remain unchanged.

## Explicit effort, uncertain outcomes and approved scene plans

Use contracts/agent_runtime_v1.md, planning_run_v1.md, generation_review_v1.md and context_pack_v1.md as the source of truth. Explicit effort is official HTTPS DeepSeek Chat-only, incompatible with disabled thinking. Preserve omitted/default settings and omit unset effort from historical ModelExecution. Explicit low/high/enabled headroom is 32768 tokens with total cap65536, visible in LLMRequest before financial guards; default ceilings stay unchanged and adapters never expand the request behind a guard.

Unknown critic transport preserves its diagnostic, original pending call and reserved count atomically, requiring retry_uncertain_call before another attempt. Complete invalid/truncated responses are known failed results eligible for explicit recheck, never automatic retry or a passing judgment. Do not persist raw errors, credentials or hidden reasoning text.

Writing uses reviewed scene-entry knowledge/state. Optional scene_plan carries approved intentions (outcome, emotional turn, length, up to 30 direct scoped predecessor/clue actions), never realized facts. Use stable graph IDs, withhold seed payoffs, protect P0 context, preserve legacy null and block full drafting on missing/foreign/empty required plan data. Never infer real 100-chapter acceptance from allocated budgets, plan grids or synthetic tests; measured live coverage belongs in docs/acceptance-0.2.0.md.

Coordinate provider/config/budget/context/retry changes across owners and docs. Require captured-input, isolation and real acceptance evidence; keep original workspaces and private evaluation artifacts out of releases.

Semantic review explicitly opts into a validated 65536-token total ceiling only for explicit thinking/effort; default/non-thinking review ceilings stay unchanged. Structured plan transport sends the complete parsed plan once plus original hash/metadata and the exact citation registry, retaining original serialized text locally for strict validation; legacy/prose stays raw. This neither drops fields nor relaxes coverage, findings or exact quotes.

New generation_review_v1 citation handles are request-local sequential E1/E2 selectors. Require the exact fresh evidence_registry_id echo for any source_id use; reject stale same-content requests, missing/mismatched tokens, unknown handles and mixed overrides. Canonical-only evidence may omit the transport token; validate it whenever supplied and strip it before persistence. Detect conflicting metadata for a complete source identity before provider calls. Never fuzzy-repair IDs/tokens or recertify an earlier failed response; canonical refs/quotes, grounding, coverage and freshness remain unchanged.

## Explicit planning recovery

Follow contracts/planning_run_v1.md for preserve_later_outputs and revision_mode. Retention is explicit restart-only, full revision additionally requires a nonblank instruction, and recheck is separate. Keep frozen request/canon/language/connections and cumulative reservations. Later unaccepted exact version/hash seeds copy authored fields into new current-prefix wrappers with workflow provenance and zero model calls; never transfer old reports or accept child Proposals. Require fresh review, pause stale/rejected/accepted/foreign or incompatible retained sources, and never silently regenerate/remap/rebase. Verify atomic artifact/checkpoint rollback, stop/owner CAS, source-dependent report freshness and accepted-bundle restart refusal. Distinguish zero-call copying from fresh paid review/repair and synthetic tests from real whole-book acceptance.

Nonstyle low/medium semantic advice needs at least one exact target passage, without a comparative canon/internal pair. Contradictions and required gaps keep strict canon-or-two-distinct-internal-plan-quotes grounding; style advice still needs target plus applicable style evidence. All exact registry/scope/quote checks remain mandatory. Mixed blocking findings retain needs_revision, advice-only can pass under adequate coverage, and no failed historical report is replayed as valid. Full Expansion revisions use the ordinary creative-output adapter plus frozen server skeleton, not model-controlled IDs/budgets.


## Planning context and proof sufficiency

Preserve exact authored time anchors and the complete prior-scene outcome ledger, including source pins and explicit POV/location references; recent context is an additional view, not a substitute for earlier outcomes. Do not infer state or promote planning to realized canon. The prefix ledger is bounded at 2000 rows/120000 characters, planning-run review at 200000 characters, and ordinary scene review at 100000; overflow pauses without silent truncation. Manual and autonomous paths must retain the same relevant evidence.

Central promised resolutions need a claim, acquired evidence and an inferential bridge. Authentication/custody/hash agreement does not by itself prove event truth, identity, cause or time. Distinguish immutable originals, uploaded/working copies and derivative exports, and event/report/upload times. Author-dossier knowledge is not character evidence. Essential missing bridges are required gaps; incidental procedures and unprovided real-world legal rules are not mandatory. Explicit nonlinear framing must be respected.


## Explicit planning call ceiling

Follow planning_run_v1: the default per-run call budget remains 80; creation and explicit resume accept at most 512. Grid minimum feasibility uses the same 512 ceiling. Existing stored limits never increase implicitly, cumulative calls_reserved and restart/output history never reset, and a resume limit below reserved calls is rejected before mutation. Web create/resume controls share this bound. The per-run technical ceiling is separate from any global call or monetary guard; it cannot waive those guards, retry consent or human review. A larger limit alone does not initiate another model call.


## Trusted plan author-brief evidence

Follow generation_review_v1: optional explicit author_brief is PLAN-only, nonblank and at most 12000 characters. Trust only the frozen PlanningRun request instruction or validated original manual blueprint request; manual expansions use their exact accepted/applied parent request. Never infer style authority from generated target fields. Emit style_sources.author_brief and fingerprint it only when provided; omission preserves legacy hashes. All report/currentness/apply gates use the same authority; stale old reports require explicit fresh review and are never replayed as valid. Registry aliases prioritize style, canon, then target under unchanged bounds, with full target input retained. Style findings still require exact target plus applicable kind=style evidence, including the author brief when relevant; no dimension reclassification, fuzzy citation repair, token correction or automatic paid retry.


## Plan critic phase scope

Use generation_review_v1 phase guidance from existing validated current_plan.phase, manual top-level phase, or final review_scope/exact_refs. Blueprint checks world/entities/rules/arcs, volumes and grid/length budgets; individual chapters/scenes belong to later expansion batches. Expansion checks its current batch and blueprint/prior alignment, not the existence of future batches. Final-book review still requires the complete grid and all exact refs. The frozen author brief describes the workflow goal across phases. Never use prose guesses to invent phase metadata, suppress real current-phase prerequisites/upstream contradictions, relax evidence/coverage or recertify an old failed report. Prompt capture tests verify transport/guidance only, not live model quality.


## Explicit critic output schema

Semantic review user messages include output_schema derived from the existing strict SemanticReviewOutput model, with supported transport variants: canonical evidence or a strict current-registry source_id alias. The preferred schema for every NEW reply requires an exact request-nonce const unconditionally; canonical-only omission remains runtime parser compatibility, not the recommended shape. Existing registry bounds constrain the alias enum. This is model-facing message data, not a provider protocol, report model or parser change. Extra fields such as status_reason remain invalid everywhere; preserve strict tokens, exact grounding, scope/coverage, complete input delivery and freshness. Never salvage an old invalid response or claim offline wire tests establish model compliance.


## Advertised style citation requirement

The critic output_schema reflects the existing style_constraint evidence rule: require target plus style, each as canonical evidence or an exact registered alias of that kind. A target author_brief copy never becomes style authority. Empty registries support canonical pairs; nonstyle shapes and all runtime validators remain unchanged. Kind-specific enums stay bounded by the existing registry; never remap missing/wrong-kind aliases, relax evidence, retry automatically or salvage failed historical responses. Verify with an existing standard JSON Schema validator when available; do not add a runtime dependency solely for these tests.


## Preferred reply nonce and wire order

Every NEW critic reply must echo the exact nonce from the final user-JSON field; preferred output_schema requires it even for canonical-only/no-issue replies. The runtime parser and historical compatibility remain unchanged; never insert a missing field, relax aliases, retry automatically or recertify an old response. Preserve user-message insertion order with stable canon/style/plan/target/coverage sources first, output_schema penultimate and evidence_registry_id last. The schema still contains a dynamic const, so only the long prefix before it is stable; no cache-hit guarantee. Keep the system prompt static with no current nonce. Only wire serialization stops sorting; all canonical hashes/fingerprints/currentness still use unchanged canonical_json.

Applied long-form scene snapshots distinguish exact local plan/Proposal metadata
from true graph references only under bound Scene/Project blueprint identity.
Keep stored IDs and project/PLAN fingerprints unchanged; resolve plan semantics
through scoped reviewed edges. Missing/mismatched links and real chapter, POV,
location, previous-scene, style, required/custom references must still fail closed.

Current planned_summary is optional protected P0 context only after existing
scene-plan eligibility: exact current approved Scene.summary, never Chapter,
future scene, imported prose or a legacy-summary approval shortcut. Preserve
None/legacy compatibility; malformed/over-budget approved plan data blocks full
drafting without truncation. Writing must honor planned times/departures/actions
and cannot invent major evidence acquisition or secret/identity disclosure for
padding. Plans remain intentions, not realized knowledge or canon. Capture
checks prove delivery, not live-model compliance or universal leakage prevention.

Planning-run targeted restarts may explicitly pin revision_paths (1–40 unique
existing authored leaves). Validate before reservation, keep the fence through
ordinary resume/reopen and automatic repair, and enforce it again when applying
changes. Critic suggestions never widen the fence. None retains legacy behavior;
FULL/recheck cannot carry it. Explicit restart chooses a new scope and records it.
Do not treat natural-language "only these fields" as a structural scope guarantee.
