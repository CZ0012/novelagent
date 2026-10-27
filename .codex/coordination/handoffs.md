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

## SG-026 — Update preparation sharing violation

Initial finding (resolved below): the installed 0.1.13 client downloads and verifies the update, then fails its native replacement probe with Windows error 32 and restores its managed backend. Installer execution is not reached. This path was introduced by the 0.1.13 safety fix; 0.1.14 did not change it. Creation investigates real PyInstaller parent/child shutdown and probe timing, while Front separates failure stage from recovery outcome. No private paths, credentials or manuscript content belong in tracked records.

SG-026 verification: native transient-sharing retry and reviewed outline language repair are complete. Final validation: 377 Python passed/1 skipped, 75 Web, 11 Rust, 35 real backend lifecycle iterations and 5 real NSIS guard cases. Browser review/apply and an authorized private-copy provider response verified unchanged drafts, IDs and relations. Independent source and decoded-package privacy checks passed, pinned signature verified and tamper rejected. Publishing v0.1.15; running author app and original novel workspace remain untouched.

SG-026 closed: software commit 7715712/tag v0.1.15 and signed public release published. Re-downloaded installer, signature and latest.json match the independently verified local files byte for byte. Latest release metadata is stable v0.1.15 with exactly three software assets. No installed app or original novel workspace was modified. Older clients blocked by preparation require saving work, tray Quit and one manual same-directory installation.

## SG-027 final integration handoff (2026-09-25)

Front delivered manuscript reading/editing, exact selection requests, composition UI and bilingual catalogs; Contract/Creation delivered frozen backend/contracts with 420 distinct tested cases. Review delivered bounded red/green diffs and cleared provenance, CAS, recovery and cross-scope guards. Main completed synthetic browser and authorized isolated private-provider acceptance, including targeted fixes for missing composition application and diff layout overflow. Check independently validates final source, sidecar, signed package and exclusion of private data before publication.


## SG-028 final handoff

All product owners are frozen. Independent reciprocal reviews repaired URL diagnostic leakage, inaccurate rule-based model attribution, explicit-profile fallback, RTF deletion visibility and DOCX entry-name ambiguity. Main verified real files and authorized third-party calls only in ignored copies; malformed model JSON remains a rejected result. Check approved the signed 0.1.17 installer, source/bytecode/assets correspondence and exclusion of credentials and novel workspace data. Main owns software-only publication and public-byte verification.


SG-028 closed after signed release publication and three-asset download comparison. Backend, Front and Import owners completed reciprocal review; Main verified user-facing bilingual behavior and preserved original configuration/data. Check approved final source, sidecar and installer. See docs/acceptance-0.1.17.md for results and protocol limitations.

## 0.2.0 local candidate verification (2026-10-25)

Final backend full regression:755 passed,1skipped. Front245 fulltests plus20focused finaldisplay checks/build passed. Local Windows0.2.0 installer static/signature/tamper/privacy audit and isolatedpersistentbackend/restart smoke passed; no installation orpublication. Source16newruntime modules/75compiledsource matches and7Webassets verified. Offline browser exercised complete21stage bookbundle review/accept/apply and100chapter/200scene directory; fixtures clearly labeled synthetic.

Full real-provider book acceptance remains open under SG-031-BUDGET. Implementation/package evidence is not a substitute for that goal criterion. See docs/acceptance-0.2.0.md; author workspace/key material and generated acceptance outputs remain outside Git.


## 2026-10-25 Front final source and browser follow-up

Front fixed Context evidence, dirty Draft omission, source_changed recovery guidance, explicit Context build/refresh, and large-project inspector layout. Complete frontend259tests passed before the final button/layout additions; latest14focusedchecks/build passed. Main verified the isolated100chapter/200scene UI in Edge: Context action populates approvedplan/budget/seed protection, graph collapsed and expanded keep Context readable. Evidence remains in ignored UI-fixture folder; no real novel quality claim, paid model call, or author workspace mutation from UI test. Role rules mirrored by Main because Front could not write protected coordination files.

## SG-032 readiness handoff — 2026-10-27

Independent Review完成投影、完整作者审查权威、精确编辑授权和checkpoint fail-closed审查；omniscient belief合同偏差经Main授权最小修复，49项定向通过。API测试保留导入前HOME/key隔离且恢复环境，11项及Ruff通过。报告在忽略的 .storygraph/writer-visibility-independent-review-20261027.md。最终全回归、Web确认、新包构建交Main；旧59e2721包不含修改。真实整书50/100章规划，旧Writer v6为局部修正后通过；新隔离只有离线UI/假模型证据，文学目标仍active。未改源计划、未真实调用、未提交。


## Reliable chronology integration handoff

Independent synthetic reproduction confirmed automatic narrative NEXT_SCENE can expose a later event at an earlier parallel Scene entry. Main authorized a bounded shared-helper correction; explicit manual chronology remains authoritative, legacy automatic edges require exact creation/source binding, and reads exclude stale proofs without mutating canon. Creation owns implementation/tests; Review owns matching contracts/docs and independent acceptance. Ongoing noncanon planning remains separate; no private prose, credentials or live runtime state belongs here.

Reliable chronology review handoff: contracts/docs/role guidance synchronized with all four automatic application paths and complete internal fork/join order. Independent synthetic checks verify no future-state projection, both-branch state/knowledge convergence, audited time-edit recovery, unaudited mutation rejection and unchanged unapplied Project-only PLAN snapshot. Scene evidence fingerprint already invalidates old reports when unsafe relations leave actual facts. Narrow parser/provenance issues found during review are resolved. Main owns final whole-suite validation and rebuilt local candidate; no paid call or author-workspace mutation in this software review.


Final handoff, 2026-10-27: Creation/Review work for SG-031 and SG-032 is closed under the bounded acceptance criteria. Main completed mechanical source/currentness reconciliation, independent framework and adjacent-prose review, preserved unsuccessful evidence and prepared local delivery. Runtime source remains ab343b8 and the verified0.2.0 installer is unchanged. No agent has pending model dispatch or source changes. See docs/acceptance-0.2.0.md for exact verification and limitations; private fiction artifacts remain ignored, outside coordination.
