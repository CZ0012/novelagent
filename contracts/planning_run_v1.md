# Whole-book Planning Run Contract v1

`planning_run_v1` independently designs a complete long-form fiction framework
before human canon application. It generates outlines, never 500,000 characters
of manuscript prose. Related contracts: `longform_plan_v1`,
`proposal_artifact_v1`, `generation_review_v1`, `graph_store_v1`, and
`language_policy_v1`.

## Storage and isolation

Content remains in the existing Proposal Store. `planning_runs` and
`planning_reports` tables share its SQLite connection, lock and database.
Proposal output and its exact run checkpoint commit in one SQLite transaction.
Run control stores refs, budgets and nonsecret execution fingerprints, not
credentials, Source contents or Draft prose. No automatic step accepts a
Proposal, writes graph/events, creates Drafts/Candidates, or alters Sources.

The task fixes the project language and full canon content fingerprint at
creation. Every later paid call checks currentness. Proposed earlier plans are
explicitly labelled `proposed_planning_context`; they are not inserted into a
fake canon graph and never grant characters knowledge. Reading prior plans
does not require human acceptance or graph application.

## Routes and request shapes

- `POST /projects/{id}/planning-runs` accepts existing flat BlueprintRequest
  fields plus `batch_size=5` (1–5), `max_calls=80` (1–128), and
  `max_repairs_per_step=2` (0–2). The grid's minimum generation/review call count
  must fit the hard 128-call limit. A deliberately lower initial budget may
  pause partway and be explicitly increased later.
  Optional paired `seed_blueprint_id,seed_blueprint_version` selects an exact
  same-project, confirmed-language, valid UNAPPLIED `longform_plan_v1` blueprint.
  Its frozen BlueprintRequest must exactly match the supplied base request.
  Copy it transactionally into branch step zero without a generation call;
  preserve original model provenance with an explicit workflow-copy/no-call
  note. The original Proposal is unchanged, and semantic review remains required
  before expansion. Later seed version changes invalidate run currentness and
  first application. Partial application events also forbid seeding.
- `GET /projects/{id}/planning-runs` returns `{runs}`.
- `GET /projects/{id}/planning-runs/{run_id}` returns `{run}`.
- `POST .../{run_id}/stop` accepts `{expected_version}`.
- `POST .../{run_id}/resume` accepts `{expected_version,
  retry_uncertain_call=false,max_calls?,restart_from_step?,revision_instruction?}`. A budget increase is explicit and
  capped at 128; it cannot be below already reserved calls.
  An optional zero-based chosen step restarts planning explicitly. With a
  nonblank instruction (up to 12,000 characters) and a current valid saved
  output, perform a targeted repair; without it regenerate the selected step.
  Preserve old Proposals, reset following checkpoints to pending, and clear the
  final report/bundle. Record source refs and an instruction hash in restart
  history. Per-human-request repair counts reset; total reserved calls never
  reset. Accepted/applied bundles cannot be silently superseded.
- `GET .../{run_id}/reviews/{review_id}` returns `{report,current}` for a pinned
  step/final report in that scoped run.
- `POST /projects/{id}/proposals/{bundle_id}/apply/longform-book` accepts
  `{expected_version,reviewer,rationale,review_id?}` after ordinary explicit
  Proposal acceptance. The bundle's persisted per-step and final reviews are
  authoritative inputs; a generic review of manifest IDs alone is insufficient.

Create/resume queue the run; a synchronous worker owned by the API host executes
it in a background thread. GET/polling never starts paid work. Stop blocks all
subsequent calls. An already dispatched call may finish: persist its output,
then pause without another call. Existing human-per-batch APIs remain distinct.

## Run projection

`PlanningRun` contains `id,project_id,version,status,stage,request,output_language,
canon_fingerprint,calls_reserved,max_calls,stop_requested,pause_reason,
pending_call,steps,bundle_proposal_id,final_review_id,execution_fingerprints,
owner_pid,worker_token,seed_blueprint_ref,restart_history,created_at,updated_at`.

Statuses: `queued`, `running`, `paused`, `awaiting_review`, `completed`.
Stages: `blueprint`, `expansion`, `book_review`, `bundle`, `done`.
`awaiting_review`/`done` means the complete bundle is ready for author review;
`completed` means an accepted bundle was explicitly applied. It never means a
full-length manuscript was generated.

Steps are an initial blueprint followed by all ordered batches. Each records
`index,phase,volume_index,chapter_start,chapter_count,status,proposal_ref,
review_id,repairs,revision_instruction`. Statuses: `pending`, `generated`, `needs_revision`, `passed`.
An exact ref is `{id,version,body_sha256}`. Review IDs pin immutable reports.
Pause reasons are stable nonsecret codes, including `stopped`, `call_budget`,
`schema_invalid`, `review_failed`, `repair_limit`, `uncertain_call`,
`canon_changed`, `source_changed`, `connection_changed`, `context_budget`,
and `execution_failed`. Exception/provider bodies never enter these fields.

Every update uses version compare-and-set. A call reservation durably increments
the budget before dispatch and records `id,task,operation,step_index` as
`pending_call`. Generation and continuity use explicit configured task models.
Connection/model/thinking/preset fingerprints freeze on first use; changed
configuration pauses, never silently substitutes a model. Only fingerprints
and existing nonsecret ModelExecution metadata persist.
The winning worker owns a persistent unique token. Reservation and result
checkpoint writes require that token and matching pending-call identity. A
losing claim/CAS must return the winner's state without pausing it, clearing its
reservation or dispatching duplicate work; the in-process active registry alone
is not a cross-process correctness boundary.

Recovery skips known active in-process runs and live foreign-process owners.
Interrupted running checkpoints become paused. A pending call is uncertain:
the external provider may have charged even if its response was lost.
`retry_uncertain_call=true` is required before another paid attempt. There is
no claim of exactly-once external billing and no automatic transport retry.

## Bounded generation and criticism

Each step makes one generation call, then one grounded semantic review. A
grounded `needs_revision`/`blocked` report may trigger at most the requested
number of targeted repair calls, each followed by a fresh review. Repair calls
are counted when reserved, including failed output, not only successful edits.
Schema errors, inconclusive/failed reviews, context overflow or budget limits
pause. Explicit resume may retry an inconclusive review; exhausted repair limits
do not create an unbounded loop. Malformed JSON is not guessed or repaired.
Inconclusive/nonactionable step reports resume at review, not paid blind
rewriting. A failed final report may be explicitly rechecked; actual content
repairs require choosing a responsible step and invalidate dependent outputs.

All generated/repaired payloads pass existing Blueprint/Expansion language,
budget, ID, dependency, entity-reference and clue lifecycle validators. A repair
creates a new Proposal; old outputs remain historical and unaccepted. Later
steps use only passed exact refs. User version changes invalidate currentness;
there is no silent selection of latest content or canon fingerprint relabel.

After all batches pass, a separate final review compares the complete blueprint
and an exact whole-book scene summary/outcome/dependency/clue ledger with every
selected ref. Each full batch was separately reviewed. The final ledger is not
a claim that all fields of all scenes fit in one model context, that a whole
manuscript was reviewed, or that all semantic errors were found. Actual overflow
pauses instead of truncating and declaring pass.

## Branch and bundle Proposals

`outline_draft`/`structured_json` branch bodies use
`schema=longform_branch_plan_v1` and contain `run_id,project_id,output_language,
canon_fingerprint,step_index,phase,blueprint_ref,previous_refs,blueprint,expansion`.
They reuse the strict authored models but are not executable by existing
`apply/longform`. Parent refs mean proposed dependencies, not human approval.

When all checks pass, create one new `longform_book_bundle_v1` Proposal with
`run_id,project_id,output_language,canon_fingerprint,blueprint_ref,
expansion_refs,final_review_id`. It pins the complete exact manifest. Author
acceptance of that bundle explicitly covers all referenced plan content. Child
Proposal statuses are neither forged nor automatically changed.

## Atomic application and recovery

First application requires exact accepted bundle/version, unchanged manifest,
all pinned children and passing fresh per-step/final reports, active project,
matching canon/language, and complete whole-book topology/budgets. IDs and
same-kind entity names cannot collide; existing Chapter positions are protected.

For memory/JSON graphs, stage every whitelisted world/entity/style/chapter/scene
node, relation, provenance event and completion marker in a clone under the
graph guard. Persist the complete graph/event snapshot atomically before
publishing it. No Draft or Source storage participates. Unsupported graph
backends reject. Synchronous persistence failure publishes nothing.

After graph persistence, record `longform_book_application`, `graph_node`,
`graph_relation` and `canon_event` derived refs on the accepted bundle, then mark
the run completed. This is staged recoverable persistence, not cross-database
2PC. A retry verifies the entire accepted delta against durable creation events,
exact manifest hash and current object ownership/endpoints before repairing
receipts. Missing/corrupt evidence fails closed; ID or title equality is not a
receipt. Verified completed retries preserve later author edits and do not
require a fresh paid review after their own application changed canon.

Canon/source changes before application pause or reject; no implicit rebase or
rewrite is supported. Preserve the old branch and require an explicit new
planning/reconciliation decision. A failed quality run remains inspectable;
bounded autonomous planning does not guarantee that a model will produce a
passing book on every request.
