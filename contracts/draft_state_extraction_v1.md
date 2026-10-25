# Draft State Extraction Contract v1

## Purpose

`draft_state_extraction_v1` adds explicit natural-prose extraction from one exact
saved scene Draft. It produces unpersisted `candidate_fact_v1` previews only.
The caller may save them as a structured `fact_draft` Proposal; explicit promotion
then creates pending candidates under the existing review contract. There are no
Graph, Candidate Store, Draft Store or EventLog writes in the extraction service.

The marker extractor remains a deterministic utility. Its tests do not prove
natural-language extraction quality. Neither extractor can declare canon.

## Service and authorization

`extract_natural_draft_state(graph, project_id, source_draft, provider, model,
output_language)` returns `list[CandidateFact]`. Arguments are keyword-only.
The API resolves `source_draft` from the exact same-project stored ID/version and
requires at least `read_generate` before resolving the configured `extraction`
connection. No style preset changes extraction behavior. No provider/model
fallback, remote tools, automatic paid retry or silent truncation is permitted.

The source Draft project, source Scene and current project language must match.
A Draft without a confirmed matching language is rejected before the provider.
The source is deep-copied before invocation. Empty prose and scenes exceeding
32,000 Unicode characters are rejected before invocation; the caller must use a
bounded scene, not claim that a clipped chapter was fully scanned.

Only the immutable scene-scoped canonical snapshot is provided alongside prose.
Natural names/aliases in the prose participate in retrieval. Incomplete scoped
canon fails before invocation. Sources, other Drafts, private project settings
and cross-project graph content are never implicit inputs.

## Strict provider output

The provider returns exactly `{"facts": [...]}`, with at most 16 items. Each item:

- `fact_type`: a supported CandidateFact narrative state type
- existing `subject_id`, `relation`, optional existing `object_id`, optional `value`
- `operation`: `update_node`, `create_relation`, `update_relation`, or `none`
- `target`, approved scalar `properties`
- `source_span`: `start_offset`, exclusive `end_offset`, exact nonempty `quote`
- `temporal_scope`: exact source `scene_id` and its `timeline_position` or null
- `confidence` in `[0,1]`
- `certainty`: `asserted`, `inferred`, or `conflicting`
- bounded generated `rationale` in the project output language

Offsets count Python Unicode code points, not UTF-16 code units. The exact quote
must equal the source slice and contain at most 500 characters. Repeated quotes
retain the supplied specific occurrence; validation never relocates them by
search or repairs offsets. Evidence is required for every preview, including
inferences. Speculation, dreams, false assertions and negations are not automatic
state changes. The model must mark uncertainty rather than invent corroboration.

The MVP does not create new entities. Unknown IDs, invalid canonical node types,
unsupported edge labels and metadata/structure edits fail the whole output.
Node updates use type-specific state-property allowlists; relation updates use
a bounded narrative/temporal allowlist. Project, Chapter and StyleProfile cannot
be relation endpoints in this extraction path. Common relationship types have
explicit endpoint-type rules, including Character-to-Secret `KNOWS_SECRET`,
Foreshadowing-to-Scene seed/payoff, and Event/Scene causal links. `update_relation`
must match the existing relation ID, type and both endpoints. New relation targets
use the existing `subject -> RELATION -> object` convention.

Historical mutation is deliberately restricted in this milestone. Validated
`update_node` and `update_relation` requests are converted to observation-only
CandidateFacts: `proposed_graph_patch.operation = none`, target is the canonical
subject, and properties are empty. The localized rationale explicitly says no
canon state changes; `value` and evidence metadata preserve the proposed state,
original operation and original target for human inspection. Accepting one may
record a review audit event but cannot update the node or existing relationship.
This does not implement historical character/location/relationship state tracking.

SG-030 adds the narrow `temporal_state_v1` exception: compatible single typed
Character life_status/physical_state, Character/Item location_id and Item owner_id
changes become reviewed append_state assertions with server-derived source hash
and slot fingerprint. LOCATED_AT/OWNED_BY transitions use those single-valued
state slots rather than creating overlapping raw relationships. Other/free-form
node and existing-relation updates retain the observation-only behavior above.
The typed path preserves explicit initial baselines and entry/through-scene
history; it does not imply general historical tracking for arbitrary properties.

Only `create_relation` can become a new graph relationship after human review.
Its server-built properties always include `valid_from_scene = source_scene_id`,
the actual temporal key recognized by Graph Store. A conflicting supplied
boundary fails. Invented `valid_from`/`valid_to`, `valid_until_scene`, exact
`scene_id`, and exact `timeline_position` are not allowed in these relation
patches. The current graph uses `NEXT_SCENE` reachability to exclude this relation
from earlier scenes and include it from the source scene onward. Unknown order
fails closed; the API must not imply it inferred chronology from prose dates.
Negated knowledge cannot create a `KNOWS_SECRET` relation with `known = false`,
because current knowledge queries interpret the edge itself as knowledge.

Properties cannot carry nested patches, project IDs, credentials, node types,
review metadata or nonfinite values. The model cannot supply candidate IDs,
canon/review statuses, provenance fields or reviewer decisions. Strict extra-field
validation, fact count and quote checks reject the entire batch; no valid prefix
is saved or returned when any item fails. Malformed JSON or Markdown wrappers are
not repaired. Empty facts is an explicit valid no-supported-change result.

## Candidate construction and temporal provenance

The server fixes project, source scene, source Draft and patch `source_ref`.
Stable candidate IDs hash exact Draft ID/version/text and the validated assertion.
Identical repeated assertions deduplicate. `asserted` maps to `DRAFT_FACT`,
`inferred` to `HYPOTHESIS`, and `conflicting` to `CONFLICT`; all review decisions
remain pending, without reviewer or reviewed timestamp.

Draft evidence preserves the exact quote and a bounded metadata note with Draft
version, complete text SHA-256, full canonical fingerprint and source temporal
scope. A graph-fact reference records the canonical subject identity. Temporal
scope describes where the claim was narrated; it does not prove that it applies
forever or allow an earlier scene to silently overwrite later canon. The author
must review any temporal state transition using the existing canon review flow.

Every candidate passes the same `graph.validate_candidate_scope` ownership gate
used by `ReviewService`, without submitting it. Canon is fingerprinted again
after the provider; a changed graph rejects the operation. Promotion and commit
must revalidate scope and evidence under `candidate_fact_v1`; extraction-time
validation never replaces final review checks.

`validate_natural_candidate_source(candidate, draft_store=...)` re-resolves the
exact stored Draft, verifies the complete text hash, stored version, source
project/scene, temporal source scene and exact source span/quote. It also requires
the forced temporal boundary for new relations and rejects historical update
patches. ReviewService runs it on submission, accept/edit-accept and immediately
before graph commit after persisting the review decision. A changed source at
that final synchronous precondition compensates the candidate back to pending,
without a graph event or mutation. Natural candidates without a verifiable
DraftStore or extraction snapshot fail closed. Legacy explicit-marker candidates
remain compatible; rejecting or deferring a stale candidate remains possible.

API and CLI runtime construction pass their shared DraftStore to ReviewService;
the scene workflow uses that same configured service. These checks are bounded
in-process preconditions, not a cross-SQLite/Graph transaction or a guarantee
against arbitrary multi-process writers changing the source at the exact commit
boundary. Temporal versioned state and stronger durable commit invariants are
tracked in `.codex/coordination/sg029-temporal-followup.md`.

The structured Proposal body may use
`{"source_draft_id":"...","candidate_previews":[...]}`. This is compatible with
the existing strict fact-draft promotion path. Proposal generation is neither
candidate submission nor canon adoption. Nonsecret extraction model execution
provenance belongs to the enclosing Proposal and must name the actual task.

## Failure and evidence limits

Safe service errors are `natural_state_provider_failed`,
`natural_state_invalid_output`, and `natural_state_canon_changed`, plus bounded
preflight contract errors. External exception bodies, endpoint addresses,
credentials, parser text and private manuscript fragments must not enter errors.

Offline fake-provider tests verify bounded inputs, exact Chinese spans, emoji
codepoint offsets, temporal scope, inference/conflict statuses, node/edge scope,
atomic rejection, stable IDs, no writes and no retry. These tests do not establish
real-model extraction precision/recall. Any real-model claim requires separate
authorized, independently annotated acceptance evidence.
