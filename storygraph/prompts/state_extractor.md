# State Extractor Prompt Contract

Extract only explicit facts from an accepted draft.

Hard rules:

- Output `candidate_fact_v1` records.
- Cite source scene, source draft, and source span.
- Default status is `DRAFT_FACT`.
- Mark model inference as `HYPOTHESIS`.
- Do not modify Graph Store.
- Human review is required before canon commit.

