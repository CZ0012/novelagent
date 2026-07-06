# Branch Map

Use this file to make asynchronous local git work visible. A branch entry does not imply that the branch has been pushed, committed, reviewed, or merged.

## Naming

Preferred format:

```text
codex/sg-123-short-scope
```

Use the existing user-requested branch name if the user asks for one.

## Active And Planned Branches

| Branch | Task | Owner | Base | Scope | Status | Merge target |
| --- | --- | --- | --- | --- | --- | --- |
| `codex/desktop-workbench` | SG-001 | Main Agent | existing branch | Subagent roster and coordination Markdown baseline. | current branch | project default branch when ready |
| `codex/sg-002-real-api-demo-cleanup` | SG-002 | Main Agent | `codex/desktop-workbench` | Coordinate demo cleanup and actual API-backed demonstration flow into implementable workstreams. | ready-for-review | project default branch when ready |
| `codex/sg-002-contract-api-boundary` | SG-002A | Contract Agent | `codex/sg-002-real-api-demo-cleanup` | Confirm existing v1 contracts and FastAPI routes cover the real API demo flow. | ready-for-review | `codex/sg-002-real-api-demo-cleanup` |
| `codex/sg-002-front-real-api-workbench` | SG-002B | Front Agent | `codex/sg-002-real-api-demo-cleanup` | Remove or isolate frontend sampleData and keep all claimed workspace state API-backed. | ready-for-review | `codex/sg-002-real-api-demo-cleanup` |
| `codex/sg-002-backend-real-flow` | SG-002C | Backend/API Creation Agent | `codex/sg-002-real-api-demo-cleanup` | Verify persistent JSON workspace routes for project, draft, workflow, candidates, and review. | ready-for-review | `codex/sg-002-real-api-demo-cleanup` |
| `codex/sg-002-desktop-api-host` | SG-002D | Desktop Creation Agent | `codex/sg-002-real-api-demo-cleanup` | Validate Tauri as a host for the same FastAPI + React workbench and managed backend. | ready-for-review | `codex/sg-002-real-api-demo-cleanup` |
| `codex/sg-002-docs-runtime-truth` | SG-002E | Docs Creation Agent | `codex/sg-002-real-api-demo-cleanup` | Keep docs honest about CLI, API/Web, desktop source builds, and signed release/update channels. | ready-for-review | `codex/sg-002-real-api-demo-cleanup` |
| `codex/sg-002-check-real-api-demo` | SG-002F | Check Agent | `codex/sg-002-real-api-demo-cleanup` | Run tests, lint/build checks, contract drift checks, permission checks, and canon-safety checks. | ready-for-review | `codex/sg-002-real-api-demo-cleanup` |
| `codex/sg-002-review-acceptance` | SG-002G | Review Agent | `codex/sg-002-real-api-demo-cleanup` | Final acceptance review for demo cleanup and real API-backed workflow claims. | planned | `codex/sg-002-real-api-demo-cleanup` |
| `codex/sg-002-real-agent-docx-test` | SG-002H | Test Creation Agent | `codex/sg-002-real-api-demo-cleanup` | Private smoke test using the local LLM key and user-supplied local DOCX without storing prose. | ready-for-review | `codex/sg-002-real-api-demo-cleanup` |
| `codex/sg-003-proposal-workspace` | SG-003 | Main Agent | `codex/desktop-workbench` | Coordinate Proposal Workspace planning and phased implementation. | done | project default branch when ready |
| `codex/sg-003-proposal-contract` | SG-003A | Contract Agent | `codex/sg-003-proposal-workspace` | Define `proposal_artifact_v1`, API semantics, statuses, provenance, review decisions, and promotion boundaries. | done | `codex/sg-003-proposal-workspace` |
| `codex/sg-003-proposal-store-api` | SG-003B | Backend/API Creation Agent | `codex/sg-003-proposal-workspace` | Implement Proposal Store models and FastAPI routes with versioning and permission gates. | done | `codex/sg-003-proposal-workspace` |
| `codex/sg-003-workflow-proposals` | SG-003C | Workflow Creation Agent | `codex/sg-003-proposal-workspace` | Route future Agent scene/fact outputs into proposal artifacts before promotion. | done | `codex/sg-003-proposal-workspace` |
| `codex/sg-003-front-proposal-inbox` | SG-003D | Front Agent | `codex/sg-003-proposal-workspace` | Add the API-backed Chinese-first `协作草稿箱` UI. | done | `codex/sg-003-proposal-workspace` |
| `codex/sg-003-docs-proposal-workspace` | SG-003E | Docs Creation Agent | `codex/sg-003-proposal-workspace` | Document Proposal Workspace boundaries, promotion paths, and canon safety. | done | `codex/sg-003-proposal-workspace` |
| `codex/sg-003-check-proposal-workspace` | SG-003F | Check Agent | `codex/sg-003-proposal-workspace` | Run proposal tests, lint/build checks, permission checks, and contract drift checks. | done | `codex/sg-003-proposal-workspace` |
| `codex/sg-003-review-acceptance` | SG-003G | Review Agent | `codex/sg-003-proposal-workspace` | Final acceptance review for iterative proposal workspace behavior. | done | `codex/sg-003-proposal-workspace` |
| `codex/sg-004-release-0.1.2` | SG-004 | Main Agent | `codex/desktop-workbench` | Version, package, publish, and verify the 0.1.2 desktop release/update channel. | done | GitHub `main` / release tag `v0.1.2` |
| `codex/sg-004-version-bump` | SG-004A | Release Creation Agent | `codex/sg-004-release-0.1.2` | Synchronize 0.1.2 source versions and release docs. | done | `codex/sg-004-release-0.1.2` |
| `codex/sg-004-release-checks` | SG-004B | Check Agent | `codex/sg-004-release-0.1.2` | Verify tests, lint, Web build, installer build, and local release assets. | done | `codex/sg-004-release-0.1.2` |
| `codex/sg-004-github-release` | SG-004C | Release Creation Agent | `codex/sg-004-release-0.1.2` | Commit, push, tag, and publish GitHub Release assets for v0.1.2. | done | GitHub release `v0.1.2` |
| `codex/sg-004-release-acceptance` | SG-004D | Review Agent | `codex/sg-004-release-0.1.2` | Verify the published GitHub latest release and updater metadata. | done | `codex/sg-004-release-0.1.2` |
| `codex/sg-005-import-structure-draft` | SG-005 | Main Agent | `main` | Project-level imported novel analysis, `project_structure_draft` proposals, explicit apply-to-chapters/scenes, and sidebar project view/edit/create cleanup. | done | project default branch when ready |
| `codex/sg-005-import-structure-draft` | SG-006 | Main Agent | current branch | Repeat-safe `project_structure_draft` apply semantics, API regression coverage, and Web notice handling. | done | project default branch when ready |
| `codex/sg-005-import-structure-draft` | SG-007 | Main Agent | current branch | Existing Scene metadata edit route and Web controls for resolving imported structure scenes before writing. | done | project default branch when ready |
| `codex/sg-005-import-structure-draft` | SG-008 | Main Agent | current branch | Project-scoped Character/Location list APIs and Web POV/location option controls. | done | project default branch when ready |
| `codex/sg-005-import-structure-draft` | SG-009 | Main Agent | current branch | Existing Chapter metadata edit route and Web controls for correcting imported chapter structure. | done | project default branch when ready |
| `codex/sg-005-import-structure-draft` | SG-010 | Main Agent | current branch | Complete Web Chapter metadata form coverage for volume, purpose, and status. | done | project default branch when ready |
| `codex/sg-005-import-structure-draft` | SG-011 | Main Agent | current branch | Complete Web Scene metadata form coverage for outcome, emotional turn, previous scene, and status. | done | project default branch when ready |
| `codex/sg-005-import-structure-draft` | SG-012 | Main Agent | current branch | Web Scene style constraint editor for Context Pack writing. | done | project default branch when ready |
| `codex/sg-005-import-structure-draft` | SG-013 | Main Agent | current branch | Publish 0.1.6 software release/update assets and push GitHub state. | done | GitHub release `v0.1.6` / project default branch when ready |
| `codex/sg-014-import-hint-prefill` | SG-014 | Main Agent | `codex/sg-005-import-structure-draft` | Web-only imported Scene POV/location hint prefill into explicit Character/Location seed forms. | done | project default branch when ready |
| `codex/sg-014-import-hint-prefill` | SG-015 | Main Agent | current branch | Web-only link-back from newly seeded Character/Location nodes into the current Scene metadata form. | done | project default branch when ready |
| `codex/sg-014-import-hint-prefill` | SG-016 | Main Agent | current branch | Web-only exact match from imported Scene POV/location hints to existing Character/Location canon nodes. | done | project default branch when ready |
| `codex/sg-017-agent-discussion-localization` | SG-017 | Main Agent | `codex/sg-014-import-hint-prefill` | Chinese-first localization coverage plus Agent discussion/selected-text revision into non-canon Proposal Store artifacts. | done | `main` / release tag `v0.1.7` |

## SG-002 Branch Notes

- The current workspace is on `codex/desktop-workbench`; SG-002 edits may be developed there until the user asks for physically separate local branches.
- The real-agent smoke input is local and private. Do not commit imported document content, API keys, generated prose, or workspace database files.
- KouriChat configuration was corrected locally to `llm_json_mode=false` because the provider rejected the OpenAI JSON response_format parameter. `deepseek-v4-flash` returned repeated provider busy responses, so the local config now uses the tested working KouriChat model `gpt-4o-mini`.
- If a subtask needs a contract shape change, pause implementation and record a handoff to Contract Agent before changing code.

## SG-003 Branch Notes

- Current implementation is starting on `codex/desktop-workbench` after SG-002 commit `283839a`; physical branch splits can be created later if parallel edits become necessary.
- Proposal artifacts are collaboration records only. They must not become canon, current scene drafts, CandidateFacts, or workflow checkpoints without explicit backend promotion paths and permission checks.
- Phase 1 contract/model/store/API is implemented and covered by focused tests plus full Python `pytest` and `ruff`.
- Explicit promotion/workflow boundaries are implemented: accepted `scene_draft` proposals can promote to Draft Store, accepted `fact_draft` proposals can submit CandidateFacts only from a real source draft, and `scene_generation` can output a `scene_draft` proposal with later steps skipped.
- Web `协作草稿箱` and docs are implemented. Any richer multi-user collaboration, richer editor UX, or deeper desktop smoke coverage should split into SG-004 rather than block SG-003.
- Check/Review stale-version feedback was fixed by requiring `expected_version` on proposal accept/reject routes and Web calls, plus regression coverage.
- Final verification on 2026-06-21: `python -m pytest -q` passed with 108 passed / 1 skipped, `python -m ruff check .` passed, `npm --prefix apps/web run build` passed, `git diff --check` reported no whitespace errors, and local API/Web previews were healthy.

## SG-004 Branch Notes

- Current implementation is still on `codex/desktop-workbench`; the release branch name is recorded for visibility, while the physical branch can stay as-is unless the user asks for branch splitting.
- GitHub publishing for this task means only software release/update synchronization: commit/tag/push plus GitHub Release assets and `latest.json`.
- Local Tauri output uses `StoryGraph Agent_0.1.2_x64-setup.exe`; GitHub Release upload uses normalized `StoryGraph.Agent_0.1.2_x64-setup.exe` and matching `.sig`, matching the existing v0.1.1 release asset convention.
- Local verification for the release commit passed: `pytest`, `ruff`, Web build, version consistency, full installer build, and regenerated 0.1.2 `latest.json`.
- Do not publish local workspaces, canon state, drafts, imported manuscript files, API keys, signing private keys, or generated private prose.

## SG-005 Branch Notes

- Current implementation is on `codex/sg-005-import-structure-draft` from `main` commit `ea19442`.
- Contract Agent scope: add the smallest `project_structure_draft` proposal boundary and explicit promotion/apply semantics.
- Front Agent scope: empty project should guide import/analyze first; the sidebar should show project info with Edit/New controls, not a persistent create form or prominent demo initialization.
- Backend/API Creation Agent scope: project-level imported document analysis may create only a Proposal Artifact; accepted structure proposals can create Chapter/Scene graph nodes through explicit backend apply.
- Check Agent scope: verify no imported manuscript text, API keys, or generated private prose enter Git or coordination files; generation must not write canon facts or CandidateFacts.
- Final verification on 2026-06-22: focused project-structure API tests passed, full `python -m pytest -q` passed with 114 passed / 1 skipped, `python -m ruff check .` passed, `npm --prefix apps/web run build` passed, local browser smoke confirmed no prominent demo initialization and import-first empty workspace copy, and `git diff --check` reported no whitespace errors.

## SG-006 Branch Notes

- Current implementation continues on `codex/sg-005-import-structure-draft` because SG-006 is a narrow follow-up to the same import-structure apply path.
- Repeated apply must not create duplicate Chapter/Scene canon nodes, CandidateFacts, or unrelated story-bible nodes.
- Existing target ids are reused only when their provenance matches the same structure proposal id and a non-future proposal version; unrelated id collisions remain conflicts.
- Final verification on 2026-07-04: focused project-structure API tests, full Python tests, Ruff, Web build, and diff whitespace checks passed.

## SG-007 Branch Notes

- Current implementation continues on `codex/sg-005-import-structure-draft` because SG-007 follows the same imported-structure authoring path.
- Scene metadata edits are explicit author operations; they may update an existing Scene node with provenance but must not create CandidateFacts, story-bible nodes, drafts, or proposal artifacts.
- Imported `pov_label` and `location_label` remain hints until the author enters stable `pov_character_id` and `location_id` values.
- Final verification on 2026-07-04: focused project-structure API tests, full Python tests, Ruff, Web build, and diff whitespace checks passed.

## SG-008 Branch Notes

- Current implementation continues on `codex/sg-005-import-structure-draft` because SG-008 supports the imported-structure scene metadata path.
- Character/Location lists are read-only convenience APIs over existing canon nodes; they must not infer or create story-bible entries from imported labels.
- Web controls should show stable IDs next to display names and keep manual ID entry possible for advanced author workflows.
- Final verification on 2026-07-04: focused project-structure API tests, full Python tests, Ruff, Web build, and diff whitespace checks passed.

## SG-009 Branch Notes

- Current implementation continues on `codex/sg-005-import-structure-draft` because SG-009 supports the same imported-structure author correction path.
- Chapter metadata edits are explicit author operations; they may update an existing Chapter node with provenance but must not create scenes, CandidateFacts, Drafts, Proposal Artifacts, or unrelated graph nodes.
- Editing a Chapter title does not rename the stable chapter id; IDs remain stable graph refs.
- Final verification on 2026-07-04: focused project-structure API tests, full Python tests, Ruff, Web build, and diff whitespace checks passed.

## SG-010 Branch Notes

- Current implementation continues on `codex/sg-005-import-structure-draft` because SG-010 completes the Chapter metadata editor introduced in SG-009.
- The frontend should send only supported Chapter metadata fields and explicit author provenance to the existing Chapter PATCH route.
- This task should not alter structure proposal application, scene creation, CandidateFact review, or story-bible seed semantics.
- Final verification on 2026-07-04: full Python tests, Ruff, Web build, and diff whitespace checks passed.

## SG-011 Branch Notes

- Current implementation continues on `codex/sg-005-import-structure-draft` because SG-011 completes the Scene metadata editor introduced in SG-007.
- Scene outcome, emotional turn, previous scene id, and status are planning metadata used by Context Pack / writing workflows; editing them must remain an explicit author operation with provenance.
- This task should not alter CandidateFact extraction/review or structure proposal application semantics.
- Final verification on 2026-07-04: focused project-structure API tests, full Python tests, Ruff, Web build, and diff whitespace checks passed.

## SG-012 Branch Notes

- Current implementation continues on `codex/sg-005-import-structure-draft` because SG-012 extends the Scene metadata editor for Context Pack writing.
- Style samples remain soft retrieval guidance; `style_constraints` become hard Context Pack guidance only when the author explicitly edits the Scene metadata.
- This task should not create style samples, CandidateFacts, Drafts, Proposal Artifacts, chapters, or unrelated graph nodes.
- Final verification on 2026-07-04: focused project-structure API tests, full Python tests, Ruff, Web build, and diff whitespace checks passed.

## SG-013 Branch Notes

- Current implementation continues on `codex/sg-005-import-structure-draft` because the user asked to publish the accumulated MVP progress after SG-012.
- GitHub work is only for software release/update distribution: commit/tag/push plus GitHub Release installer, `.sig`, and `latest.json`.
- Do not publish local story workspace data, canon state, drafts, imported manuscript files, API keys, signing private keys, or generated private prose.
- Final verification on 2026-07-04: branch and tag were pushed, GitHub Release `v0.1.6` is latest, assets are uploaded, and the latest updater endpoint returns version 0.1.6.

## SG-014 Branch Notes

- Current implementation is on `codex/sg-014-import-hint-prefill` so post-release MVP work is separated from the v0.1.6 release branch.
- Imported `pov_label` and `location_label` remain non-canon hints. Prefill actions may only update local Web form state; canon Character/Location creation still requires the existing explicit seed buttons and full permission.
- This task should not change `project_structure_draft` apply semantics, CandidateFact review, backend seed contracts, or imported document storage.
- Final verification on 2026-07-04: Web build, Python tests, Ruff, diff whitespace check, and API/Web local smoke passed.

## SG-015 Branch Notes

- Current implementation continues on `codex/sg-014-import-hint-prefill` because SG-015 is a narrow Web follow-up to the imported Scene hint resolution path.
- Character/Location seed buttons remain the only canon write in this flow. Filling Scene `pov_character_id`, `required_characters`, or `location_id` is local form state until the author explicitly saves Scene metadata.
- This task should not change backend seed contracts, structure proposal apply semantics, CandidateFact review, or imported document storage.
- Final verification on 2026-07-04: Web build, Python tests, Ruff, and diff whitespace checks passed.

## SG-016 Branch Notes

- Current implementation continues on `codex/sg-014-import-hint-prefill` because SG-016 completes the same imported hint resolution UI.
- Existing Character/Location matching is exact and uses already-loaded project-scoped canon list APIs. It may only fill local Scene form state; saving the Scene remains an explicit author action.
- This task should not create new backend routes, change seed contracts, alter CandidateFact review, or infer canon facts from imported prose.
- Final verification on 2026-07-04: Web build, Python tests, Ruff, and diff whitespace checks passed.

## SG-017 Branch Notes

- Current implementation is on `codex/sg-017-agent-discussion-localization`, created from `codex/sg-014-import-hint-prefill`, so merging it to `main` carries the previous SG-014 through SG-016 branch state plus the new Agent discussion/localization work.
- Agent discussion may read the current Context Pack, current draft editor text, already-imported local-library snippets, and author-enabled web search snippets. These are inputs to a non-canon Proposal Store artifact only.
- Selected-text revision can generate a full `scene_draft` proposal, but it must not overwrite the current Draft Store draft until the author explicitly accepts and promotes the proposal.
- GitHub synchronization for this branch remains only the software release/update channel: tag, release assets, updater signature, and `latest.json`.

## Branch Entry Template

```text
Branch:
Task:
Owner:
Base:
Scope:
Changed areas:
Check status:
Review status:
Merge target:
Notes:
```
