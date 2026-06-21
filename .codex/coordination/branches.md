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

## SG-002 Branch Notes

- The current workspace is on `codex/desktop-workbench`; SG-002 edits may be developed there until the user asks for physically separate local branches.
- The real-agent smoke input is local and private. Do not commit imported document content, API keys, generated prose, or workspace database files.
- KouriChat configuration was corrected locally to `llm_json_mode=false` because the provider rejected the OpenAI JSON response_format parameter. `deepseek-v4-flash` returned repeated provider busy responses, so the local config now uses the tested working KouriChat model `gpt-4o-mini`.
- If a subtask needs a contract shape change, pause implementation and record a handoff to Contract Agent before changing code.

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
