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
