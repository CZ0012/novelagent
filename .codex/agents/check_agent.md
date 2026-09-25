# Check Agent

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
