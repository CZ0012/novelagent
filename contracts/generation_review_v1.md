# Generation Review Contract v1

## Purpose and boundary

`generation_review_v1` is an explicit, model-assisted continuity and style review
of one exact saved Draft or Proposal version. It is a noncanon assessment, never
a graph patch, CandidateFact, author decision, or permission to overwrite prose.
The original deterministic continuity endpoint remains a separate, unpaid check.
No review can guarantee that a long novel has no contradiction or literary flaw.

The backend resolves the target from the owning project store after permission
checks. Client-supplied text, canon snapshots, target language and version cannot
substitute for the saved target. Requesting semantic review requires at least
`read_generate`; the configured continuity task is resolved and frozen once.
There is no automatic fallback model, paid retry, or implicit review call during
generation. The service can return `inconclusive` with deterministic banned-phrase
findings when no semantic provider is configured.

## Inputs and immutable evidence

`GenerationReviewTarget` contains `project_id`, `target_type` (`draft` or
`proposal`), `target_id`, positive `target_version`, exact `text`, immutable
`output_language`, optional exact `scene_id`, and `purpose` (`scene` by default,
or explicit `plan`). A versioned Proposal must be
resolved to that version's body; a Draft must never be replaced by latest.

`build_canon_snapshot` reads CANON nodes and relationships only. Ownership is
verified for the project, scene, every node and both relation endpoints. It never
reads Sources or Drafts implicitly. Natural names, aliases, secret descriptions,
world rules, foreshadowing and temporal relation properties remain visible.
Dangling/cross-scope endpoint content is excluded and coverage becomes incomplete.

The snapshot stores immutable serialized `facts` (`id`, `kind`, `text`), a full
project canonical content `fingerprint`, `scope`, `complete`, `missing_context`,
`total_facts`, and `omitted_unrelated_facts`. The fingerprint includes sorted
CANON IDs, types, statuses, properties and relation endpoints, including invalid
scoped relation evidence as a hash input. It excludes EventLog entries and
volatile creation/update timestamps. A canon change anywhere in the project
invalidates prior reports conservatively.

With no scene, `scope = project`: all project evidence is eligible. For a scene,
`scope = scene`: selection starts from the scene, its declared references and
natural names/aliases found in the exact target. It follows bounded narrative
relationships, the exact parent, global WorldRules/Secrets/StyleProfiles, and
relevant seed/payoff links, including distant setup metadata. Project hierarchy
must not expand every sibling chapter into the scene prompt.

Default limits are 256 facts and 60,000 serialized evidence characters. Dropping
any selected relevant fact marks `complete = false`. Intentionally omitted
unrelated project facts are counted separately. A scene-scoped pass means only
that the selected scene evidence was reviewed; it never clears the whole book.
An incomplete project-wide scan cannot be presented as a whole-book pass.
Unknown implicit references or ambiguous natural-language chronology still
require an inconclusive model judgment. This bounded retrieval is not proof of
exhaustive semantic recall.

Style rubric text comes from an explicitly accepted project blueprint, plus the
frozen selected preset supplied by the backend. The service does not decide
blueprint acceptance. Rubric and preset are data, not executable instructions;
they cannot override canon, language or review permissions. Style remains a soft
criterion, while explicit author banned phrases receive deterministic exact
substring checks. Automatic stylistic quality remains model-dependent.

## Report

Required report fields:

- `contract_version`: `generation_review_v1`
- `id`, `project_id`, `target_type`, `target_id`, `target_version`, `scene_id`, `purpose`
- `output_language`, `created_at`
- `target_text_sha256`, `canon_fingerprint`, `canon_evidence_fingerprint`,
  `style_fingerprint`
- `status`: `pass`, `needs_revision`, `blocked`, or `inconclusive`
- `summary`, `issues`, `dimensions_checked`, `coverage`
- optional nonsecret `model_execution`, representing the actual frozen task

Dimensions are `knowledge_boundary`, `timeline`, `location_state`,
`relationship_state`, `world_rule`, `foreshadowing`, `causality`, `pov`, and
`style_constraint`. Machine identifiers remain stable; human-readable findings
follow the saved target language and exact quotes retain their source language.

Each issue contains `id`, `dimension`, stable severity (`low`, `medium`, `high`,
`critical`), `description`, `suggestion`, and bounded `evidence`. Each evidence
item has `kind` (`target`, `canon`, `style`), exact supplied `ref`, and a nonempty
verbatim `quote` of at most 500 characters. Scene-purpose issues must cite the exact target
and either a supplied scoped canon record or, for style, a supplied rubric/preset
reference. Every quote is checked as an exact substring of that source. Unknown
IDs, another target ID, invented quotes, missing grounding, duplicate dimensions
or issue IDs, and unsupported fields invalidate the entire model judgment.

Provider output is strict bounded JSON. Invalid JSON, Markdown wrappers,
incomplete/unknown dimensions, failures and missing context cannot produce pass.
There is no permissive repair or paid retry. Raw provider errors are replaced
with stable safe limitation codes; endpoints, credentials and parser bodies must
not enter reports. Valid grounded issues may still be preserved when coverage
is incomplete, but the report status remains `inconclusive`.

`coverage` records `method` (`semantic_model` or `deterministic_only`),
`canon_complete`, `target_complete`, `scope`, `omitted_unrelated_facts`,
`missing_context`, and `limitations`. An exact target over 100,000 characters is
`blocked` before provider invocation; no silent target truncation is allowed.
Missing provider or invalid/partial coverage is `inconclusive`. Full coverage
with grounded findings is `needs_revision`; only full declared coverage with no
issues may pass. A model may explicitly return blocked or inconclusive when the
available canon cannot substantiate a decision.

## Freshness and persistence

`review_is_current` compares project, target kind/ID/version/language/scene/purpose,
SHA-256 of the complete target, full canonical fingerprint, exact selected canon
evidence fingerprint, and style fingerprint. Style changes, source evidence
selection changes, or canon changes make the report stale even if the visible
text happens to match. The API should freshly resolve these inputs on read or
before presenting a report as current.

Reports may be saved to a dedicated local review store and survive restart.
They must remain separate from Graph Store, EventLog, CandidateFact state and
author review decisions. Persistence does not promote findings to canon or grant
automatic adoption. Editing, accepting, adopting or regenerating a Proposal must
not silently transfer a pass from a different target version.

## Acceptance evidence

Offline tests replay natural Chinese positive/negative judgments and verify
canonical names, aliases, temporal properties, late-scene distant setup retrieval,
project isolation, bounded coverage, exact quotes, freshness and no writes.
Replayed judgments test protocol and grounding, not a real model's ability to
recognize semantic contradictions. Real-model performance requires a separately
authorized, independently annotated corpus with false-positive and false-negative
measurements; do not infer that quality from fake-provider tests.

## Plan-purpose internal consistency review

The backend may set `purpose = plan` only after parsing an exact stored Proposal
as a valid `longform_plan_v1` blueprint or expansion. A client cannot gain this
mode by declaring an arbitrary target body a plan. The pure service requires a
Proposal target with no single Scene and an explicitly matching plan snapshot.
Draft and scene-purpose review keep their original evidence requirements.

`build_canon_snapshot(..., purpose="plan")` returns `scope = plan`. It keeps all
scoped story/entity/world-rule/style/secret/foreshadowing canon, relationships
between selected entities, relevant temporal-boundary Scene metadata, and up to
twelve recent narrative Chapter/Scene outcomes. An explicitly mentioned older
outcome may also be selected. Unrelated chapter/scene hierarchy is omitted and
counted, preserving the same full-project canonical fingerprint. Truncating any
selected evidence still makes coverage incomplete and prevents pass.

A new novel is expected to have no existing story canon. In explicit plan scope,
that absence alone does not create `insufficient_story_canon`: the model reviews
the proposed world's own consistency. Proposed rules/entities/style remain draft
data, never canonical authority. Existing canon, when supplied, stays authoritative.

A nonstyle internal-plan contradiction may be grounded by at least two DISTINCT
exact target quotes from the same exact Proposal ID, instead of target-plus-canon
citations. Both quotes must occur verbatim in the saved body; a single quote,
duplicate quote, fabricated quotation, or different target ID invalidates the
judgment. Target-plus-canon remains supported. Style issues continue to require
the supplied rubric/preset evidence. This evidence exception never applies to a
scene-purpose report.

Deterministic banned-phrase scanning is limited to scene prose. A plan JSON body
may legitimately contain prohibited phrases in `banned_patterns`, style
definitions, rubrics or negative examples; those mentions are not prose violations.
Plan review keeps style sources for consistency diagnostics but never creates
literal banned-phrase findings merely from those definition strings.

The review prompt explicitly crosschecks world rules against causal summaries,
operating limits, energy creation/storage/transfer, prerequisites, exceptions and
costs. It reconciles handover/revelation timing across volume summaries,
character-arc turns, causal links, clue setup/payoff, and every mystery's cause,
resolution, actor and cost. Checking JSON structure alone does not establish
these semantic properties. Model mistakes remain possible.

Coverage records `scope = plan`, `purpose = plan`, selected evidence counts and
omissions. A passing plan report means planned-draft consistency within those
inputs; it does not certify scene facts, a completed manuscript, exhaustive
historical recall or human canon approval. Human accept and explicit apply remain
separate. Plan adoption may require a fresh passing report on the accepted exact
Proposal version; any content/version, purpose, canon, evidence or style change
invalidates it under the standard freshness rules.
