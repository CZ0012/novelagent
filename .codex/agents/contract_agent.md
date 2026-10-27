# Contract Agent

context_pack_v1 resolves omitted/null protected targets through bounded AUTO
8000..16000 (2000-token steps with 256-token essential headroom), legacy 4000
otherwise; wire budget reports the selected concrete integer.
Explicit positive targets remain strict; bool/zero/negative reject. Optional
context API body and CLI defaults must preserve no-body compatibility and P0.

Runtime timeout boundary: StoryGraphSettings uses a 300-second default model
HTTP socket timeout; explicit STORYGRAPH_LLM_TIMEOUT_SECONDS (including 60)
remains authoritative. This adds no settings schema, retry/fallback or total-job
deadline and does not change unknown paid-call outcome/recovery semantics.

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

Keep config/provenance, outcome limits, pending-call semantics and optional scene-plan consumers synchronized. Update affected instructions/docs while preserving absent-field, historical hash and receipt compatibility.

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

## Writer Visibility v1

Follow `contracts/writer_visibility_v1.md`: local versioned disclosure policy is separate from Graph/canon and PLAN. Protected prose must use the positive approved Writer view and preflight before provider construction; missing/stale policy or lost sidecar blocks, never falls back. Preserve explicit legacy unisolated behavior. Reader Draft/version/hash/UTF-16 spans and expected inference do not automatically become disclosed facts or edit permission. Public names/claims/voice must be explicitly authorized, while scene critics keep full canonical authority plus the current disclosure constraint in freshness/adoption. Preview must show actual model messages, and policy/API/UI changes need source-binding, scope and no-canon-write regressions.

Protected editing uses per-request `prose_input_grants`: exact stripped instruction hash plus a same-project saved Draft/version/hash target, or UTF-16 selection with expected text. Selection discloses only the span; continuation/full revision disclose only the bounded target. ReaderPresented never grants editing. Preview and actual prose reuse the same messages; concrete prose buttons authorize these inputs without another confirmation. Do not silently truncate, add sources/search/history/presets, or permanently prohibit protected editing. Project cast templates project only scene actors unless an offstage public name is explicitly allowed and scope-validated. Preserve complete old message behavior for `legacy_unisolated`.

Keep existing canonical Scene `must_include` literal checks: protected policy must explicitly authorize those literals in its surface plan/claims or fail before provider construction. Never solve a visibility-policy gap by silently disclosing raw author context or deleting the output constraint. A selected scene summary is not a new literal requirement.

Strict prose provenance must name the visible policy/style origin and mark configured raw presets and author discussion history as not transmitted. Preserve the compact configured `agent_preset` snapshot for compatibility while `agent_preset_role`/`agent_preset_transmitted` state its actual transport role. Legacy/discussion preset transmission remains unchanged.


## Reliable world chronology

Narrative list positions, previous_scene_id and planning-only CAUSES are not world
precedence. Follow temporal_state_v1: automatic edges require deterministic
accepted interval proofs and exact source/target timeline hashes; overlap, touching
boundaries, unsupported text or stale source evidence stay unknown/incomparable.
Manual explicit NEXT_SCENE remains authoritative. Legacy automatic edges need
actual ID/source/creation-event binding, not prefix heuristics; reads never rewrite
canon. Preserve scene-grained entry/through semantics and all human-review gates.
Preserve prompt/schema formats and unapplied Project-only planning inputs and
fingerprints. Withdrawing proven-unsafe automatic facts from an applied-project
model view must change its actual PLAN evidence fingerprint and stale old reports.

Follow temporal_state_v1, graph_store_v1, longform_plan_v1, context_pack_v1 and composition recovery in proposal_artifact_v1. Document exact automatic proof metadata and immutable legacy evidence; no new public planning field or silent migration.

Reliable read order must include every eligible strict interval-before pair, even with sparse persisted links. Test ordinary parallel fork/join: a later scene resolves both completed branches, without dense canon edges/model fields or stale mutable-cache reuse. Interval eligibility must still reject time edits that invalidate accepted creation evidence.

Include reviewed project-structure import among automatic sequencing paths. A later approved canonical time-update event can restore interval read authority; unaudited mutations cannot. Preserve the old edge proof/receipt without rewriting it, and do not let subsequent title-only edits discard approved timeline evidence.
