# source_document_v1

`source_document_v1` defines the project-scoped local Source Store used for
imported manuscripts, outlines, setting notes, and other author-provided
reference documents.

A Source Document is private local runtime data. It is not Draft Store prose,
not a Proposal Artifact, not a CandidateFact, and not Graph Store canon. Import
and extraction may populate only the Source Store. Any later Agent output must
enter Proposal Store or another existing review boundary explicitly.

Language semantics follow `language_policy_v1`.

## Required Fields

```json
{
  "contract_version": "source_document_v1",
  "id": "source_001",
  "project_id": "project_sample",
  "title": "世界设定",
  "relative_path": "设定集/世界设定.docx",
  "media_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "language": "zh-CN",
  "byte_size": 30176,
  "checksum_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "extraction_status": "ready",
  "extracted_text": "仅在详情响应和 Source Store 内部读取中返回。",
  "character_count": 19,
  "warnings": [],
  "error": null,
  "provenance": {
    "imported_by": "author",
    "imported_via": "local_file",
    "source_last_modified_ms": 1750000000000,
    "note": "作者从项目资料页导入。"
  },
  "created_at": "2026-08-09T00:00:00Z",
  "updated_at": "2026-08-09T00:00:00Z"
}
```

Required top-level fields:

- `contract_version`: must be `source_document_v1`.
- `id`: stable local Source Document id.
- `project_id`: owning project id.
- `title`: author-visible document title.
- `relative_path`: normalized slash-separated import path; it must not contain
  an absolute drive, UNC path, `.` segment, or `..` segment.
- `media_type`: normalized supported media type.
- `language`: canonical valid BCP 47 language tag such as `zh-CN` or `en-US`, or
  `und` while the author has not confirmed it. Validation, normalization, and
  model-use rules follow `language_policy_v1`.
- `byte_size`: original local file size in bytes.
- `checksum_sha256`: lowercase 64-character SHA-256 of the original file bytes.
- `extraction_status`: `ready`, `failed`, or `archived`.
- `extracted_text`: extracted plain text or null.
- `character_count`: length of `extracted_text`, or zero when text is absent.
- `warnings`: bounded extraction/import warnings.
- `error`: bounded user-readable extraction error or null.
- `provenance`: local import provenance without secrets or absolute paths.
- `created_at` and `updated_at`: UTC timestamps.

## Supported Formats

The additive v1 implementation supports:

- `.txt` as `text/plain`
- `.md` and `.markdown` as `text/markdown`
- `.rtf` as `application/rtf` (plain-text extraction; no rendering or embedded objects)
- `.docx` as
  `application/vnd.openxmlformats-officedocument.wordprocessingml.document`

PDF, OCR, images, PSD, archives, and executable formats are not supported
by this contract implementation. A client must report skipped or failed
files honestly rather than relabeling them as successful text imports.

Local extraction distinguishes empty input, failed/inconsistent reads, invalid
document containers, unsupported encodings, empty extracted text and resource
limits. A zero-byte original is an empty file, not proof that the importer
corrupted it. A file whose reported size differs from bytes read must not be
presented as a successful extraction. Errors are bounded stable categories with
localized UI explanations; raw parser errors must not expose absolute paths or
document content. Existing persisted parser errors remain readable, and an
available recorded error must not be described as a missing backend error.

Office owner/lock files beginning with `~$` are skipped as temporary files before
extraction and persistence. They are not novel documents or import failures.
RTF extraction is a bounded local text reader: preserve paragraphs, Unicode
characters and supported code-page text; skip formatting metadata, pictures,
embedded objects and field instructions. Never fetch external resources or
execute/render embedded content. Unsupported encodings and malformed/over-limit
inputs must fail explicitly rather than silently drop manuscript text.

## Extraction Status

- `ready`: `extracted_text` is present and usable for explicit Source Store
  reading, structure analysis, or Agent context selection.
- `failed`: extraction did not produce usable text. `error` must explain the
  failure; `extracted_text` must be null or empty.
- `archived`: the author removed the document from normal project-library
  views. Archiving is not deletion and does not invalidate existing stable
  proposal provenance refs.

Source text may remain stored for an archived record so existing provenance can
still be audited locally. v1 does not define a destructive delete route.

## Summary And Detail Views

List responses must use a Source Document summary that contains every field
except `extracted_text`. `character_count`, status, warnings, and error allow a
client to show useful state without loading or leaking the private full text.

The project-scoped detail route may return `extracted_text`. Clients should load
detail only for an explicit reader or action. API logs, coordination Markdown,
workflow events, proposal refs, and graph records must not embed the full text.

## Idempotency And Stable Identity

The import identity key is:

```text
(project_id, normalized relative_path, checksum_sha256)
```

- Re-importing the same key must return the same `id` and must not create a
  duplicate record.
- An unchanged ready record returns `created = false` and `updated = false`.
- Retrying a failed extraction with usable text may update the same record and
  returns `created = false`, `updated = true`.
- A changed checksum at the same path creates a new stable Source Document id;
  the prior record remains available for provenance until explicitly archived.
- Identical paths or checksums in different projects are always separate
  records. No import may reuse a record across projects.

## Governed API Routes

```http
POST /projects/{project_id}/sources
GET  /projects/{project_id}/sources
GET  /projects/{project_id}/sources/{source_document_id}
PATCH /projects/{project_id}/sources/{source_document_id}
POST /projects/{project_id}/sources/{source_document_id}/archive
POST /projects/{project_id}/sources/{source_document_id}/structure-draft
```

`POST /projects/{project_id}/sources`:

- requires at least local `read_generate` permission;
- accepts extracted text plus import metadata from the local Web/Tauri client;
- validates that the project exists, the relative path is safe, the media type
  is supported, the checksum shape is valid, and ready text is non-empty;
- returns `{ "document": <summary>, "created": bool, "updated": bool }`.

`GET /projects/{project_id}/sources`:

- requires read permission;
- returns summaries only and excludes archived records by default;
- may accept an explicit `include_archived` query for local audit views.

`GET /projects/{project_id}/sources/{source_document_id}`:

- requires read permission;
- returns the project-scoped detail including `extracted_text`.

`PATCH /projects/{project_id}/sources/{source_document_id}`:

- requires at least local `read_generate` permission;
- accepts a corrected `language` plus `expected_updated_at` for optimistic
  concurrency;
- changes language metadata only and must not change stable ID, checksum,
  extracted text, archive state, or provenance.

`POST /projects/{project_id}/sources/{source_document_id}/archive`:

- requires at least local `read_generate` permission;
- is idempotent and returns a summary;
- archives Source Store data only and must not remove derived proposals, drafts,
  candidates, graph data, or events.

`POST /projects/{project_id}/sources/{source_document_id}/structure-draft`:

- requires at least local `read_generate` permission and a `ready` source;
- resolves text in the backend rather than accepting duplicate private text;
- accepts `cross_language_policy`, defaulting to `project_only`, and applies
  `language_policy_v1` before any provider call;
- creates only a non-canon `project_structure_draft` Proposal Artifact;
- records `ProposalRef(kind="source_document", ref=<stable id>)`;
- must not create Chapter or Scene nodes until the existing explicit proposal
  accept-and-apply action is completed by the author.

The legacy `POST /projects/{project_id}/imports/structure-draft` text request may
remain temporarily for compatibility, but it MUST require a valid
`source_language` and apply the same `cross_language_policy`. A missing or
invalid source language is `422`, including when `explicit_reference` was
requested. The project workbench should use the source-backed route after
migration.

## Agent Discussion Integration

`POST /projects/{project_id}/scenes/{scene_id}/agent-discussion` may add:

```json
{
  "source_document_ids": ["source_001"],
  "include_latest_draft": true,
  "included_draft_id": "draft_001",
  "cross_language_policy": "project_only"
}
```

- The default is an empty list; no Source Store document is included implicitly.
- Every id must belong to the route project and have `extraction_status = ready`.
- The backend resolves bounded text and records stable `source_document` refs.
- `project_only` rejects a source whose language differs from
  `Project.language`; `explicit_reference` permits only a known valid different
  BCP 47 tag selected in this request. `und` is rejected under both policies.
- A language rejection occurs before any model provider call and never includes
  source text in the error.
- The client must show which documents are selected before sending the request.
- A current workbench client that enables saved-Draft inclusion MUST also send
  the exact displayed Draft id as `included_draft_id`. The backend resolves that
  id only inside the route project and Scene and uses that same Draft as the
  provider input and Proposal `source_refs[kind = draft]`; it MUST NOT silently
  substitute the latest Draft. Missing or cross-scope ids fail before a provider
  call. Legacy clients that enable inclusion without this additive field may
  retain latest-Draft compatibility, but that fallback is not current workbench
  behavior.
- If the author disables current-draft inclusion, the client must not send the
  editor text as `base_text` or through another field, and
  `included_draft_id` must be absent or null.
- Existing inline `local_sources` requests may remain temporarily for API
  compatibility, but every item MUST include a valid `language` and obey the
  same cross-language policy. Missing/invalid language is `422`; it is never
  inherited from the project. Persisted-workbench documents should use stable
  ids.

Agent output remains a non-canon `scene_rebuild` or `scene_draft` Proposal
Artifact. It must not overwrite Draft Store, create CandidateFacts, or write
Graph Store canon.

### Source-To-Agent Client Handoff

A Source Library action that carries a document to the Agent panel is a
selection-and-navigation convenience only. It MUST place only the stable
`SourceDocument.id` in transient client selection state and navigate to the
Agent panel. The handoff itself:

- MUST NOT copy `extracted_text` into an author instruction, `base_text`, a
  legacy `local_sources` payload, Proposal ref, browser persistence, or another
  client/story store;
- MUST NOT call the model provider, create a Proposal or Draft, archive or patch
  the Source Document, or mutate Candidate, Graph, Event, or workflow state;
- MUST NOT enable `explicit_reference` or otherwise change
  `cross_language_policy` automatically; and
- MAY reuse already loaded summary metadata for display, but the eventual
  author-submitted Agent request must send the stable id in
  `source_document_ids` and let the backend resolve and validate the text.

A selected source with a different language remains visibly blocked under
`project_only` until the author explicitly changes the policy in the Agent
panel. Navigating to the panel is not that consent. Removing the selection
before send transmits no source id and no source text.

## Proposal References

New persistent Source Store provenance uses:

```json
{ "kind": "source_document", "ref": "source_001", "note": "世界设定" }
```

`proposal_artifact_v1` keeps its open string ref shape, so no Proposal Artifact
field change is required. Legacy `kind = imported_document` refs remain valid as
opaque compatibility refs, but they do not prove that a persistent Source Store
record exists. New source-backed routes must use `source_document`.

Refs may include a short bounded quote or source span when needed for review,
but must never copy a full private document.

## Project And Language Isolation

- Every list, detail, archive, structure-analysis, and Agent-resolution path is
  scoped by `project_id`.
- Looking up another project's Source Document must return not-found behavior,
  not document metadata.
- `language` belongs to the source record and follows `language_policy_v1`; it
  never sets `Project.language` or `output_language`.
- Chinese, English, and other tagged documents must not be mixed automatically.
  Cross-language use requires both explicit stable-source selection and
  `cross_language_policy = explicit_reference` in the same request. A legacy
  inline/text request uses its explicitly supplied payload plus required known
  `source_language` as the compatibility equivalent; it never gains stable
  Source Store identity.
- Cross-language use does not translate, relabel, or change output language.
- `und` documents remain storable and reviewable but cannot enter Agent or
  structure prompts until the author assigns a valid known language.

## Canon Safety Invariants

- Source Store is not a source of canon truth.
- Import, retry, read, list, archive, and structure analysis must not mutate
  Draft Store, Candidate Store, Graph Store, Event Log, or workflow checkpoints.
- Full source text must not be written to Graph Store, CandidateFact evidence,
  proposal refs, updater metadata, coordination files, or Git.
- Source-backed Agent calls may transmit selected bounded text only to the
  author-configured model provider after the author's explicit action.
- A generated structure proposal may create only Chapter/Scene nodes after the
  existing explicit accept-and-apply boundary.
- Facts extracted from source material still require a real Draft Store source
  and `candidate_fact_v1` review provenance before canon commit; this contract
  does not relax that rule.
- Web and Tauri use the same FastAPI Source Store routes. The desktop shell must
  not create a separate import database or canon-writing path.

## Explicit source text adoption into a scene Draft

`POST /projects/{project_id}/scenes/{scene_id}/draft/from-source` is a separate
`full` author-write action. Importing, viewing or selecting a Source never invokes
it automatically. It requires `source_document_id`, `expected_source_updated_at`,
`expected_source_checksum`, `start`, `end`, `expected_text` and required nullable
`expected_current_draft_id`. Offsets are half-open **UTF-16 code units**, matching
browser/JavaScript selection. The server rejects out-of-range positions, split
surrogate pairs and any mismatch between the exact Source span and expected text.
The selected text is copied verbatim, including paragraph breaks and whitespace;
it is not a summary, model rewrite or guessed mapping from an old outline.

The Source must be ready, same-project, unchanged and have the exact project
language; `und` and cross-language verbatim adoption are rejected. Authors may
instead explicitly reference foreign-language Sources when requesting an Agent
proposal under the existing cross-language policy. Adoption never translates or
relabels source text and creates no graph, CandidateFact or event-log writes.

The current scene Draft is compared under the Draft lock before a new version is
created. A retry of the same validated source operation returns its existing
Draft ID. `Draft.provenance` is additive nullable JSON (SQLite `provenance_json`,
legacy records remain null); source adoption stores kind, source ID/checksum/
updated-at, extracted-text SHA-256, UTF-16 start/end, adopted-text SHA-256 and the
previous Draft ID. It stores no absolute local path or duplicate source prose.
Graph → Source → Draft locks keep scene ownership/project language and Source
state stable through adoption. The current implementation supports local JSON
and memory graphs only; unsupported graph backends fail closed.

Legacy structure proposals containing only opaque `imported_document` refs do
not establish Source Store identity or exact prose spans. Clients must not invent
those links, treat summaries as manuscript text, or assign an entire imported
novel to a selected scene. Explicit selection and adoption/generation are required.
