# SG-029A planning handoff

Owner: Contract/Creation planning agent. Shared branch: codex/sg-029-longform-collaboration.

Implemented models/longform.py, services/longform_planning.py, planning contract
and proposal subtype clarification. Main owns API wiring and role/runtime docs.
Generation service signatures and route shapes were sent to Main and Front.
Application requires the existing local persist_snapshot callback.

Checks: python -m pytest tests/test_longform_planning.py -q: 36 passed.
python -m ruff check on the three owned Python files: all checks passed.
Includes full 500k target, 5 volumes/100 chapters/200 scenes over 20 bounded
batches; no Draft creation; exact budgets; seed/payoff validation; stale canon;
review gates; concurrent apply; staged persistence failure; restart receipt repair.

Completed hardening: unrelated chapter-index collision preflight before model
calls, frozen-envelope mutation rejection, creation/marker receipt corruption,
later-batch retry preservation, accepted author edits and initial-state mapping.
No provider calls,
credential reads, branch switches or commits were performed by this agent.

Known product limit: budget allocation and planning topology are tested; prose
quality and semantic consistency require Main's separately budgeted live checks.

Integration audit: service call signatures in apps/api/authoring_routes.py match.
Main was notified to preserve stable longform error categories and validate
canonical style list/string shapes before using them. Canonical blueprint style
sets require_semantic_review=true; planned arc final states do not become current
Character state. Existing unrelated chapter positions fail closed.

Second assignment: implemented shared quality_policy.py, guarded local and
LangGraph direct Draft workflow output, CLI write-scene generation and new
composition prose application. Explicit manual save and verified completed
legacy composition retry remain available. tests/test_quality_policy.py: 5 passed.

Independent audit tests/test_longform_adoption_audit.py initially reproduced
accepted Proposal provenance bypass and missing scene style overrides (2 fail,
1 manual-save pass). Main owns fixes in main.py/authoring_routes.py; these tests
should be rerun after Main's fixes. Existing 85 context/proposal/review/composition
tests passed before shared quality changes. No live model calls by this agent.

After Main fixes, targeted audit + quality suites passed together: 8 passed.
Accepted provenance no longer bypasses opt-in adoption and effective scene style
now reaches semantic review. Ruff across planner, quality, workflow, CLI,
composition and all owned tests passed. Main retains full-suite/live/UI acceptance.

Live-output follow-up: after Main's official provider attempt failed structural
validation, strengthened prompt with explicit cross-field invariants and full
prior clue placements. Added static-whitelisted LongformPlanError.reason_code
for safe diagnostics (Main owns API serialization). No repair/retry or paid call
was added. Planning tests now 38 passed; schema and canon gates unchanged.

Explicit revision assignment complete: LongformRevisionRequest and
revise_longform generate a new unapplied alternative with exact source lineage,
preserved frozen scope/request, current canon revalidation, all normal validators
and source/parent/canon race rejection. Applied and partial-application sources
reject before any call. Added optional review_id and first-application callback
hook; fully verified completion retries skip the callback for receipt recovery.
Planning tests now 44 passed. Main owns routes/semantic-review enforcement and
Front owns controls; no live calls by this agent.

Typed baseline extension coordinated with acceptance agent: optional
EntityPlan.initial_state has Character life/condition/location and Item
location/owner slots only. Local ref kinds validate; apply maps explicit
nonempty values to graph initial_state. No defaults or new inferred canon.
Legacy serialization omits absent/null optional baseline, preserving prior
receipt hashes and event properties. Planning tests now 57 passed, including
old-body canonical hash and JSON-reload idempotent retry.

Targeted revision mode added: mode full remains backward-compatible default;
targeted response contains 1–40 exact before/after string-leaf changes from a
server allowlist. Machine fields, references, initial-state slots, budgets,
request/envelope and structural operations are excluded. The source schema and
full payload are provided; only chosen leaves change in a deep copy, followed
by full existing validation and race checks. Planner tests now 75 passed,
including traversal/ID/duplicate/before-mismatch failures, untouched-field
equality, source race and expansion parent/budget preservation. No paid calls.
