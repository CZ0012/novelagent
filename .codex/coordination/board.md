# Coordination Board

Status values: `planned`, `active`, `blocked`, `ready-for-check`, `ready-for-review`, `done`.

| ID | Status | Owner | Branch | Goal | Required agents | Next action |
| --- | --- | --- | --- | --- | --- | --- |
| SG-001 | done | Main Agent | `codex/desktop-workbench` | Replace old feature-module subagent docs with the new project-governance agent roster and local Markdown coordination workflow. | Contract Agent, Check Agent, Review Agent | Keep this as the baseline for future agent work. |
| SG-002 | ready-for-review | Main Agent | `codex/sg-002-real-api-demo-cleanup` | Coordinate demo cleanup so public flows demonstrate real API-backed local workflows instead of hidden in-memory/sampleData paths. | Contract Agent, Front Agent, Check Agent, Review Agent, specialized Creation Agents | Review final SG-002 state and decide whether any optional desktop build smoke is still needed. |
| SG-002A | ready-for-review | Contract Agent | `codex/sg-002-contract-api-boundary` | Confirm the real API demo flow reuses existing contracts and routes without private frontend fields. | Check Agent, Review Agent | Existing v1 contracts cover the flow; no contract shape change needed. |
| SG-002B | ready-for-review | Front Agent | `codex/sg-002-front-real-api-workbench` | Remove or isolate UI demo/sampleData dependencies while keeping explicit demo initialization honest. | Contract Agent, Check Agent | `apps/web/src/sampleData.ts` removed; Web build passes and workspace surfaces use backend APIs. |
| SG-002C | ready-for-review | Backend/API Creation Agent | `codex/sg-002-backend-real-flow` | Keep the persistent JSON workspace path able to create projects, scenes, drafts, workflow runs, candidates, and reviews. | Contract Agent, Check Agent | Local persistent API smoke passed with DOCX import, workflow, CandidateFact, and review boundaries. |
| SG-002D | ready-for-review | Desktop Creation Agent | `codex/sg-002-desktop-api-host` | Confirm Tauri hosts the same FastAPI + React workbench and does not bypass ReviewService. | Front Agent, Check Agent | Desktop-hosted persistent backend path was used for smoke; Tauri shell code was not changed in this task. |
| SG-002E | ready-for-review | Docs Creation Agent | `codex/sg-002-docs-runtime-truth` | Clean runtime docs so CLI, API + Web, source-built desktop, and signed updater channel are distinct. | Check Agent, Review Agent | README, README.zh-CN, architecture, and desktop README now present persistent API as the real path and demo as explicit/dev-only. |
| SG-002F | ready-for-review | Check Agent | `codex/sg-002-check-real-api-demo` | Run focused tests, lint/build checks, contract drift checks, permissions, canon safety, and release wording checks. | Review Agent | `pytest`, `ruff`, Web build, KouriChat model probe, and private real LLM + local DOCX smoke completed. |
| SG-002G | planned | Review Agent | `codex/sg-002-review-acceptance` | Decide whether the result actually cancels demo-first behavior and demonstrates real API-backed flow. | Main Agent, Check Agent | Review after SG-002A through SG-002F are ready-for-review. |
| SG-002H | ready-for-review | Test Creation Agent | `codex/sg-002-real-agent-docx-test` | Use the user's existing local LLM config and private local DOCX input for a real Agent smoke test. | Check Agent, Review Agent | `deepseek-v4-flash` was busy; KouriChat `gpt-4o-mini` completed the real LLM + local DOCX smoke. |
| SG-003 | done | Main Agent | `codex/sg-003-proposal-workspace` | Add a reviewable Proposal Workspace where Agent/author can iterate non-canon artifacts before promotion to drafts, CandidateFacts, or canon review. | Contract Agent, Front Agent, Check Agent, Review Agent, specialized Creation Agents | Closed after current-state audit: contract/API/UI/workflow/docs implemented, final checks pass, no open SG-003 blockers or handoffs. |
| SG-003A | done | Contract Agent | `codex/sg-003-proposal-contract` | Define `proposal_artifact_v1` and API/store boundaries without weakening canon safety. | Check Agent, Review Agent | `contracts/proposal_artifact_v1.md` added with user-requested artifact/status values, provenance, versioning, review decision, and canon-safety invariants. |
| SG-003B | done | Backend/API Creation Agent | `codex/sg-003-proposal-store-api` | Implement Proposal Store and FastAPI routes for create/list/get/update/revise/review proposal artifacts with version history. | Contract Agent, Check Agent | Proposal Store/API implemented with focused proposal tests, full `pytest`, `ruff`, and stale-write coverage passing. |
| SG-003C | done | Workflow Creation Agent | `codex/sg-003-workflow-proposals` | Adjust scene generation and state extraction flows so Agent outputs can land in Proposal Store before promotion. | Contract Agent, Check Agent | `output_target=proposal_workspace`, draft/candidate promotion APIs, and canon-safety tests are in place; default workflow remains compatible. |
| SG-003D | done | Front Agent | `codex/sg-003-front-proposal-inbox` | Add Chinese-first `协作草稿箱` UI for listing, editing, revising, reviewing, and promoting proposals. | Contract Agent, Backend/API Creation Agent, Check Agent | Web types, API calls, workbench panel, import-to-proposal, workflow-to-proposal, and promotion buttons are wired to real backend APIs; Web build passes. |
| SG-003E | done | Docs Creation Agent | `codex/sg-003-docs-proposal-workspace` | Document Proposal Workspace as the non-canon collaboration layer between Agent outputs and confirmed drafts/canon. | Check Agent, Review Agent | README, README.zh-CN, architecture, and desktop README explain Proposal Store boundaries and promotion paths. |
| SG-003F | done | Check Agent | `codex/sg-003-check-proposal-workspace` | Verify tests, lint/build, permission gates, canon safety, contract drift, and documentation language. | Review Agent | Stale accept/reject, CandidateFact evidence drift, and reader text feedback fixed; current rerun: `pytest` 108 passed / 1 skipped, `ruff`, Web build, and `git diff --check` pass. |
| SG-003G | done | Review Agent | `codex/sg-003-review-acceptance` | Decide whether Proposal Workspace actually supports iterative Agent/author collaboration before draft/candidate/canon promotion. | Main Agent, Check Agent | Final audit accepts SG-003: proposal artifacts are non-canon, versioned, API-backed, UI-visible, and promoted only through explicit backend gates. |
| SG-004 | done | Main Agent | `codex/sg-004-release-0.1.2` | Finish the Proposal Workspace project state as a 0.1.2 desktop release and publish the software/update channel to GitHub. | Check Agent, Review Agent, Release Creation Agent | Closed for release commit: version sources, docs, tests, lint, Web build, installer build, release assets, and GitHub publication gates are defined for v0.1.2. |
| SG-004A | done | Release Creation Agent | `codex/sg-004-version-bump` | Synchronize source versions and desktop docs for 0.1.2. | Check Agent | `VERSION`, Python package, Web package/app version, desktop package, Cargo package, Tauri config, API metadata, lockfiles, and docs now point to 0.1.2. |
| SG-004B | done | Check Agent | `codex/sg-004-release-checks` | Verify Python tests, lint, Web build, desktop installer build, updater signature assets, and release hygiene. | Review Agent | `pytest`, `ruff`, Web build, version consistency, full `npm --prefix apps/desktop run build:installer`, and local 0.1.2 release asset checks passed. |
| SG-004C | done | Release Creation Agent | `codex/sg-004-github-release` | Commit, tag, push, and create GitHub Release `v0.1.2` with installer, `.sig`, and `latest.json`. | Main Agent, Review Agent | Release commit includes the files required for tag `v0.1.2`; GitHub upload verification is the external acceptance gate. |
| SG-004D | done | Review Agent | `codex/sg-004-release-acceptance` | Confirm GitHub latest release and updater metadata genuinely point to v0.1.2 assets, not local-only outputs. | Main Agent, Check Agent | Final release acceptance requires post-upload `gh release view`, `latest.json`, and asset URL checks. |
| SG-005 | done | Main Agent | `codex/sg-005-import-structure-draft` | Let authors import an existing novel into an empty project, have the Agent draft chapter/scene structure, and require author confirmation before creating official project tree nodes. | Contract Agent, Front Agent, Backend/API Creation Agent, Check Agent, Review Agent | Closed after implementation: `project_structure_draft` contract/API/UI/docs are in place; Python tests, ruff, Web build, browser smoke, and diff checks pass. |
| SG-006 | done | Main Agent | `codex/sg-005-import-structure-draft` | Make applying an accepted `project_structure_draft` repeat-safe so refresh/retry does not duplicate Chapter/Scene canon writes. | Contract Agent, Front Agent, Backend/API Creation Agent, Check Agent | Closed after implementation: API apply is idempotent for same-proposal retries, UI notice distinguishes reuse, contract note is updated, and verification passes. |
| SG-007 | done | Main Agent | `codex/sg-005-import-structure-draft` | Let authors edit existing Scene metadata after imported structure application so missing POV/location/goal/conflict can be resolved before Context Pack writing. | Contract Agent, Front Agent, Backend/API Creation Agent, Check Agent | Closed after implementation: scene metadata PATCH route, sidebar edit controls, docs, and focused/full verification are complete. |
| SG-008 | done | Main Agent | `codex/sg-005-import-structure-draft` | Expose project-scoped Character/Location option lists so authors can resolve imported scene POV/location hints into stable IDs without guessing. | Contract Agent, Front Agent, Backend/API Creation Agent, Check Agent | Closed after implementation: read-only list APIs, sidebar POV/location options, docs, and focused/full verification are complete. |
| SG-009 | done | Main Agent | `codex/sg-005-import-structure-draft` | Let authors edit existing Chapter metadata after imported structure application so generated chapter titles/order/summaries can be corrected without rebuilding the project tree. | Contract Agent, Front Agent, Backend/API Creation Agent, Check Agent | Closed after implementation: chapter metadata PATCH route, sidebar load/save controls, docs, and focused/full verification are complete. |
| SG-010 | done | Main Agent | `codex/sg-005-import-structure-draft` | Complete the Web Chapter metadata editor so volume order, purpose, and status can be edited through the same explicit author path as the backend route. | Front Agent, Check Agent | Closed after implementation: Web Chapter form covers backend fields and full verification passes. |
| SG-011 | done | Main Agent | `codex/sg-005-import-structure-draft` | Complete the Web Scene metadata editor so outcome, emotional turn, previous scene, and status can be edited before Context Pack writing. | Front Agent, Backend/API Creation Agent, Check Agent | Closed after implementation: Web Scene form covers Context Pack planning fields and full verification passes. |
| SG-012 | done | Main Agent | `codex/sg-005-import-structure-draft` | Let authors edit Scene style constraints used by Context Pack writing, including POV style, tense, tone, rhythm, diction, dialogue style, and banned patterns. | Front Agent, Backend/API Creation Agent, Check Agent | Closed after implementation: Web Scene style constraints flow into Context Pack and full verification passes. |
| SG-013 | done | Main Agent | `codex/sg-005-import-structure-draft` | Publish the current MVP as software version 0.1.6 with synchronized source versions, GitHub tag/release assets, updater metadata, and pushed branch state. | Release Creation Agent, Check Agent | Closed after release: branch/tag pushed, GitHub Release `v0.1.6` is latest, and updater metadata/assets are verified. |
| SG-014 | done | Main Agent | `codex/sg-014-import-hint-prefill` | Help authors resolve imported Scene POV/location labels by pre-filling explicit Character/Location canon seed forms without automatic graph writes. | Front Agent, Check Agent | Closed after implementation: Web hint actions are form-only, existing seed buttons remain the explicit canon write path, and verification passes. |
| SG-015 | done | Main Agent | `codex/sg-014-import-hint-prefill` | Carry newly seeded Character/Location stable IDs back into the current Scene metadata form without auto-saving Scene graph updates. | Front Agent, Check Agent | Closed after implementation: seed-created IDs are copied only into local Scene form state and verification passes. |
| SG-016 | done | Main Agent | `codex/sg-014-import-hint-prefill` | Let imported Scene POV/location hints reuse exact-matching existing canon Character/Location IDs from the Web sidebar. | Front Agent, Check Agent | Closed after implementation: exact matches can fill local Scene form IDs without saving graph updates, and verification passes. |
| SG-017 | done | Main Agent | `codex/sg-017-agent-discussion-localization` | Add Chinese-first localization coverage and an Agent discussion/selected-text revision path that creates non-canon proposals only. | Front Agent, Localization Worker, Backend/API Creation Agent, Check Agent | Closed for v0.1.7 release: implementation, localization pass, browser validation, tests, build, installer, and release asset generation passed. |

## SG-005 Acceptance Criteria

- Empty projects can accept an imported local manuscript/document without requiring a pre-existing chapter or scene.
- Agent analysis creates a non-canon, author-editable `project_structure_draft` proposal that contains proposed chapters and scenes with summaries and source provenance.
- Official Chapter/Scene Graph Store nodes are created only after the author explicitly accepts and applies the proposal through a backend API.
- The structure draft/apply flow never writes CandidateFacts or canon facts, and never imports private manuscript prose into coordination files.
- The left sidebar shows current project information when a project exists, offers explicit Edit and New Project controls, and shows the create form only when requested or when no project exists.
- Existing manual chapter/scene creation remains available and project-scoped.

## SG-005 Non-Goals

- Do not auto-commit extracted facts, characters, locations, or world rules to canon in this task.
- Do not build a full manuscript segmentation editor with drag/drop or rich diffing.
- Do not store imported document content in coordination Markdown or Git.
- Do not replace `fact_draft` or CandidateFact review flows.

## SG-005 Verification

- Focused API tests for project-level import-to-structure proposal creation and accepted proposal application.
- Canon safety tests proving structure draft generation does not create Chapter/Scene nodes until explicit apply.
- Frontend type/build checks for the new project-level import action and sidebar project view/edit/create modes.
- `python -m pytest -q`
- `python -m ruff check .`
- `npm --prefix apps/web run build`

## SG-006 Acceptance Criteria

- Re-applying the same accepted `project_structure_draft` returns the previously derived Chapter/Scene nodes instead of attempting duplicate Graph Store writes.
- If a target node id already exists from unrelated provenance, the apply action still fails with a conflict.
- The Web workbench distinguishes a first application from an already-applied retry in its Chinese notice.
- The behavior remains scoped to Chapter/Scene structure application and does not create CandidateFacts or other story-bible canon nodes.

## SG-006 Verification

- Focused API regression for repeated project-structure apply.
- `python -m pytest -q`
- `python -m ruff check .`
- `npm --prefix apps/web run build`
- Final verification on 2026-07-04: focused project-structure API tests passed, full `python -m pytest -q` passed with 115 passed / 1 skipped, `python -m ruff check .` passed, `npm --prefix apps/web run build` passed, and `git diff --check` reported no whitespace errors.

## SG-007 Acceptance Criteria

- Authors can update an existing Scene's title, ordering, POV character id, location id, timeline position, goal, conflict, required characters, include/violation constraints, and status through an explicit backend route.
- The route requires `full` permission, project-scopes the scene, records reviewer/rationale/source provenance, and persists JSON graph updates.
- Updating Scene metadata does not create CandidateFacts, characters, locations, world rules, drafts, or proposal artifacts.
- The Web workbench exposes a Chinese-first edit action for the selected scene so imported `pov_label` / `location_label` hints can be resolved into stable ids before Context Pack writing.

## SG-007 Verification

- Focused API regression for selected Scene metadata update and candidate-safety.
- Frontend type/build checks for selected-scene edit UI.
- `python -m pytest -q`
- `python -m ruff check .`
- `npm --prefix apps/web run build`
- Final verification on 2026-07-04: focused project-structure API tests passed, full `python -m pytest -q` passed with 116 passed / 1 skipped, `python -m ruff check .` passed, `npm --prefix apps/web run build` passed, and `git diff --check` reported no whitespace errors.

## SG-008 Acceptance Criteria

- FastAPI exposes read-only project-scoped Character and Location lists that return stable IDs and node properties without creating graph events, drafts, candidates, or proposals.
- Lists include only CANON nodes that belong to the requested project and do not leak other project data.
- The Web workbench loads these lists for the selected project and offers them as POV/location options in the Scene metadata form while still allowing manual stable IDs.
- Newly created Character/Location seed actions refresh the option lists and make the created ID visible to the author.

## SG-008 Verification

- Focused API regression for project-scoped Character/Location list filtering.
- Frontend type/build checks for POV/location option UI.
- `python -m pytest -q`
- `python -m ruff check .`
- `npm --prefix apps/web run build`
- Final verification on 2026-07-04: focused project-structure API tests passed, full `python -m pytest -q` passed with 117 passed / 1 skipped, `python -m ruff check .` passed, `npm --prefix apps/web run build` passed, and `git diff --check` reported no whitespace errors.

## SG-009 Acceptance Criteria

- Authors can update an existing Chapter's title, volume/chapter order, summary, purpose, and status through an explicit backend route.
- The route requires `full` permission, project-scopes the chapter, records reviewer/rationale/source provenance, and persists JSON graph updates.
- Updating Chapter metadata does not create CandidateFacts, Drafts, Proposal Artifacts, scenes, or unrelated graph nodes.
- The Web workbench exposes Chinese-first load/save controls for the selected chapter so imported chapter structure can be corrected after apply.

## SG-009 Verification

- Focused API regression for selected Chapter metadata update and no candidate/proposal side effects.
- Frontend type/build checks for selected-chapter edit UI.
- `python -m pytest -q`
- `python -m ruff check .`
- `npm --prefix apps/web run build`
- Final verification on 2026-07-04: focused project-structure API tests passed, full `python -m pytest -q` passed with 118 passed / 1 skipped, `python -m ruff check .` passed, `npm --prefix apps/web run build` passed, and `git diff --check` reported no whitespace errors.

## SG-010 Acceptance Criteria

- The Web Chapter metadata form includes volume index, chapter index, summary, purpose, and status for the selected chapter.
- Saving Chapter metadata sends every supported backend Chapter update field while retaining explicit author provenance.
- Loading a selected chapter hydrates all editable Chapter fields from the backend project outline.
- This remains an author-edit path only; it does not create CandidateFacts, Drafts, Proposal Artifacts, scenes, or unrelated graph nodes.

## SG-010 Verification

- Frontend type/build checks for expanded Chapter metadata controls.
- `python -m pytest -q`
- `python -m ruff check .`
- `npm --prefix apps/web run build`
- Final verification on 2026-07-04: full `python -m pytest -q` passed with 118 passed / 1 skipped, `python -m ruff check .` passed, `npm --prefix apps/web run build` passed, and `git diff --check` reported no whitespace errors.

## SG-011 Acceptance Criteria

- The Web Scene metadata form includes outcome, emotional turn, previous scene id, and status for the selected scene.
- Saving Scene metadata sends every supported scalar planning field needed by Context Pack writing while retaining explicit author provenance.
- Loading a selected scene hydrates all editable Scene planning fields from the backend project outline / graph node properties.
- This remains an author-edit path only; it does not create CandidateFacts, Drafts, Proposal Artifacts, chapters, or unrelated graph nodes.

## SG-011 Verification

- Focused API regression for Scene metadata update fields that affect Context Pack writing.
- Frontend type/build checks for expanded Scene metadata controls.
- `python -m pytest -q`
- `python -m ruff check .`
- `npm --prefix apps/web run build`
- Final verification on 2026-07-04: focused project-structure API tests passed, full `python -m pytest -q` passed with 118 passed / 1 skipped, `python -m ruff check .` passed, `npm --prefix apps/web run build` passed, and `git diff --check` reported no whitespace errors.

## SG-012 Acceptance Criteria

- The Web Scene metadata form includes editable style constraints for POV style, tense, tone, sentence rhythm, diction, dialogue style, and banned patterns.
- Creating or updating a Scene sends `style_constraints` only through the explicit author metadata path with reviewer/rationale/source provenance.
- Loading a selected scene hydrates style constraints from backend project outline / graph node properties.
- Context Pack construction reflects the authored style constraints and banned patterns.
- This remains an author-edit path only; it does not create CandidateFacts, Drafts, Proposal Artifacts, style samples, chapters, or unrelated graph nodes.

## SG-012 Verification

- Focused API regression for Scene style constraints flowing into Context Pack.
- Frontend type/build checks for expanded style constraint controls.
- `python -m pytest -q`
- `python -m ruff check .`
- `npm --prefix apps/web run build`
- Final verification on 2026-07-04: focused project-structure API tests passed, full `python -m pytest -q` passed with 118 passed / 1 skipped, `python -m ruff check .` passed, `npm --prefix apps/web run build` passed, and `git diff --check` reported no whitespace errors.

## SG-013 Acceptance Criteria

- `VERSION`, Python package metadata, Web package/display version, desktop package, Cargo package/lock, Tauri config, API metadata, and release docs all agree on `0.1.6`.
- Verification passes after the version bump and SG-012 implementation.
- The desktop build produces the Windows NSIS setup executable and Tauri updater `.sig` for 0.1.6.
- `latest.json` points to the GitHub `v0.1.6` release asset and uses the matching updater signature.
- GitHub receives the branch, tag `v0.1.6`, release assets, and release metadata only for software distribution.
- Local novel workspaces, canon, drafts, imported documents, project settings, review state, API keys, and private prose are not published.

## SG-013 Verification

- Version consistency search for `0.1.6` and stale project `0.1.5` references.
- `python -m pytest -q`
- `python -m ruff check .`
- `npm --prefix apps/web run build`
- `npm --prefix apps/desktop run build:installer`
- `apps/desktop/scripts/prepare-release-assets.ps1`
- GitHub tag/release verification for `v0.1.6`.
- Final verification on 2026-07-04: version consistency passed, full `python -m pytest -q` passed with 118 passed / 1 skipped, `python -m ruff check .` passed, `npm --prefix apps/web run build` passed, `npm --prefix apps/desktop run build:installer` passed, `latest.json` signature/URL verification passed, branch and tag were pushed to GitHub, and GitHub Release `v0.1.6` is marked Latest with installer, `.sig`, and `latest.json` assets.

## SG-014 Acceptance Criteria

- When a selected imported Scene has `pov_label` or `location_label`, the Web sidebar offers Chinese-first actions to copy those labels into the existing Character/Location seed forms.
- The hint actions only update local form state; they do not call backend seed APIs, create CandidateFacts, create Proposal Artifacts, or write Graph Store canon.
- Authors still explicitly create canon Character/Location nodes through the existing seed buttons with `full` permission and provenance.
- Existing manual Character/Location seed entry remains available for non-import workflows.

## SG-014 Verification

- `npm --prefix apps/web run build`
- `python -m pytest -q`
- `python -m ruff check .`
- `git diff --check`
- Final verification on 2026-07-04: `npm --prefix apps/web run build` passed, full `python -m pytest -q` passed with 118 passed / 1 skipped, `python -m ruff check .` passed, `git diff --check` passed, and local API/Web smoke returned HTTP 200.

## SG-015 Acceptance Criteria

- After an explicit Character seed succeeds and the current Scene metadata form has no POV character ID, the Web UI fills the new stable Character ID into `pov_character_id` and adds it to `required_characters`.
- After an explicit Location seed succeeds and the current Scene metadata form has no location ID, the Web UI fills the new stable Location ID into `location_id`.
- These link-back actions only mutate local React form state; they do not call the Scene metadata PATCH route, create CandidateFacts, create Proposal Artifacts, or write additional Graph Store canon.
- The success notices make the remaining explicit `保存场景元数据` step clear before the Scene node receives the new IDs.

## SG-015 Verification

- `npm --prefix apps/web run build`
- `python -m pytest -q`
- `python -m ruff check .`
- `git diff --check`
- Final verification on 2026-07-04: Web build passed, full `python -m pytest -q` passed with 118 passed / 1 skipped, `python -m ruff check .` passed, and `git diff --check` reported no whitespace errors.

## SG-016 Acceptance Criteria

- When an imported Scene `pov_label` exactly matches an existing project Character display name or ID, the Web sidebar offers a Chinese-first action to fill that stable ID into the current Scene metadata form.
- When an imported Scene `location_label` exactly matches an existing project Location display name or ID, the Web sidebar offers a Chinese-first action to fill that stable ID into the current Scene metadata form.
- Filling an existing Character also adds the stable ID to `required_characters` if missing.
- These match actions only mutate local React form state; they do not call backend seed APIs, save Scene metadata, create CandidateFacts, create Proposal Artifacts, or write Graph Store canon.

## SG-016 Verification

- `npm --prefix apps/web run build`
- `python -m pytest -q`
- `python -m ruff check .`
- `git diff --check`
- Final verification on 2026-07-04: Web build passed, full `python -m pytest -q` passed with 118 passed / 1 skipped, `python -m ruff check .` passed, and `git diff --check` reported no whitespace errors.

## SG-017 Acceptance Criteria

- User-facing Web/Tauri workbench text is Chinese-first through shared localization resources rather than scattered one-off English labels.
- The Web workbench exposes an `Agent` tab where authors can discuss the current scene, mark a selected draft span, include current Context Pack/draft text, include already-imported local-library snippets, optionally request web search, and ask for discussion, selected-span revision, or full-scene revision.
- `POST /projects/{project_id}/scenes/{scene_id}/agent-discussion` requires `read_generate` permission and configured LLM credentials.
- Agent discussion output creates only Proposal Store `scene_rebuild` or `scene_draft` artifacts; it must not overwrite Draft Store, create CandidateFacts, write Graph Store canon, or bypass proposal review/promotion.
- Selected-span revision produces a full `scene_draft` proposal only when the selected text is uniquely found in the supplied base draft; otherwise it falls back to a `scene_rebuild` note.
- Documentation keeps GitHub release/update synchronization distinct from local novel workspace/canon/draft/review data.

## SG-017 Verification

- Focused API tests for Agent discussion proposal creation, selected-span replacement, web-search context, and no draft/fact/graph mutation.
- `python -m pytest -q`
- `python -m ruff check .`
- `npm --prefix apps/web run build`
- `npm --prefix apps/desktop run build:installer`
- Version consistency and GitHub release verification for the new release tag.
- Final local verification on 2026-07-06: focused Agent discussion API coverage is included in full `python -m pytest -q` (120 passed / 1 skipped), `python -m ruff check .` passed, `npm --prefix apps/web run build` passed, browser validation passed on desktop and 390px mobile viewports with no console errors, `git diff --check` reported no whitespace errors, and `npm --prefix apps/desktop run build:installer` regenerated the v0.1.7 NSIS installer, `.sig`, and `latest.json`.

## SG-003 Acceptance Criteria

- `proposal_artifact_v1` exists as a versioned contract with explicit artifact types, statuses, source refs, provenance, versioning, and review decision semantics.
- Proposal artifacts are stored separately from Draft Store, Candidate Store, Graph Store, workflow checkpoints, and frontend-only state.
- Author and Agent revisions create versioned proposal history without mutating canon or current scene drafts.
- Accepted proposals do not automatically become canon. Promotion to scene draft, CandidateFact, or canon review is explicit and routed through existing backend boundaries.
- FastAPI exposes real local API routes for proposal create/list/get/update/review actions with project scoping and permission gates.
- Web/Tauri UI can show a Chinese-first `协作草稿箱` backed by API data, not fixtures.
- Check Agent can prove imported documents, LLM outputs, proposal edits, and fact drafts cannot directly mutate Graph Store canon.

## SG-003 Non-Goals

- Do not replace CandidateFact or ReviewService with proposal artifacts.
- Do not make proposals a second canon source.
- Do not implement rich collaborative multi-user editing in this phase.
- Do not require external LLM calls for proposal storage tests.
- Do not commit private manuscript prose, API keys, generated long-form output, or local workspace data.

## SG-003 Verification

- Focused unit/API tests for proposal models, store versioning, project-scoped listing, review state transitions, and promotion boundary behavior.
- Permission tests: `read_only` may read proposals; `read_generate` may create/revise; `full` is required for accept/reject and any promotion that can affect drafts/candidates/canon review.
- Canon safety tests: proposal create/revise/review must not change Graph Store, Draft Store, or Candidate Store unless an explicit promotion endpoint is used.
- `python -m pytest`
- `python -m ruff check .`
- `npm --prefix apps/web run build` after frontend changes.

## SG-004 Acceptance Criteria

- Root `VERSION`, package metadata, Web displayed version, Tauri config, Cargo package, lockfiles, API metadata, and release docs agree on `0.1.2`.
- Desktop build produces a Windows executable, NSIS setup executable, and Tauri updater `.sig` for 0.1.2.
- Published GitHub Release `v0.1.2` includes the installer asset, matching `.sig`, and `latest.json`.
- GitHub latest-release endpoint resolves to `v0.1.2`, and `latest.json` points to a downloadable 0.1.2 installer URL.
- GitHub remains only the software release/update channel; no local story workspace, canon, drafts, settings, imported documents, private API keys, or private prose are published.

## SG-004 Verification

- `python -m pytest -q`
- `python -m ruff check .`
- `npm --prefix apps/web run build`
- `npm --prefix apps/desktop run build:installer`
- `gh release view v0.1.2 --json tagName,isLatest,assets,url`
- Download or HTTP-check the published `latest.json` and installer asset URLs.

## SG-002 Acceptance Criteria

- Empty persistent or desktop workspaces do not silently show seeded demo content as real author projects.
- The Web/Tauri workbench reads project trees, graph/timeline previews, drafts, workflow runs, and pending facts from FastAPI.
- Built-in fantasy demo remains available only through explicit `Seed Demo` / `POST /demo/seed` with `full` permission and provenance.
- Local imports and LLM outputs can become drafts or pending candidates only through backend APIs; they never directly mutate Graph Store canon.
- `scene_generation` workflow surfaces `build_context`, `write_draft`, `check_continuity`, `extract_state`, and `human_review`.
- Candidate facts mutate canon only through ReviewService accept/edit-accept paths; reject/defer preserve audit history without canon writes.
- Private API keys, imported document prose, and local workspace data are not written to coordination files or committed.

## SG-002 Non-Goals

- Do not delete the explicit fantasy demo fixture used by tests and onboarding.
- Do not introduce cloud workspace synchronization or GitHub synchronization for novel data.
- Do not add new contract fields unless Contract Agent identifies a real incompatibility.
- Do not describe source-built or local updater artifacts as a published signed release channel.

## SG-002 Verification

- `python -m pytest`
- `python -m ruff check .`
- `npm --prefix apps/web run build`
- Private smoke test with the user-supplied local DOCX input and existing local LLM key, without logging document prose.
- Optional desktop build/smoke only if frontend/API checks leave desktop-hosting behavior uncertain.

## Task Template

```text
ID:
Status:
Owner:
Branch:
Goal:
Relevant files:
Required agents:
Acceptance criteria:
Non-goals:
Verification:
Next action:
```
