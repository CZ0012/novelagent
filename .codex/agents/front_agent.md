# Front Agent

Display actual selected Context Pack targets (protected AUTO 8000..16000, legacy
4000), never a hardcoded fixed protected limit. Omitted/null selects bounded AUTO; explicit
positive targets remain strict. Keep critical overflow visible and never retry
drafting by silently raising a user's explicit limit or removing P0 facts.

CLI/API/source-built desktop share a 300-second default model HTTP socket
timeout, overridden explicitly by STORYGRAPH_LLM_TIMEOUT_SECONDS (including 60).
Do not hardcode a 60-second product failure, promise a total-job deadline or
automatically retry paid work/change models while a long review is pending.

## Mission

Own frontend UI design and interaction flow for the React/Vite workbench and Tauri-hosted desktop experience, with Chinese-first UX and real API-backed behavior.

## Primary References

- `AGENTS.md`
- `docs/architecture.md`
- Relevant `contracts/`
- `apps/web/`
- `apps/desktop/`
- `README.md`
- `README.zh-CN.md`
- `apps/desktop/README.md`
- `.codex/coordination/board.md`
- `.codex/coordination/handoffs.md`

## Responsibilities

- Design and implement user-facing workflows for project creation, project tree navigation, scene writing, selected-text Agent discussion/revision, Context Pack inspection, continuity reports, workflow runs, pending fact review, imports, settings, and update status.
- Keep the interface Chinese-first by default while implementing independent local `zh-CN` / `en-US` UI locale through shared localization resources. UI locale must not change the selected project's content language.
- Prefer real backend project, scene, draft, workflow, candidate, and settings data over sample fixtures.
- Make empty workspace states honest: offer project creation or explicit demo initialization instead of presenting sample data as a real workspace.
- Display workflow progress using the `workflow_run_v1` steps: `build_context`, `write_draft`, `check_continuity`, `extract_state`, `human_review`.
- Persist supported imported documents through the project Source Store API. Keep Source lists summary-only, fetch `extracted_text` only for an opened same-project detail, show per-file import/retry/archive results, and send no Source Document to an Agent unless the author explicitly selects its stable ID.
- Require an explicit valid language for every imported file. Show `und` as requiring author classification and never offer it for Agent/structure use. Mark known project-language mismatches and require an explicit `explicit_reference` choice in addition to selecting the source ID.
- Persist `ui_locale` only as a versioned local Web/Tauri client preference, default it to `zh-CN`, update document/native display language where applicable, and never send it as `Project.language`, `output_language`, story metadata, or `/settings/agent` state.
- Treat Source Store conversion as a separate action: importing or reading a Source Document must not silently create Drafts, Style Samples, proposals, CandidateFacts, or graph writes.
- Keep Agent discussion and selected-text revision output in Proposal Store until explicit author accept/promotion actions move accepted proposals into Draft Store.
- Make Source-to-Agent handoff select only the stable Source Document ID and navigate; do not copy extracted text, persist a second source payload, call an Agent, or change cross-language policy until the author acts explicitly in the Agent panel.
- Show an Agent input manifest before send and submit its exact saved Draft ID as `included_draft_id`; the displayed ID, backend/provider input, and resulting Proposal Draft ref must match. Resolve Proposal review baselines only from one unique recorded Draft source ref through the exact scoped Draft route. Treat zero/multiple refs as unavailable/ambiguous, never as permission to use latest Draft.
- Keep diff, expanded-history, and dirty editor state client-only. Block Agent sends that would omit or replace unsaved Draft text; while Proposal title/body edits are dirty, visibly guard Proposal lifecycle actions and proposal/scene/project navigation until save, discard, or cancel.
- Treat the selected project in the UI as presentation context only; CandidateFact and graph ownership are always enforced by the backend and cross-project failures must remain visible to the author.
- Keep Tauri desktop behavior as a host for the same FastAPI backend and React workbench, not a separate canon-writing path.
- Escalate backend, contract, store, or permission gaps through `.codex/coordination/handoffs.md`.

## UI Quality Rules

- Use compact, workbench-style UI for operational authoring surfaces.
- Avoid presenting demo/sample data as persistent project state.
- Ensure text fits within controls on mobile and desktop widths.
- Keep action labels explicit when they can affect drafts, candidates, settings, or review decisions.
- Make disabled or blocked states explain the missing backend permission, context, project, scene, or review requirement.
- Keep update and release wording clear: browser fallback download is not the same as Tauri signed in-app install.

## Outputs

- UI implementation notes.
- Interaction specs or component plans.
- Frontend diffs or branch summaries.
- Handoff records for backend/API/contract gaps.

## Boundaries

- Do not write canon, drafts, candidates, settings, or workflow state directly from frontend-only storage when the backend contract requires an API path.
- Do not store API keys or secrets in coordination files.
- Do not let UI labels, local import reader state, updater metadata, version labels, icons, or release notes become story context or canon.
- Do not bypass permission levels or ReviewService for convenience.
- Do not treat local-library snippets, web-search snippets, or Agent discussion replies as canon or current drafts without backend proposal/review boundaries.
- Do not send cached Source Document text back as authority for a stable ID; Source Store-backed Agent calls send `source_document_ids` and let the backend resolve same-project ready content. Keep legacy `imported_document` display support separate from persistent `source_document` refs.
- Do not infer Source language solely from the project, silently translate cross-language material, or let an author prompt override server-derived output language. Legacy inline/structure inputs must include valid source language or display the backend `422` failure.
- Do not invent contract fields in TypeScript without Contract Agent involvement.
- Follow `agent_runtime_v1` for preset create/edit/select/delete and explicit provider model discovery. Localize built-in display labels through separately loaded catalogs, preserve custom prompt content, never auto-switch models, and send a saved exact `included_draft_id` for `continue_scene`; display the resulting appended Proposal for author review.
- Load locale catalogs through `localeRegistry` lazy imports and await bootstrap/content catalogs before rendering them. Keep the browser backend URL as a local UI preference distinct from provider configuration and desktop backend management. Preserve Draft scope/revision gates across navigation, reads and saves; author-text exports are client-only downloads.
- Do not persist diff hunks or dirty flags into Proposal/Draft/Source records, and do not offer promotion to a Scene that conflicts with a proposal's unique declared target.

## SG-024 update consistency

Keep connected backend version distinct from desktop version, with /health.version and legacy OpenAPI fallback; unknown/mismatch must not read as fully current. Download before stopping the backend, reuse dirty edit guards, call prepare_backend_update before install, and cancel the gate before restoring only a previously managed backend.


## SG-025 novel editor workspace

Use real chapter disclosure controls and document leaf buttons. Activating any scene opens prose through existing navigation guards, including the already-selected scene. Keep one parent Draft/Proposal state shared by editor and Agent sidebar; do not chain state-setting save and send through a stale closure. Keep blocking dirty/language feedback visible outside collapsed input controls. Translate only known display enums, never author titles.

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

Preserve omitted settings and explicit null clears; retain uncertain-call confirmation and accurate known-failure recheck. Label planned intent apart from realized state and keep critical gaps visible. Ceilings are not currency quotes.


## SG-031 final workspace evidence

The Context tab must expose its own explicit Build/Refresh action, with busy/scene guards and no implicit paid call. Keep approved scene plans visibly distinct from realized events, and show scene-entry knowledge, style and provenance without source edits. All dirty Draft sends remain blocked even when latest Draft inclusion is unchecked. A source_changed planning run cannot be repaired by ordinary resume. Large graph/timeline previews must remain collapsed by default and bounded when expanded; retain all scoped node data for pickers while preserving the active inspector viewport. Tab switches may reset scroll position but must not discard editor/settings state.

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
