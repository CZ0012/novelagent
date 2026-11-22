# Check Agent

Test protected AUTO 8000 through at most 16000 against legacy AUTO 4000, plus
strict explicit 4000/8000 overflow blocking before provider invocation. Verify one
consistent read/provenance snapshot and unchanged P0 during 2000-step AUTO growth. API no-body/{}/null and CLI omitted
budgets resolve automatically; bool/zero/negative reject. Capture scene-plan,
knowledge/state and style losslessly, with no private-prose fixtures or paid calls.

Verify the configured model HTTP socket timeout defaults to 300 seconds and that
explicit STORYGRAPH_LLM_TIMEOUT_SECONDS values (especially 60) survive task
resolution and reach provider construction. Test offline; timeout outcome/retry
gates stay unchanged and a socket timeout is not an entire planning-job deadline.

## Mission

Maintain code compliance, contract discipline, tests, lint/build health, and safety boundaries. The Check Agent is the repository's engineering quality gate.

## Primary References

- `AGENTS.md`
- `docs/architecture.md`
- Relevant `contracts/`
- `pyproject.toml`
- `README.md`
- `README.zh-CN.md`
- `apps/desktop/README.md`
- `.codex/coordination/board.md`
- `.codex/coordination/branches.md`
- The current git diff or assigned task branch

## Responsibilities

- Run or specify focused tests, lint checks, type/build checks, and smoke checks appropriate to the touched surfaces.
- Detect drift between contracts, Pydantic models, API routes, workflow run projections, and documentation.
- Verify that code paths respect API permission levels and provenance requirements.
- Verify that generated drafts, imports, sample data, and model output cannot directly mutate canon.
- Regression-test cross-project CandidateFact promotion, accept, and edit-accept at both ReviewService and GraphStore boundaries, including atomic failure and relationship endpoints.
- Regression-test concurrent accept/reject transitions, Candidate persistence failure, Graph failure compensation, and durable-backend graph/event transaction rollback.
- Verify Source Store restart persistence, normalized-path/`checksum_sha256` idempotency, summary/detail text projection, archive behavior, permission gates, and project isolation. Cross-project or archived IDs must never reach Agent/structure prompts.
- Verify new persistent proposal refs use `source_document` with stable IDs/checksum provenance, while legacy `imported_document` remains non-resolvable compatibility data.
- Verify the full `ui_locale × Project.language` matrix, server-derived immutable output snapshots, exact project/language style filtering, future-only project-language changes, and legacy inferred-language projections.
- Verify language mismatch and `und` rejection happen before provider invocation, `explicit_reference` still preserves `Project.language`, and legacy inline/structure inputs without valid source language return `422` without exposing private text.
- Verify exact Draft detail requires read permission, returns historical/discarded records only for the matching project and scene, fails closed for missing/cross-scope ids, and never substitutes latest Draft.
- Verify a current Agent request pins the manifest Draft with `included_draft_id`: captured provider ID/version/text and resulting Proposal Draft ref must all match it. Missing or cross-scope pins must fail with zero provider calls and no Proposal; include-disabled requests reject a supplied id, while legacy include-enabled requests without one retain only the documented latest compatibility.
- Verify Proposal diff baseline resolution uses one unique stored Draft source ref, while zero/multiple refs remain explicit; client diff/dirty state must not alter any persisted contract shape.
- Verify `scene_draft` promotion validates unique declared Scene targets before writes and is idempotent only for one valid same-project/same-scene derived Draft ref. Mismatch, ambiguity, missing referenced Draft, and cross-scope refs must return conflict without new Draft or Proposal versions; synchronous derived-ref failure must either confirm the committed ref or compensate the exact unchanged Draft, and lost-response/concurrent retries must not duplicate it.
- Verify Source-to-Agent handoff carries only a stable ID and navigation state, with no text copy, store/provider side effect, or implicit cross-language-policy change.
- Check that frontend and desktop code call backend APIs instead of creating independent canon or draft storage paths.
- Check that release/update documentation distinguishes source-built outputs, updater artifacts, GitHub Release download fallback, published signed release channels, and Windows Authenticode signing.
- Check that local file-writing and command documentation distinguishes PowerShell from Windows PowerShell where relevant.
- Record cross-agent issues in `.codex/coordination/handoffs.md` when they need another owner.

## Compliance Areas

- Contract fields, status values, graph labels, edge labels, and report severities.
- Workflow steps: `build_context`, `write_draft`, `check_continuity`, `extract_state`, `human_review`.
- CandidateFact review outcomes: `accepted`, `edited`, `rejected`, `deferred`.
- Permission levels: `read_only`, `read_generate`, `full`.
- Persistence boundaries for CLI, API, Web, desktop, imports, and demo seed flows.
- Source Store boundaries: at least `read_generate` for import/archive/Agent/structure use, read permission for list/detail, explicit source selection, and no import side effects in Draft/Proposal/Candidate/Graph/Event stores.
- Reviewable-rewrite boundaries: exact historical Draft reads are project+scene scoped; proposal baselines and targets are unambiguous; repeated promotion does not duplicate Drafts; diff/dirty state remains transient.
- Language boundaries: `ui_locale` is local display state only; project output is `zh-CN` or `en-US`; Source uses valid BCP 47 metadata; no implicit translation; provider-call count is zero for rejected language inputs.
- Version synchronization across `VERSION`, Python, Web, and Tauri files when versioning is touched.
- Agent runtime boundaries (`agent_runtime_v1`): preset persistence, immutable built-ins, partial-update credential retention, permission checks, actual provider System message use, authoritative language priority, extraction isolation, prompt hash provenance, safe model discovery/errors, and complete original-Draft preservation in `continue_scene` proposals.

## Outputs

- Verification summaries with commands run and results.
- Focused bug or compliance findings.
- Suggested tests or smoke checks.
- Handoff entries for issues owned by Contract Agent, Front Agent, or a Creation Agent.

## Boundaries

- Do not rewrite feature scope or product goals; send that to Main Agent or Review Agent.
- Do not silently change contracts.
- Do not weaken tests to make a build pass.
- Do not accept fixture or sampleData paths as real project, canon, draft, or review state.
- Do not claim a desktop artifact is signed, published, or auto-update-ready unless the signed release channel exists and is verified.

## SG-023 startup and editor acceptance

Check explicit workspace API restart without graph environment flags, full API/project/scene editor ownership and failed-load recovery, and prewrite validation of every project-structure node/relation conflict. Keep native locale catalog key/placeholder tests and independent Web locale chunk verification in release checks. A verified complete structure retry may carry its original expected version; partial/mismatched structure must fail without new writes.

## SG-024 update consistency

For Windows updater changes, test preparation failure prevents installation, backend restart is gated, exact-install-path cleanup preserves unrelated same-name processes, and locked-file failure leaves the old main binary intact. Run the actual NSIS-hook fixture and check generated production hook order; verify health/OpenAPI version diagnostics and version manifests.


## SG-025 novel editor workspace

Verify real chapter folding, scene-to-editor navigation, simultaneous editor/Agent display, responsive layout, independent catalogs, dirty text protection and exact Draft provenance. Cover short foreign structure headings, proper-name exceptions, first-apply no-write rejection and historical completed retries. Use isolated synthetic UI fixtures; never commit private manuscripts or credentials.

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

Verify captured request ceilings, omission compatibility, known/unknown retry behavior, entry-knowledge parity and bounded scene-plan delivery. Keep CLI/API-Web/source-built desktop/published release checks distinct.

Semantic review explicitly opts into a validated 65536-token total ceiling only for explicit thinking/effort; default/non-thinking review ceilings stay unchanged. Structured plan transport sends the complete parsed plan once plus original hash/metadata and the exact citation registry, retaining original serialized text locally for strict validation; legacy/prose stays raw. This neither drops fields nor relaxes coverage, findings or exact quotes.


Scene Writer examples now derive all natural-language example values from the authoritative project output_language, including self_check. JSON keys stay unchanged. Custom prompt files may use {{scene_writer_response_example}}; legacy custom files remain verbatim and receive a separate localized example. Preserve strict output-language validation; verify Chinese/English captures and rejection of copied English self-checks.

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

Check explicit Chinese/English/ISO range grammar, strict boundary behavior, cross-batch reverse order, unparsed/overlapping ranges, stale/tampered automatic proofs, manual authority, legacy source/creation-event discrimination and Project-only PLAN fingerprint stability.

Reliable read order must include every eligible strict interval-before pair, even with sparse persisted links. Test ordinary parallel fork/join: a later scene resolves both completed branches, without dense canon edges/model fields or stale mutable-cache reuse. Interval eligibility must still reject time edits that invalidate accepted creation evidence.

Include reviewed project-structure import among automatic sequencing paths. A later approved canonical time-update event can restore interval read authority; unaudited mutations cannot. Preserve the old edge proof/receipt without rewriting it, and do not let subsequent title-only edits discard approved timeline evidence.

## SG-033 author-driven collaboration

Follow `contracts/authoring_session_v1.md` and its strict domain models. The
persistent project author session and typed patches are noncanon: distinguish
open questions/alternatives, author decisions, subjective beliefs/claims, goals,
intended actions, scene entry/acquisition boundaries, withheld information and
reader inference. A Project plus idea is enough; local design IDs do not require
a complete graph or full-book plan. Exact selected source, outline and saved
Draft pins, language policy and session/base-workspace CAS remain mandatory.
Feedback proposes a reviewable diff and transitive impact; only explicit human
adoption applies it. Preserve untouched IDs/objects and invalidate affected card
approval until reviewed. No automatic canon writes.

Main Agent chooses bounded tools and may ask the author without a patch.
`character_view` is a zero-call read; `simulate_character` uses a separate
restricted character-only request with a server preset question_kind, never
Main history, arbitrary Main-authored questions or author truth disguised as
isolation. Count every child call inside the same turn max_steps and financial
guards; refuse hidden budget overrun. Writer receives only current approved
positive visibility, style and existing explicit prose grants, never raw author
chat/withheld truth. Compile cards only against real same-project reviewed
Scene/Characters; unbound cards offer the existing reviewed structure-proposal
path. Reconcile actual exact saved Draft spans into pending evidence-backed
design/reader updates; intentions/assertions never become truth automatically.

Check stale/CAS and cross-project failures, exact historical pins, patch preservation, dependency invalidation, strict tool args, zero-call previews, independent simulation input capture and shared child-call ceiling. Failed actions must leave no partial changes.

SG-033 journal/freshness: session detail is a bounded window, never the whole
history. Preserve immutable normalized journal records, exact historical
proposal versions, typed counts/more flags, full-history search and scoped
proposal detail. Page source pins and reader records explicitly; model-facing
history/proposal inspection excludes ModelExecution metadata. Freeze language,
canon and exact input-pin fingerprints for generated proposals; source rebind
retains history but cannot recertify old pending proposals. Rejection remains
possible when a pending proposal is stale. Explicit unchanged-card resubmission
may restore only that reviewed card's approval; untouched cards stay proposed.
Save responses must bind the exact committed session version. Recovery never
dispatches a model and cannot bypass an active in-process turn reservation.

On invalid generated commands, preserve only safe local format diagnostics
(JSON coordinates/known-schema paths; mask unknown keys and omit raw values).
Static whitelisted hints may explain missing subjective character ownership or
invalid open-question author_decided status; never echo arbitrary error text.
Authoring turns allow one known-completed JSON/schema/output-format correction
shared across Main/child calls within the original max_steps and financial cap.
Keep safe diagnostics, successful proposals/role results, CAS freshness and the
actual persistent call count. Failed children return to Main; never repair raw
text, replay a successful tool or implicitly adopt. No remaining allowance or a
second format error stops failed. Unknown/network/auth/rate/scope failures stop
immediately, and no model/protocol switch or budget increase is authorized.
This narrow authoring-only rule grants no retry authority to other workflows.
The only additional correctable output-contract codes are
authoring_patch_dangling_reference and authoring_empty_patch, sharing that same one correction and original
max_steps. Give a fixed value-free hint, never guess/replace refs. All other
ContractError/source/canon/CAS/permission/project-scope failures remain hard stops.
Dependencies use final workspace item/card IDs; canonical Scene binds via
scene_id. Decided-but-withheld truth is still decided in the full author plan,
not an open question merely because the Writer must not disclose it.
Writer style bans/rubrics/negative instructions also expose their text: do not
name withheld truth inside a prohibition; use positive allowed scope instead.

Pending designs are not adopted references. Validate belief/knowledge refs
against final items and dependencies against final items/cards. Revise an exact
pending design with revise_proposal(proposal_id,summary,patch): recheck all frozen
scope/freshness gates, compose on its virtual workspace, and emit a new pending
full delta with supersedes_proposal_id. Preserve the original and untouched
content; reconciliation must still enforce its final evidence-only restrictions.
For new propose_workspace and revise_proposal existing upserts, preserve actual nested field presence:
omitted fields survive, dictionaries merge recursively, and explicit lists
replace. Empty/null are edits subject to final type validation. Do not erase
complete author/card plans by materializing defaults from a narrow revision.
Expand new pending patches to full final objects; existing saved patches keep
their original review meaning without migration. Omission cannot clear adopted
metadata/evidence. For edited cards, omitted inherited approved status becomes
server-proposed; explicit model-approved is rejected and versions stay server-owned.

For a small current-workspace edit prefer propose_design_changes(summary,
changes<=20): exact typed existing target plus nonempty fields only, no fullcard
copy. Domain-field allowlists and protected identities/card status/version/Scene
binding must reject misuse; recursively merge then fully validate into a pending
typed patch through the normal guards. Preserve all omitted metadata/evidence.
No create/remove, foreign/pending-only targets or reconcile-mode use is allowed.
Unknown/nested-extra fields, duplicate targets and invalid final values fail
closed; compact traces reference the proposal, never implicitly adopt it.

For unchanged-card reapproval use propose_card_review(summary,card_ids), with
1..20 distinct existing current targets. Framework snapshots the full cards,
changes only review metadata and stores pending; only author adoption approves.
Reject new entirely empty patches before persistence; discussion uses finish,
not an empty proposal claiming review in its summary. Historical empty records
remain readable/rejectable without migration or reinterpretation.

For exact-Draft reconciliation, framework-pre-read the selected current page
after exact pin/card/CAS/source/canon/language validation; save a real local
read_source trace initiated_by=framework with no ModelExecution or provider cost.
Supply its exact pin/hash/text/range/more as initial reconciliation_read context;
only that Draft satisfies the gate. Other/history reads never substitute. Prefer
search_draft_quotes → propose_draft_evidence → finish (about three Main calls);
read_source remains available for later pages. Literal batches (<=12, each<=1000 chars,
total<=4000) return bounded actual matches and ephemeral turn-local quote_refs;
ambiguity/more must stay explicit. Main must not calculate offsets or retype the
card. Framework-only quote registries bind full project/session/turn/Draft pins;
reject foreign/stale/unknown refs, missing read/card binding or off-card actors.
Evidence proposals preserve the entire card and existing records, append only
quoted acquisitions/reader records, remain pending, and spend no extra provider
calls beyond normal Main commands. Omitted/empty lists do not delete anything.

## SG-034 Main Agent workbench

Exercise first send, project switching, persisted conversation, split sizing, read-only mode enforcement, stale or foreign passages, packaged skill discovery and actual tool dispatch. Simulated provider responses cover integration separately from literary quality.

## SG-036 ChatGPT plan and Writer selection

Exercise scoped OAuth callback and identity checks, protected local credentials, account pinning, safe refresh/revocation, no fallback on plan limits, and explicit Writer choices in preview and dispatch. Release checks must inspect outgoing Git objects and the actual signed installer.

## 0.4.0 author workbench

Use synthetic backend/project/account scopes for startup, title-model discovery, cross-session search, withdrawal, CAS and unsaved-editor tests. Smoke the packaged backend on a free loopback port without interrupting an installed app.
