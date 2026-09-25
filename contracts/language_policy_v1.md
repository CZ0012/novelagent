# Language Policy Contract v1

## Purpose

`language_policy_v1` defines the independent language boundaries for the local
user interface, project-authored content, Agent output, imported sources, and
persisted generated artifacts.

An author may explicitly request translation of already persisted outline
metadata through the reviewed `outline_language_patch_v1` subtype of
`canon_patch`, defined in `proposal_artifact_v1`. This exception is an explicit
content rewrite with before/after review, never a UI-language side effect,
automatic migration, metadata relabel, or translation of source/manuscript text.
The original project language, node IDs, and original strings are frozen; only
the separately accepted and explicitly applied replacements update the existing
outline. Structure generation also checks natural-language `timeline_position`.
The shared generated-output guard rejects obvious short English sentences in
Chinese output while preserving ambiguous proper names and machine identifiers;
it remains a conservative heuristic rather than comprehensive language detection.

The initial product supports `zh-CN` and `en-US` for UI and project output.
Imported sources may carry another valid BCP 47 language tag because the tag
describes the source rather than granting permission to mix or translate it.

Related contracts: `graph_store_v1`, `source_document_v1`, `context_pack_v1`,
`proposal_artifact_v1`, `style_sample_store_v1`, `workflow_run_v1`, and
`continuity_report_v1`.

## Language Types

### UI Locale

`ui_locale` MUST be one of:

- `zh-CN`
- `en-US`

It controls display-layer labels, menus, dates, status explanations, validation
messages, and desktop-native visible text. It MUST NOT control story content or
Agent output and MUST NOT be persisted in Graph Store, Source Store, Draft Store,
Context Pack, Proposal Store, Candidate Store, Workflow Store, or Event Log.

The default UI locale is `zh-CN`. Web and Tauri-hosted clients persist it as a
versioned local client preference. It is not a project setting and does not
belong in `/settings/agent`. A Tauri native preference may mirror the WebView
preference only to localize native window, tray, and updater text.

### Project Language

`Project.language` is the authoritative language for project-authored content
and new Agent output. It MUST be one of:

- `zh-CN`
- `en-US`

The existing field name `language` is retained for compatibility. It means
project content language, never UI locale or source-document language.

For backward-compatible API creation, an omitted `language` may default to
`zh-CN`, but the response and UI MUST expose the resolved value explicitly. The
project form must not silently change it based on `ui_locale`.

### Output Language

`output_language` is a server-derived immutable snapshot of `Project.language`
at the start of a generation or workflow operation. It is not a third mutable
language preference and clients MUST NOT override it with an author instruction
or request-local value.

All story prose, rewrites, project-structure titles and summaries, generated
proposal bodies and titles, scene summaries, deterministic fallbacks, and other
persisted Agent-authored content MUST follow `output_language`. Proper names,
contract identifiers, stable IDs, and bounded verbatim source quotes may retain
their original form.

Project structure analysis MUST validate its normalized chapter/scene titles,
summaries, purpose, goals, and conflicts before saving a generated Proposal.
This applies to both model and deterministic analysis. The language guard must
not exempt all short headings merely because they are below a prose-length
threshold: generic labels such as `Prologue` and recognizable short English
narrative phrases conflict with `zh-CN`. A Chinese chapter-number prefix alone
does not satisfy this requirement when the remaining heading is English.
Generation prompts should illustrate the schema with the resolved project's
content language rather than English placeholder values for every project.

The script/phrase guard is conservative validation, not a general language
detector or translator. Short ambiguous names and acronyms such as `Alice`,
`Mars`, and `AI` remain permitted. Source-title metadata, explicit POV/location
labels, timeline metadata, and exact names declared in those POV/location
labels retain their original form. Unrecognized mixed-language wording can
still require author review. Validation errors identify field paths and the
required language without exposing field text; they must not trigger an
implicit second paid model call or silently translate source content.

### Source Language

`SourceDocument.language` describes the imported source text. It MUST be either:

- a syntactically valid, canonicalized BCP 47 language tag; or
- `und` when the language is unknown or has not been author-confirmed.

New inputs SHOULD use hyphens and canonical BCP 47 casing. Legacy underscore
forms may be accepted at the API boundary and normalized before persistence.
Implementations MUST NOT silently map a broader or different tag such as `en`,
`zh-Hans`, or `zh-TW` to `en-US` or `zh-CN`.

Source language metadata does not make source text canon, authorize model use,
or request translation.

## Language Resolution

For every new generation or workflow run, the backend MUST:

1. Resolve the route project and validate `Project.language`.
2. Freeze that exact value as `output_language` before resolving model inputs.
3. Resolve every persistent source by stable ID inside the same project.
4. Apply the cross-language policy before sending any private text to a model.
5. Store `output_language` on the resulting Context Pack, Draft, Proposal
   Artifact, WorkflowRun, and ContinuityReport where those records are created.

An author instruction may refine content but MUST NOT change
`output_language`. Changing output language requires an explicit project-language
change.

## Cross-Language Source Policy

Requests that may send Source Documents to an Agent or structure analyzer MUST
use `cross_language_policy` with one of these values:

- `project_only`: default. Every selected Source Document language must exactly
  equal `Project.language`. `und` is not eligible.
- `explicit_reference`: permits an author-selected source with a known, valid
  BCP 47 language whose language differs from `Project.language`.

For persistent sources, `explicit_reference` is valid only when the author both
selects the stable Source Document ID in the current request and explicitly
selects this policy. For a compatibility-only inline or text-structure request,
the source payload itself is the explicit input and MUST also carry a known,
valid `source_language`. The backend still applies the available ownership,
ready/archive, bounded-text, permission, and provenance checks.

Cross-language inclusion MUST NOT:

- change `output_language`;
- translate or relabel source text automatically;
- auto-select other documents or remembered snippets;
- treat source content as canon or primary CandidateFact evidence; or
- weaken project, permission, provenance, or review boundaries.

Language mismatches under `project_only` MUST fail atomically before any model
provider call. Errors may identify bounded source IDs and language tags but MUST
NOT include source text or absolute paths.

`und` sources are ineligible under both policies. The author must correct the
source language before any model use.

Legacy inline `local_sources` and legacy structure-import requests MUST include
a valid source language. Missing or invalid language fails validation with
`422`; it is not defaulted from the project or treated as an implicit
`explicit_reference`. New persistent flows continue to prefer stable
`source_document_ids`.

## Persisted Language Snapshots

New records use these fields:

- `ContextPack.output_language`
- `Draft.content_language`
- `ProposalArtifact.content_language`
- `WorkflowRun.output_language`
- `StyleSample.language`
- `ContinuityReport.output_language`

`Draft.content_language` and `ProposalArtifact.content_language` MUST equal the
operation's `output_language` when created by an Agent or workflow. Manual
project content defaults to the current `Project.language` and may not silently
introduce another project output language.

Style retrieval MUST first filter by `project_id` and exact `language`, then
apply lexical or metadata scoring. A project-language change does not relabel
existing style samples.

Machine-readable contract names, enum values, issue types, status values, and
stable IDs remain unchanged and are localized only for display.

## Project Language Changes

Changing `Project.language` is an explicit, provenance-bearing project update.
The request MUST state:

- `expected_language`: optimistic concurrency value; and
- `language_change_policy`: currently only `future_outputs_only`.

`future_outputs_only` affects new Context Packs, Agent calls, drafts, proposals,
style retrieval, and workflow runs. It MUST NOT translate, rewrite, relabel, or
delete existing Source Documents, Drafts, Proposal Artifacts, Style Samples,
CandidateFacts, graph data, or workflow history.

In-progress WorkflowRuns continue with their frozen `output_language`.

## Compatibility And Migration

- Existing projects with exact `zh-CN` or `en-US` remain valid.
- Legacy `zh_CN` and `en_US` inputs may normalize to `zh-CN` and `en-US`.
- A legacy project with no language may be read as `zh-CN` because historical
  creation and Chinese-first behavior used that default. Responses MUST mark the
  value as inferred until an explicit project update persists it.
- A project with another or invalid value is `needs_review`. New Agent,
  structure-analysis, scene-generation, and workflow operations MUST stop before
  model use until the author chooses `zh-CN` or `en-US`.
- Existing sources keep valid BCP 47 tags. Missing or invalid source language is
  exposed as `und` until the author corrects its metadata; no text detection or
  silent relabeling is required.
- Existing Context Packs, Drafts, Proposal Artifacts, WorkflowRuns, Style
  Samples, and Continuity Reports without a language snapshot remain readable.
  API projections may infer the owning project language and MUST expose
  `language_inferred = true`; stored prose and reports are never rewritten.
  Every newly created pack, version, run, sample, or report MUST persist the
  snapshot.
- Legacy `imported_document` refs remain opaque provenance and do not become
  resolvable Source Document IDs.

## API Semantics

Project create/update requests continue to use `language`. New writes reject
unsupported project languages as validation errors.

Project read projections expose `language_status` as `confirmed`, `inferred`,
or `needs_review`. When compatibility inference is used, they also expose
`language_inferred = true`; these are projection/migration markers rather than
additional language authorities.

Project-language changes extend the existing project update route with
`expected_language` and `language_change_policy = future_outputs_only`.

Source metadata correction SHOULD use:

```text
PATCH /projects/{project_id}/sources/{source_document_id}
```

The request supplies `language` and `expected_updated_at`. It changes metadata
only and MUST NOT change the stable ID, checksum, extracted text, archive state,
or provenance.

Agent discussion and source-backed structure analysis accept
`cross_language_policy`, defaulting to `project_only`. Successful responses and
persisted artifacts expose the server-resolved `output_language`.

Legacy inline Agent sources and legacy text-based structure analysis also
require `source_language`. Omitting it is a validation error even for old route
shapes.

Recommended machine-readable failures include:

- `unsupported_project_language` (`422` for new writes)
- `project_language_needs_review` (`409` before generation)
- `source_language_mismatch` (`409` before provider use)
- `source_language_unknown` (`409` under either source policy)
- `project_language_changed` (`409` for failed optimistic concurrency)

## Invariants

- UI locale and project language are independently selectable.
- UI locale never changes model output language.
- Source language never changes project or output language.
- No source is translated, mixed, or sent implicitly.
- Cross-language reference requires explicit source selection/input, a known
  valid tag, and explicit policy in the same request; persistent sources use
  stable IDs.
- Existing records retain their original text and frozen language semantics.
- Language errors and logs never expose private source or draft text.

## Acceptance Matrix

The product MUST verify all four combinations:

| UI locale | Project language | UI chrome | New Agent/project content |
| --- | --- | --- | --- |
| `zh-CN` | `zh-CN` | Chinese | Chinese |
| `zh-CN` | `en-US` | Chinese | English |
| `en-US` | `zh-CN` | English | Chinese |
| `en-US` | `en-US` | English | English |

Focused acceptance tests MUST also prove:

- invalid project languages fail validation;
- a mismatch under `project_only` makes zero provider calls;
- `explicit_reference` keeps `output_language = Project.language` and records
  the selected stable refs and policy without translating the source;
- `und` is blocked under both source policies;
- language changes affect future output only;
- old and resumed records retain their snapshots or explicit inferred marker;
- style retrieval never crosses project or language; and
- UI locale is absent from all runtime story and canon stores.
