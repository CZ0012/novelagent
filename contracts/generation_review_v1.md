# Generation Review Contract v1

## Applied planning metadata in scene snapshots

An applied long-form Scene retains `longform_blueprint_id` (a Proposal identity),
`longform_scene_id`, `causal_dependencies`, `foreshadowing_seed_ids` and
`foreshadowing_payoff_ids` as exact planning provenance/local identifiers. They
are not Graph Store node references. Scene evidence recognizes this boundary
only when the Scene's derived stable ID and the owning Project's blueprint
identity agree. These properties remain unchanged in storage, evidence and
fingerprints; there is no migration or inferred canon write.

Planning semantics still resolve through scoped CANON `planning_only` CAUSES,
SEEDED_IN and PAID_OFF_IN edges, with the Context Pack's existing plan validation.
Declared local IDs must match the corresponding stable edge sources. Missing,
foreign, mistyped or inconsistent plan links remain incomplete coverage. Actual
chapter, POV, location, previous-scene, style and required-character references,
and unknown custom suffix-ID references, retain fail-closed checks. This narrow
scene-scope handling does not change project/PLAN snapshot selection or hashes.

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
For normal long-form expansion review, the server additionally resolves its
exact accepted/applied scoped parent under the existing parent contract and
builds a deterministic review projection: current saved plan, parent blueprint,
parent ID/version/content hash and frozen whole-volume batch progress. The
original immutable author brief is also included, rather than inferred from
indirect style rubrics or replaced by the current batch request. The
target hash covers this complete projection, so parent changes invalidate the
report. This is explicit server-resolved context, not client-supplied text or
canon promotion. Normal blueprint review and scene/Draft text stay unchanged.

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

Language validation of review human fields alone uses a bounded exact-identifier
filter before the shared heuristic: source IDs, actual structured JSON keys and
fixed schema keys may be removed from a temporary validation copy with identifier
boundaries. Tokens come only from current target/canon/style/registry data and
known schema names (at most 4,000 tokens/80,000 identifier characters and 300,000
source characters). Arbitrary English sentences are never allowlisted as tokens.
For Chinese reports, every cleaned human field must still contain Han text;
known-ID-only fields are not meaningful Chinese. Unknown tokens remain subject
to the normal guard. Original summaries, descriptions, suggestions, citations
and hashes are never rewritten. This exception does not change Draft/writer or
general project-language validation.

Each issue contains `id`, `dimension`, stable severity (`low`, `medium`, `high`,
`critical`), `finding`, `description`, `suggestion`, and bounded `evidence`.
`finding` is `contradiction`, `required_gap`, or `advice`. Missing legacy values
default to `contradiction`, preserving their blocking meaning. A contradiction
requires genuinely incompatible established facts under the same time/scope;
a required gap is a missing prerequisite that prevents checking/executing the
requested scope. Both are blocking regardless of severity. Advice is optional
expansion detail or literary improvement, only `low` or `medium`; severe advice
is invalid provider output, never an automatic pass or a forced repair.

Each evidence
item has `kind` (`target`, `canon`, `style`), exact supplied `ref`, and a nonempty
verbatim `quote` of at most 500 characters. Nonstyle `advice` may cite one exact
target passage: an optional improvement does not assert a conflict between two
established claims. Contradictions and required gaps retain the stricter scoped
canon-or-internal-plan-pair requirement below. Style advice still requires both
the target and an applicable supplied style source. Every quote is checked as an
exact substring of that source. Unknown
IDs, another target ID, invented quotes, missing grounding, duplicate dimensions
or issue IDs, and unsupported fields invalidate the entire model judgment.

### Exact citation registry

Provider inputs additionally expose `evidence_sources`, a bounded map of request-local sequential handles (`E1`, `E2`, ...) to exact `{kind,ref,quote,path}` source segments. The
provider may cite an alternative evidence object containing exactly
`{source_id:"a supplied key"}`. The server resolves this declared form to the
existing canonical `{kind,ref,quote}` before strict model and original-source
validation. Unknown IDs, non-string IDs, or mixed `source_id` plus overrides or
extra metadata invalidate the judgment. Canonical persisted evidence does not
gain a provider-authored quote, alternate source kind or unverified ref.

Compact handles are scoped to one provider invocation. The request also supplies
`evidence_registry_id`, a fresh opaque request-instance token. Any output using
`source_id` MUST echo that exact token as a top-level field. A missing, non-string
or mismatched token invalidates the judgment. If supplied, the token is validated
even when all evidence uses canonical kind/ref/quote. The server removes this
transport field before strict output validation and persistence. Canonical-only
outputs may omit it for compatibility. A fresh request for identical content gets
a fresh token, so stale compact-handle output cannot select another registry.

Lookup remains exact and case-sensitive. Missing characters, unknown IDs,
unregistered old hash IDs and mixed overrides remain invalid; no prefix, edit
distance, token correction or fuzzy repair is permitted. Handles are convenience
selectors, never persisted identities. Identical source records may reuse a
handle; conflicting metadata for one complete source identity fails closed before
provider invocation with `semantic_review_evidence_collision`. No shortened hash
prefix is used to assign handles. This change never replays or recertifies earlier
failed responses/reports. Persisted evidence remains canonical kind/ref/quote;
target/canon/style hashes, versions, coverage and report freshness are unchanged.

Every registered quote is a nonempty substring of the ORIGINAL validation text,
at most 500 characters. For structured JSON string leaves, use the inner
`json.dumps(value,ensure_ascii=False)` representation and verify that encoded
text actually occurs in the original serialized source. Exact raw segments are
available when decoding/encoding cannot yield a source match. No fuzzy quote
repair, paraphrase matching, normalization or invented quotation is performed.
The registry is capped at 2,000 entries and 180,000 serialized characters;
`evidence_registry_coverage` explicitly records omissions. These convenience
aliases do not truncate or replace the full target/canon/style input. Legacy
exact quotes remain supported when a segment is outside the registry. Source
coverage and normal grounding requirements remain unchanged.

For an unambiguous structured plan-purpose input, the wire carries the COMPLETE
decoded `plan_content` ONCE, plus bounded target ID/version/language/purpose
metadata and `target_text_sha256`. It omits the redundant escaped raw text copy.
The original immutable `target.text` stays local and remains the sole hash and
exact-quote validation source; no plan field, source segment, criterion or
finding is removed. The full quote-bearing citation registry is unchanged.
This is not a rewrite, a new source, a canon assertion or a replacement hash.

The optimization requires a JSON object/list with unique keys, finite numbers
and exactly representable string-source segments. Prose, scalar/unparseable
legacy text, duplicate-key/nonfinite data or alternate escaping that cannot be
exactly represented retains raw `target.text` and a null parsed-plan view. No
normalization/fuzzy matching is introduced to make a citation pass. Persisted
evidence always refers to the untouched original target, including its original
escaped quotes and newlines. Both transport shapes preserve coverage and gates.
Registry entries additionally carry bounded deterministic `context` labels when
their saved structure declares them: `volume_index` from volume records,
expansions or arc turns; `chapter_index` from chapter records; and
`character_id` from character arcs. Labels propagate only within their actual
ancestor record. An array position is never converted into a chapter/volume
number: `/volumes/0` may describe declared volume 2, for example.

The prompt requires attribution to those declared indices, not zero-based path
positions; volume-2 evidence cannot substantiate a volume-1 claim. Context stays
server-derived navigation metadata. A provider cannot supply or override it in
the `{source_id}` form. Resolution still emits ONLY canonical kind/ref/quote,
with every original quote, source hash, registry bound and blocking rule intact.
For causal-link records, context also includes declared `from_volume` and
`to_volume`: the `cause` string is labelled with source `volume_index`, while
the `effect` string is labelled with destination `volume_index`. No timing is
inferred from link ID names. The critic must distinguish a cause wrongly placed
in its source volume from a legitimate consequence or climax in the destination
volume; search basis can precede later action and acquisition.

Provider output is strict bounded JSON. Invalid JSON, Markdown wrappers,
incomplete/unknown dimensions, failures and missing context cannot produce pass.
There is no permissive repair or paid retry. Raw provider errors are replaced
with stable safe limitation codes; endpoints, credentials and parser bodies must
not enter reports. Valid grounded issues may still be preserved when coverage
is incomplete, but the report status remains `inconclusive`.

Provider failures additionally distinguish a known response outcome from unknown
transport completion through safe limitations
`semantic_review_provider_outcome_known` or
`semantic_review_provider_outcome_unknown`, alongside the existing
`semantic_review_provider_failed`. HTTP error responses and completed invalid or
length-limited responses are known failures; they are never passing judgments.
Timeouts, connection/partial-read failures and unclassified provider exceptions
are conservatively unknown. No raw exception, response body or reasoning text is
persisted. Completed text rejected by local review JSON/schema validation remains
ordinary `semantic_review_invalid_output`, not an in-flight provider request.

`coverage` records `method` (`semantic_model` or `deterministic_only`),
`canon_complete`, `target_complete`, `scope`, `omitted_unrelated_facts`,
`missing_context`, and `limitations`. An exact target over 100,000 characters is
`blocked` before provider invocation; no silent target truncation is allowed.
Missing provider or invalid/partial coverage is `inconclusive`. Full coverage
with any contradiction/required gap is `needs_revision`, even if a model says
pass or rates the problem low. Under complete adequate coverage, a model's
pass/needs_revision with advice only becomes pass while retaining every
advisory item and an explicit advisory-count/no-blocking-conflict summary.
Explicit blocked/inconclusive is preserved. A model may explicitly return blocked or inconclusive when the
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

A nonstyle internal-plan contradiction or required gap may be grounded by at least two DISTINCT
exact target quotes from the same exact Proposal ID, instead of target-plus-canon
citations. Both quotes must occur verbatim in the exact resolved review text
(saved blueprint body or the explicitly pinned expansion projection); for these blocking claims a single quote,
duplicate quote, fabricated quotation, or different target ID invalidates the
judgment. Target-plus-canon remains supported. Style issues continue to require
the supplied rubric/preset evidence. This evidence exception never applies to a
scene-purpose report.

Deterministic banned-phrase scanning is limited to scene prose. A plan JSON body
may legitimately contain prohibited phrases in `banned_patterns`, style
definitions, rubrics or negative examples; those mentions are not prose violations.
Plan review keeps style sources for consistency diagnostics but never creates
literal banned-phrase findings merely from those definition strings.
The server supplies an explicit `output_language_policy` style source derived
from the frozen target language. A model flagging stray natural-language prose
must cite its target span plus that policy (or another applicable supplied style
source). Missing style citations still invalidate output; the server never
retroactively attaches a policy quote or drops an invalid advisory finding.

The review prompt explicitly crosschecks world rules against causal summaries,
operating limits, energy creation/storage/transfer, prerequisites, exceptions and
costs. It reconciles handover/revelation timing across volume summaries,
character-arc turns, causal links, clue setup/payoff, and every mystery's cause,
resolution, actor and cost. Checking JSON structure alone does not establish
these semantic properties. Model mistakes remain possible.

For a central claimed resolution, the plan critic must assess the claim, available
story evidence and essential inferential bridge under the declared world rules.
Custody, authenticity/integrity, formal acceptance and correlation establish those
properties; they do not alone prove event truth, identity, timing or causation.
Author-dossier truth is not evidence already acquired by the POV/investigators.
An omitted bridge needed to support a central resolution is `required_gap`, not
optional outline brevity or low-severity advice; the alternative is to narrow the
claimed conclusion to its support. Minor procedural details and unstated
real-world legal requirements are not mandatory.

Source identity must remain distinguishable across immutable originals, working
copies, caches and later exports. A derived copy is not independent corroboration;
a sealed original cannot silently be overwritten, disappear or become a different
source. Distinguish genuinely new information from re-exported content, and event
time from observation/report/upload/export timestamps. Explicit nonlinear
narration is allowed; no guessed chronology or invented proof bridge may repair
an inconsistency. These are model-review requirements, not a deterministic proof
checker or evidence that the retained independent acceptance failure is solved.

The prompt distinguishes a planning dossier from scene prose: revealing the
killer to the author does not give a POV character that knowledge. Suspicion,
later proof and later quantification are normal stages; possession, working
copies, formal submission and sealed evidence are different acts. Oral
instructions do not establish signed authorization. Missing incidental dates
or routes are advice unless a real prerequisite is missing. Typed life and
physical-state slots are independent (`dead` plus `injured` is valid); reviewers
must not invent `deceased` or other unsupported enum values. The entry baseline
is distinguished from backstory, later revelations and explicit flashbacks.
When a dossier explicitly says a Character already knows a declared Secret at
entry but the typed initial_knowledge baseline omits it or is absent/unknown,
the mismatch is a blocking required_gap. Descriptive arcs cannot override Graph
knowledge authority. This does not infer knowledge from vague association, an
author's revealed synopsis or a future discovery; the source claim and typed
baseline must be grounded explicitly.

Bounded planning repair uses only blocking findings, never advisory suggestions.
An advice-only passing review therefore cannot spend a repair call. Unknown
state, missing required context, source staleness, actual truncation and
ungrounded/invalid output keep their existing conservative behavior; this
classification does not authorize automatic canon changes or force a model pass.

Coverage records `scope = plan`, `purpose = plan`, selected evidence counts and
omissions. A passing plan report means planned-draft consistency within those
inputs; it does not certify scene facts, a completed manuscript, exhaustive
historical recall or human canon approval. Human accept and explicit apply remain
separate. Plan adoption may require a fresh passing report on the accepted exact
Proposal version; any content/version, purpose, canon, evidence or style change
invalidates it under the standard freshness rules.
For autonomous expansion batches, the review projection includes the shared
whole-volume progress (for example current chapters 1–5, total 20, remaining
6–20). The critic checks pacing against that scope without treating a partial
batch as the entire volume or confusing partial proof with final resolution.


### Trusted plan author brief

PLAN semantic review may receive an explicit `author_brief` from the frozen
PlanningRun request instruction, or the validated original manual blueprint
request (manual expansion uses its exact accepted/applied parent request).
This optional service argument is a nonblank string of at most 12000 characters,
allowed only for plan-purpose review. It is never inferred from generated target
text, a target field named author_brief, or model-authored prose. It is exposed
as `style_sources.author_brief`; matching style findings still require exact
target evidence plus an applicable kind=style citation. A target copy of the
brief cannot substitute for style authority.

The explicit brief is included in style freshness fingerprints only when
provided. Omission/null preserves the historical fingerprint exactly. Changes,
addition or removal invalidate the corresponding report; all plan read/apply
gates resolve the same trusted input. Old failed results are never replayed or
recertified; prior plan reports without the newly supplied authority require
fresh review. Scene/default paths do not acquire this authority.

The bounded convenience registry registers style sources, then scoped canon,
then target segments, retaining original ordering within each group. The
2000-entry/180000-character limits and explicit omission coverage remain. Full
target text/parsed plan is still sent; exact canonical quotes remain supported
when aliases omit a segment. Token binding, exact IDs/quotes, coverage and all
blocking rules remain unchanged.


### Plan phase scope

The PLAN critic uses existing validated target metadata: planning-run and manual
expansion projections expose current_plan.phase; a manual blueprint exposes
top-level longform_plan_v1 phase; final-book projection has
review_scope=whole_book_blueprint_and_scene_outcome_ledger and exact_refs.
Blueprint review covers world/entities/rules/arcs, volume design and declared
chapter/scene/length budgets; it cannot demand individual later expansion
chapters/scenes inside that blueprint schema. Expansion review covers the current
batch plus its compatibility with blueprint/prior context; missing future
batches alone are not required gaps. Final-book review requires the complete
planned grid and all exact refs, covering the full blueprint/outcome ledger.
The author brief's full-workflow goal applies across these phases. No prose
guess introduces a phase, and no new transport field is required. Actual missing
current-phase prerequisites, upstream contradictions, proof sufficiency, strict
evidence and coverage checks remain. This prompt guidance neither certifies old
failed judgments nor proves model performance; new review remains explicit.


### Model-facing output schema

Each semantic critic user message includes output_schema, freshly derived from
SemanticReviewOutput.model_json_schema(). It retains the model's existing
required fields, bounds, enums and strict additionalProperties=false objects.
The transport variants use the existing parser-supported exact citation forms.
For NEW replies the preferred schema unconditionally requires top-level
evidence_registry_id as a string const for this request;
evidence items may be canonical kind/ref/quote or an object containing only
source_id selected from the current bounded registry. A schema conditional
also requires the nonce when any alias occurs. Canonical-only output without
it remains a parser compatibility path, not the recommended new reply shape.
The registry's existing 2000-entry bound also bounds the alias enum/schema.

This is message data and prompt guidance, not a provider protocol/response-format
change or a new validator. Local strict parsing, token matching, grounding,
coverage and semantic checks remain authoritative. Unsupported extra fields
including status_reason are still invalid at output, issue and evidence levels.
Full target/plan, canon, style and registry inputs remain present under their
existing budgets; no source is dropped to add the schema. Report shape and
freshness are unchanged, and no old failed response is replayed or salvaged.


The advertised issue schema additionally reflects the existing style grounding
rule: when dimension=style_constraint, evidence must contain at least one target
and one style citation. Each may use canonical kind/ref/quote or an exact alias
whose registered source has the corresponding kind. A target copy of an author
brief is not a style source; no alias is remapped or inferred. Empty registries
still permit valid canonical pairs, and nonstyle issue shapes remain unchanged.
The kind-specific alias enums partition the existing bounded registry, keeping
the complete advertised schema bounded. This changes only model-facing schema
guidance; strict parser/grounding acceptance and historical reports are unchanged.


### Preferred nonce and stable wire prefix

Every new critic reply is instructed to echo the exact top-level nonce found in
the FINAL user-JSON field, even when using only canonical evidence or no issues.
The preferred advertised schema requires it unconditionally. The runtime parser
is unchanged: canonical-only historical/default replies may omit it, any alias
requires the exact token, and a supplied token is always validated. No missing
field is inserted or repaired; historical invalid responses remain invalid.

Only model-facing user-JSON serialization preserves explicit insertion order
without sorting: canon, style_sources, plan_content, target, required_dimensions,
missing_context, evidence_sources, evidence_registry_coverage, output_schema,
then evidence_registry_id. All field values and full source inputs are retained.
The output schema itself still contains the dynamic nonce const near the end,
so only the source prefix before that const is stable across identical requests,
not the entire schema/message. The system prompt is static across requests and
never embeds the current nonce. This ordering permits stable-prefix reuse but
does not guarantee provider cache hits or compliance. Canonical hashing remains
on the unchanged sorted canonical_json path; report fingerprints, freshness,
provider protocol and accepted runtime shapes do not change.
