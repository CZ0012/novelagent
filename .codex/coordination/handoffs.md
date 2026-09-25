# Cross-Agent Handoffs

Use this file when one agent discovers a problem that another agent must address. Handoffs should be concrete, branch-aware, and small enough to act on.

## Open Handoffs

No open handoffs.

## Handoff Template

```text
Task:
From:
Requested agent:
Source branch:
Relevant files:
Problem:
Expected change:
Contract boundary:
Verification:
Unblock condition:
Status:
```

## Closed Handoffs

### SG-003-HANDOFF-001

Task: SG-003D
From: Front Agent
Requested agent: Workflow / Backend Creation Agent
Source branch: `codex/sg-003-front-proposal-inbox`
Relevant files: `apps/web/src/App.tsx`, `apps/web/src/api.ts`, `apps/api/main.py`, `storygraph/stores/proposal_store.py`
Problem: The `协作草稿箱` UI needs explicit backend promotion routes before it can safely expose `转为场景草稿`, `抽取为候选事实`, and `提交 canon review` actions.
Expected change: Add permission-gated backend routes that promote accepted/non-terminal proposal content through existing Draft Store, CandidateFact, and ReviewService boundaries without direct Graph Store writes.
Contract boundary: `proposal_artifact_v1` remains non-canon; promotions must record proposal/version refs in derived audit metadata and preserve existing `candidate_fact_v1` and ReviewService semantics.
Verification: API tests prove proposal create/revise/review does not mutate Graph/Draft/Candidate stores, while explicit promotion routes mutate only their intended stores with required permission gates.
Resolution: Added accepted `scene_draft` proposal promotion to Draft Store, accepted `fact_draft` proposal promotion to pending CandidateFacts from a real source draft, and `scene_generation` `output_target=proposal_workspace`.
Status: closed

## SG-023B — Presets, exact continuation, and provider discovery

Status: closed; independently checked and integrated. Owner: Contract/Creation Agent.

- Added `agent_runtime_v1` and additive Proposal/workflow provenance clarifications.
- Settings persist custom System prompt presets with immutable built-ins and partial-update compatibility; named Chinese concise, balanced, and English precise choices affect creative provider calls only.
- Added `continue_scene`: explicit scoped Draft ID, bounded trailing input excerpt, complete original Draft prefix retained server-side, new reviewable Proposal only.
- Added configured third-party model discovery without automatic switching; provider errors omit raw response bodies and network reasons.
- CLI loads the same workspace provider and preset settings. Existing direct local CLI permissions remain distinct from API permission controls.
- Verification: 35 focused Python tests passed (including 18 new preset/provider/continuation tests); Ruff passed for changed runtime and test files.
- Root owns README, architecture, desktop docs, live private-source testing, release and GitHub delivery. Front Agent owns localized UI controls and explicit continuation action. Check Agent owns independent full-suite validation.
- No private manuscript or credentials were copied into tracked files or coordination.

## SG-023 final integration

Status: closed. Code, acceptance, GitHub source synchronization and v0.1.12 publication complete; remote assets match the locally verified installer/signature/metadata.

The persistent-workspace factory mismatch, stale editor load/save scope, predictable structure-apply partial writes, and English catalog runtime dependency are fixed. Automated checks, production browser validation, private chapter continuation/revision/restart, hidden packaged backend startup, updater signature verification and in-memory tamper rejection passed. Private text stays outside tracked files. Scope and unverified browser download completion are recorded in `docs/acceptance-0.1.12.md`; no hard-crash cross-store transaction or whole-novel benchmark claim is made.

## SG-024 — Partial Windows update repair

Status: closed. Local repair and public v0.1.13 software/update release complete; downloaded assets match verified local package.

Review reproduced the main-before-backend-before-registry failure path and destructor-cleanup gap in pinned Windows updater. Native prepare/cancel gate, bounded managed process shutdown, exclusive replacement probe and exact-install-path NSIS preflight now guard updates. Web uses download/dirty-guard/prepare/install and reports legacy/current/unknown backend versions separately. Check ran 5 maintained installer checks including real lock failure and unrelated same-name process preservation; 8 Rust and 55 Web tests passed, plus 7 API/version regressions. Main verified Chinese/English browser diagnostics, installed 0.1.13 binary/runtime/installation-record consistency, updater signature and untouched author workspace files. Evidence: `docs/windows-update-recovery.md`. No private installation paths or workspace contents enter software release.


## SG-025 — Novel editor verification

Status: closed. Code, production-browser acceptance, independent package verification and public v0.1.14 software release complete. Re-downloaded installer, signature and latest.json exactly match the verified local files.

Front delivered a real folding outline, adjacent Agent and scoped title/metadata edits. Review found stale metadata targeting and malformed language-input cases; owners fixed and rechecked them. Production browser acceptance additionally found nullable planning fields causing ContextPack validation500 for minimal scenes; Creation normalized projections with explicit gaps and kept the complete-generation safety gate. Final Python suite316 passed/1skipped, Web62passed and productionbuild passed. Root verified same-scene dirty preservation, exact saved-Draft continuation/selection proposals, pinned chapter metadata and bilingual/responsive behavior using only isolated synthetic fixtures. No author workspace mutation or external model call in this task.

Final installer: pinned updater signature verified, tampered copy rejected, exact backend/Web payloads match final builds. Native updater guard remains unchanged from verified 0.1.13. Changed source and decoded package credential/private-path scans passed; no user application process was stopped.
