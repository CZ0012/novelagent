# Style Sample Store Contract v1

## Purpose

`style_sample_store_v1` defines the local retrieval boundary for style examples used by Context Pack construction.

Style samples are soft writing guidance. They are not graph canon, do not override graph facts, and must not be promoted into hard `style_constraints` without explicit author action.

## Producers And Consumers

- Primary producer: explicit author/API/CLI style-sample ingest.
- Primary consumer: Context Agent through `ContextPackBuilder`.
- Secondary consumers: Writing Agent and QA Agent through `context_pack_v1`.
- Related contracts: `context_pack_v1`, `graph_store_v1`.

## Required Style Sample Fields

- `contract_version`: must be `style_sample_v1`
- `id`
- `project_id`
- `text`
- `source_ref`
- `pov`
- `tone`
- `dialogue_style`
- `tags`
- `summary`
- `created_at`

## Search Inputs

Search must accept:

- `project_id`
- `query`
- `pov`
- `tone`
- `dialogue_style`
- `tags`
- `limit`

## Search Result Fields

Each match should include:

- `sample`
- `score`
- `matched_terms`

## MVP Retrieval Rules

- The MVP implementation uses deterministic local lexical and metadata scoring.
- It must not require external embeddings, OpenAI API keys, or network access.
- Results must be filtered by `project_id`.
- Ordering must be stable: higher score first, then `sample.id`.
- `limit` must be explicit and positive.

## Context Pack Integration

Context Pack builders may include matched sample snippets in `retrieved_style_samples`.

`provenance.style_sample_refs` should include stable style sample IDs. These refs point to the style sample store, not graph canon.

## Invariants

- Style samples must not mutate Graph Store canon.
- Style samples must not create `CandidateFact` records.
- Style samples must not contain full chapters in retrieved context.
- Automated draft generation must not auto-ingest style samples.
- Retrieved samples are `P6` context and should be dropped before hard scene constraints when budget pressure requires trimming.

