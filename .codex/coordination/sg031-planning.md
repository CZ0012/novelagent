# SG-031 autonomous noncanon planning handoff

Owned models/planning_run.py, stores/planning_run_store.py,
services/planning_run.py, services/book_bundle.py and planning_run_v1 contract.
Main owns routes/settings/docs; Front owns run controls and previews.

Default complete target: 5 volumes, 100 chapters, 200 scenes, 500000 planned
characters; 21 generate/review steps plus final ledger review, minimum 43 calls.
No intermediate human application, canon, Draft, Candidate or Source writes.
Same-DB Proposal/checkpoint CAS transactions, durable call reservations and
persistent worker-token ownership; uncertain interrupted calls need explicit
paid retry. Exact accepted whole-book manifest stages all graph/events once,
then derives recoverable receipts without mutating child Proposal statuses.

Checks: own tests/test_planning_run.py 12 passed including whole500k branch,
stop/budget/uncertainty, default review-only recovery, explicit chosen-step
restart, seed copy/no paid generation and stale seed failure. Independent Check
tests/test_planning_run_audit.py reports 17 passed including lost cross-process
claim, checkpoint rollback, live owner recovery and four receipt corruptions.
Ruff on all owned new files passed.

Optional seed fields and restart resume fields were sent to Main and Front.
Current configured task connection is frozen; a changed connection pauses.
Canon/source changes require explicit reconciliation/new branch, never silent
fingerprint replacement. All previous artifacts remain inspectable.

Targeted revision now receives exact current_values, permits exact complete leaf
or exact unique substring replacement (overlap-aware), skips validated no-ops
when another real change exists and reports skipped_noop_paths. All-no-op,
duplicate paths, ambiguous spans and unknown fields still reject. No paid calls,
credential inspection or private prose was performed/copied by this agent.
