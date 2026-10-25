# SG-029 temporal state follow-up

Status: SG-030 implements four typed append-only state slots; remaining items
below still gate broader historical-memory claims. This file is engineering coordination only; no author prose,
runtime state or credentials belong here.

## Current enforced boundary

- Natural extraction returns pending CandidateFact previews, never canon writes.
- New relation candidates force the existing `valid_from_scene` key to the exact
  source Scene. Graph reads use NEXT_SCENE reachability; unknown ordering is not
  guessed from display names or prose dates.
- SG-030 compatible life_status/physical_state/location_id/owner_id changes use
  reviewed append_state Event assertions. Exclusive LOCATED_AT/OWNED_BY changes
  use the same single-value projections. Unsupported/free-form node or existing
  relation updates remain explicit operation-none observations.
- Full source Draft text hashes, versions, exact spans and project/scene ownership
  are checked during promotion, submission and final synchronous accept/edit
  preconditions. Missing source access fails closed for natural candidates.

## Remaining work and acceptance requirements

1. temporal_state_v1 now covers typed slots, source-scene validity, out-of-order
   acceptance, conservative partial-order projection and explicit author-reviewed
   same-scene value corrections through immutable supersedes chains. Verify the
   API/UI correction flow end-to-end. Withdrawing an assertion to unknown (rather
   than correcting its typed value) remains a separate deferred retraction action.
2. Extend the narrow Character/Item registry to additional Location/Organization
   states only through typed versioned contracts, never generic timeless overwrites.
3. Keep old raw LOCATED_AT/OWNED_BY data visibly distinct from new projected state;
   define an explicit reviewed migration instead of silently guessing baselines.
4. Preserve changed relationship values historically; no in-place overwrite may
   erase earlier knowledge, loyalty or relationship status. Define knowledge
   acquisition, false beliefs, forgetting and concealment separately.
5. Test early/source/later scene projections, out-of-order acceptance, ambiguous
   chronology, scene reorder, rejected changes and repeated/lost-response accepts.
6. Bind final source freshness and graph/candidate/event persistence durably when
   multiple writers/processes are supported. Current synchronous preconditions
   and compensation do not claim a cross-database atomic transaction.
7. Update graph/candidate/review/context/report contracts and every affected
   development role instruction together. Keep human review and source provenance
   authoritative throughout migration.
8. Validate natural-language continuity precision/recall independently on annotated
   Chinese fixtures. Mocked provider protocol tests cannot establish semantic
   understanding or guarantee that a 500,000-character novel has no contradictions.

Main Agent owns prioritization and assignment for this milestone. Keep current UI
and acceptance documentation explicit that observation acceptance does not update
the corresponding canonical state.
