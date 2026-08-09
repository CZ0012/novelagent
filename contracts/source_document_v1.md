# source_document_v1

`source_document_v1` defines the project-scoped local Source Store used for
imported manuscripts, outlines, setting notes, and other author-provided
reference documents.

A Source Document is private local runtime data. It is not Draft Store prose,
not a Proposal Artifact, not a CandidateFact, and not Graph Store canon. Import
and extraction may populate only the Source Store. Any later Agent output must
enter Proposal Store or another existing review boundary explicitly.

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
- `language`: BCP 47-style language label such as `zh-CN` or `en-US`.
- `byte_size`: original local file size in bytes.
- `checksum_sha256`: lowercase 64-character SHA-256 of the original file bytes.
- `extraction_status`: `ready`, `failed`, or `archived`.
- `extracted_text`: extracted plain text or null.
- `character_count`: length of `extracted_text`, or zero when text is absent.
- `warnings`: bounded extraction/import warnings.
- `error`: bounded user-readable extraction error or null.
- `provenance`: local import provenance without secrets or absolute paths.
- `created_at` and `updated_at`: UTC timestamps.

## Initial Supported Formats

The first v1 implementation supports:

- `.txt` as `text/plain`
- `.md` and `.markdown` as `text/markdown`
- `.docx` as
  `application/vnd.openxmlformats-officedocument.wordprocessingml.document`

RTF, PDF, OCR, images, PSD, archives, and executable formats are not supported
by this initial contract implementation. A client must report skipped or failed
files honestly rather than relabeling them as successful text imports.

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

`POST /projects/{project_id}/sources/{source_document_id}/archive`:

- requires at least local `read_generate` permission;
- is idempotent and returns a summary;
- archives Source Store data only and must not remove derived proposals, drafts,
  candidates, graph data, or events.

`POST /projects/{project_id}/sources/{source_document_id}/structure-draft`:

- requires at least local `read_generate` permission and a `ready` source;
- resolves text in the backend rather than accepting duplicate private text;
- creates only a non-canon `project_structure_draft` Proposal Artifact;
- records `ProposalRef(kind="source_document", ref=<stable id>)`;
- must not create Chapter or Scene nodes until the existing explicit proposal
  accept-and-apply action is completed by the author.

The legacy `POST /projects/{project_id}/imports/structure-draft` text request may
remain temporarily for compatibility, but the project workbench should use the
source-backed route after migration.

## Agent Discussion Integration

`POST /projects/{project_id}/scenes/{scene_id}/agent-discussion` may add:

```json
{
  "source_document_ids": ["source_001"]
}
```

- The default is an empty list; no Source Store document is included implicitly.
- Every id must belong to the route project and have `extraction_status = ready`.
- The backend resolves bounded text and records stable `source_document` refs.
- The client must show which documents are selected before sending the request.
- If the author disables current-draft inclusion, the client must not send the
  editor text as `base_text` or through another field.
- Existing inline `local_sources` requests may remain temporarily for API
  compatibility, but persisted-workbench documents should use stable ids.

Agent output remains a non-canon `scene_rebuild` or `scene_draft` Proposal
Artifact. It must not overwrite Draft Store, create CandidateFacts, or write
Graph Store canon.

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
- `language` belongs to the source record and is available for later output
  language controls. v1 does not infer canon or translate text automatically.
- Chinese and English documents must not be mixed automatically. Cross-language
  inclusion requires explicit author selection in a later workflow.

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
