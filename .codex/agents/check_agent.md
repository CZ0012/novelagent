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
- Language boundaries: `ui_locale` is local display state only; project output is `zh-CN` or `en-US`; Source uses valid BCP 47 metadata; no implicit translation; provider-call count is zero for rejected language inputs.
- Version synchronization across `VERSION`, Python, Web, and Tauri files when versioning is touched.

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
