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
