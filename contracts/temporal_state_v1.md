# Temporal State Contract v1

## Boundary

`temporal_state_v1` is an additive reviewed state-memory path. It uses existing
CandidateFact review and Event graph nodes. It introduces no automatic canon
write, no new graph labels, and no separate state database. Local JSON/memory is
supported first. Neo4j append-state commits fail explicitly before mutation.

## Typed slots and initial state

- Character `life_status`: `alive` or `dead`.
- Character `physical_state`: `healthy`, `injured`, or `healing`.
- Character or Item `location_id`: an existing same-project Location ID.
- Item `owner_id`: an existing same-project Character/Organization ID, or null
  meaning explicitly unowned. Missing owner differs from known unowned.

Explicit author-reviewed `GraphNode.properties.initial_state` supplies optional
baselines. No descriptive arc/current_status, draft summary, absent slot or
default alive/healthy/owner is converted to a baseline. Unknown stays unknown.
Accepted blueprint initial-state local IDs must be resolved and type-checked to
stable graph IDs before that explicit human apply writes these baselines.

## Candidate patch

`ProposedGraphPatch.operation = append_state`, target is the existing subject ID,
and properties strictly follow `TemporalStatePatch`:

- `contract_version = temporal_state_v1`
- one `field` from the typed registry and matching scalar `value`
- `valid_from_scene`, exactly the candidate's source Scene
- `source_text_sha256`, hash of the complete exact saved source Draft
- `expected_slot_fingerprint`, hash of the subject+field baseline and complete
  reviewed assertion history captured during generation/revalidation
- additive `action`: `assert` by default, or explicit author-requested `correct`
- `supersedes_assertion_id`: required only for a correction, otherwise absent/null

Graph references are canonical and project-scoped, including subject, source
Scene, non-null owner/location and optional candidate object. The required
source Draft, exact span/quote, reviewer decision, rationale and provenance are
retained through ordinary CandidateFact review. Final review checks source
hash/span freshness. A changed slot is a conflict, not permission to silently
overwrite a newer review. Different fields are independent slots.

## Append and persistence

Accepted/edited candidates append an immutable Event node with deterministic ID
`state_<candidate_id>` and event ID `evt_state_<candidate_id>`. The Event records
reserved `event_kind = temporal_state_assertion_v1`, scoped subject/field/value,
effective Scene, source Draft ID/hash/span, candidate ID and original expected
slot fingerprint, plus existing graph reviewer/timestamp/rationale metadata.

The same graph mutation guard owns slot comparison, scene-slot uniqueness and
publication. A different assertion for an already occupied subject+field+Scene
is rejected. Exact repeats require matching stored assertion content and commit
evidence, returning the original receipt without duplicate nodes/events.

Memory commits stage Event and commit evidence together. Configured JSON graphs
persist that complete staged graph by the existing atomic-replace file path
before swapping live state. Synchronous persistence failure leaves the graph and
event log unchanged; ReviewService compensates its unchanged decision back to
pending. This does not claim a shared SQLite/JSON transaction, multi-process
source lock, power-loss atomicity or distributed linearizability.

Generic CandidateFact create_node, human seed and generic update paths cannot
create or mutate reserved temporal assertion records. A rejection/defer appends
no temporal assertion. Entity properties and raw LOCATED_AT/OWNED_BY edges are
not overwritten or auto-closed by this path.

Generic CandidateFact update_node also cannot reset `initial_state`: a baseline
must come from explicit author seed/metadata action or accepted blueprint apply.
Such an explicit human baseline correction changes the state-slot fingerprint
and invalidates pending assertions; automated extraction cannot disguise a
retrospective reset as an ordinary state fact.

## As-of projection

`resolve_temporal_state(graph, project_id, subject_id, scene_id, fields=None,
at_scene_start=False)` returns project/subject/Scene, the entry/through flag,
typed states and `complete`. Each state has field, status (`resolved`, `unknown`,
`ambiguous`), optional scalar value, assertion refs and a safe reason code.

The resolver takes an immutable read snapshot. For each slot it selects reviewed
assertions whose effective Scene is at or before the requested Scene by reliable
world precedence, then chooses the unique latest assertion under
that partial order. It never sorts by creation time, acceptance order, title,
numeric-looking ID, prose date or lexical node ID. Out-of-order writing and
acceptance therefore preserve earlier and later projections.

At entry, assertions from the queried Scene itself are excluded, so a death or
injury during that Scene cannot become its opening state. Through-scene includes
them. Initial baselines apply before the first reachable assertion. Missing
baseline is unknown. Cycles, missing referenced Scenes, invalid typed records or
incomparable chronology return ambiguous. Incomparable branch assertions are
never selected arbitrarily. A later unambiguous assertion may resolve competing
earlier states after an explicit convergence; missing branch order remains a gap.

Location and ownership are single-valued slots: at a resolved Scene there is one
scalar value with provenance, while earlier values remain immutable history.
Context/review integrations must consume these projections and surface unknown
or ambiguous tracked slots instead of falling back to timeless entity text or
raw exclusive relationships. A pass does not prove every natural-language claim
was extracted or that world-rule semantics are infallible.

## Natural extraction and corrections

Natural extraction maps compatible single typed properties, plus LOCATED_AT and
OWNED_BY changes, into server-built append_state patches. The model cannot choose
source hashes, slot fingerprints, reviewer decisions or retraction commands.
Unsupported/free-form node and existing-relation changes remain clearly labeled
observation-only no-op candidates, preserving their proposed values for review.

Accepted assertions cannot be deleted or modified. A new reviewed assertion in a
later Scene represents a later narrative transition (death/revival, injury/heal,
move/transfer), preserving earlier truth. An ordinary assertion still cannot
replace a state at an occupied same-scene slot.

## Explicit historical value correction

An author may explicitly propose a correction of a mistaken value at the SAME
effective Scene. This revises the accepted record of what happened; it is not a
later narrative transition such as resurrection or healing. The correction
appends a new immutable Event with `action = correct` and
`supersedes_assertion_id` pointing to the currently active assertion in the same
project, subject, field and effective Scene. The old Event and exact commit
receipt remain unchanged and available in history. Defaults/correction keys are
not retroactively written into old assert records, preserving their receipt
hashes and replay compatibility.

`TemporalStateCorrectionRequest` contains `assertion_id`, `source_draft_id`,
`expected_draft_version`, `expected_source_sha256`, exact `source_span`, typed
corrected `value`, `expected_slot_fingerprint`, and explicit author `rationale`.
The saved source Draft must belong to the same project and effective Scene, with
matching current project language, version, complete text hash and exact quoted
slice. The same Draft ID may have been revised; its NEW complete hash is required.
A different-scene source cannot masquerade as a correction of old story time.

`propose_state_correction` returns one unpersisted pending CandidateFact, with old
and corrected values in graph evidence, exact revised Draft evidence and explicit
author-instruction evidence. It never invokes a model or writes canon. The API
requires `read_generate`, may submit the preview as pending, and standard human
`full` accept/edit-accept performs the final append. Source freshness, full-slot
CAS and active supersedes-target validation run again at review and under the
graph mutation guard. An ordinary review edit cannot redirect the correction to
another subject, field, effective Scene or superseded target. No-op equal-value
corrections are rejected. Concurrent competing corrections have one winner;
the losing unchanged Candidate returns to pending with no graph/event delta.

Natural extraction never chooses action=correct. It cannot set correction
metadata or supersedes references through its structured model response. A
correction requires a distinct explicit author action and normal review.

Projection excludes superseded records globally as corrected canonical history,
then performs normal scene-time resolution on active revision leaves. Chains
must be same-slot, same-scene, acyclic and unambiguous; missing/cross-slot/cyclic
or branching correction links fail closed. `get_state_assertions(active_only=True)`
returns validated active leaves. Scene/plan context must not present superseded
raw assertions as current truth. Full canonical and slot fingerprints still
include the complete immutable audit history.

`temporal_state_history` returns bounded complete assertion records, exact source
evidence and an active flag, plus per-slot full fingerprint, total count and
truncation flag. It is read-only. It must be exposed only with project read
permission. The product distinguishes correcting a recorded value from deleting
an assertion or retracting it to unknown: arbitrary withdrawal/removal remains a
separate deferred author-only operation, never an automatic model action.


## Narrative slots are not world-time proof

World chronology consumes explicit author-created CANON NEXT_SCENE relations and
all eligible accepted interval proofs, including reliable pairs not materialized
as graph edges. Explicit manual relations remain authoritative
without requiring a parseable prose date. Directory ordering, `previous_scene_id`
and planning-only CAUSES are not chronology inputs. Concurrent and out-of-order
narration must not inherit later events merely because it appears later in a book.

Automatic application of long-form expansions, book bundles and composition uses
one conservative deterministic chronology policy. Only explicit bounded story-time
intervals in the accepted Scene.timeline_position may prove precedence. The
supported grammar is deliberately limited: anchored day-and-clock ranges with an
explicit range separator (supported numeric/Chinese day forms or English Day),
and ISO clock ranges with both dates written explicitly. Bare whole-day anchors
use a conservative complete-day envelope. A lone clock, partially parsed segment,
ambiguous Chinese numeral, mixed relative/ISO anchor or mixed ISO timezone style
is unknown; no NLP, fuzzy date interpretation, chapter-index date inference or
inferred instant duration. Different anchor systems are incomparable. Ambiguous multi-part
ranges are unknown unless the complete range has a safely determined envelope.
Only a provably completed earlier interval may precede the target opening; overlap
and uncertain shared boundaries stay incomparable.

New derived edges carry `properties.auto_chronology_v1` with
`origin: accepted_timeline_position`, `source_timeline_sha256` and
`target_timeline_sha256` (hashes of the exact full timeline strings). A proof is usable only while its same-project
endpoints, accepted application/source provenance and both timeline fingerprints
still match. Metadata tampering or timeline edits invalidate the old stored proof instead of
silently recertifying or mutating it. A new approved canonical time update can
supply fresh interval authority for the internal read order, as defined below. Missing proof is not
permission to fall back to narrative adjacency.

Historical automatically generated relations are recognized narrowly from their
actual deterministic IDs, matching source/application binding and original graph
creation evidence, never from an ID prefix alone. Their original endpoint timeline
snapshots must support the same conservative precedence proof and still match the
current endpoints. Legacy composition edges without such timing evidence do not
become authoritative manual edges. Explicit unrelated manual edges remain intact.
Existing graph relations/events are not deleted, reordered or rewritten during
reads; stale/unprovable automatic evidence is excluded from the reliable world
view and unresolved tracked state remains unknown/ambiguous.

State and knowledge-boundary consumers share this reliability filter. Scene critics
must not mistake narrative predecessors for the only possible world predecessors.
This is still scene-grained state: entry excludes the target Scene's own changes,
and through-scene includes them. It does not implement within-scene event clocks,
reader knowledge inference, automatic canon repair or automatic history migration.


Persisted automatic links may stay sparse (at most one selected predecessor per
new link calculation), but the internal read order includes ALL reliable strict
interval-before pairs plus authoritative manual relations and valid stored proofs.
Ordinary fork/join therefore resolves facts from both completed parallel branches;
an implementation must not discard a proven earlier branch merely to reduce
persisted edge count. Equal endpoints, overlapping intervals themselves and
unparsed time remain incomparable. A newly accepted earlier-in-story Scene can
precede an existing later Scene across application batches.

The internal order is snapshot-local, may use bounded indexes/bitsets and is not
stored as a dense canon graph or appended to model payloads. The shared
`reliable_scene_order(snapshot, project_id)` supplies `before(source, target)`
and cycle/invalid-order information to state and knowledge consumers. Every interval-derived pair needs accepted Scene creation/source evidence or a
subsequent approved canonical update containing the exact current full timeline.
An update must have matching scoped node/event provenance, reviewer, rationale
and source; a direct property mutation without such evidence stays unknown.
Later title-only changes must not erase an already approved time update. Old
stored-edge fingerprints still remain stale after a time edit: deriving read
order from a NEW audited time fact does not rewrite those relations or their
receipts. Rebuilding from unchanged invalid evidence is forbidden. Manual
explicit author relations also remain authoritative. Snapshot-local caching
must never leak across subsequent mutable graph changes.

Scene critics receive the same trustworthy projection: stale/unproven stored
automatic NEXT_SCENE cannot appear as authoritative prompt facts or citation
evidence. Raw canonical history remains fingerprinted and readable through
audits. The same exclusion applies to the default project model-evidence view used by
long-form planning. It changes evidence only where unreliable automatic relations
were actually present; unapplied Project-only PLAN inputs remain unchanged.

Reviewed project-structure import is another automatic application path. It keeps
narrative navigation separate from world chronology; its scene interval evidence
requires exact structure-Proposal/version/source and graph creation binding.
A custom source_ref alone is not manual chronology authority for imported auto
links. Historical source-structure receipts are not silently migrated.
