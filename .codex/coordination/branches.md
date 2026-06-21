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
