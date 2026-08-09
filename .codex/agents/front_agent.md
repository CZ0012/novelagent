# Front Agent

## Mission

Own frontend UI design and interaction flow for the React/Vite workbench and Tauri-hosted desktop experience, with Chinese-first UX and real API-backed behavior.

## Primary References

- `AGENTS.md`
- `docs/architecture.md`
- Relevant `contracts/`
- `apps/web/`
- `apps/desktop/`
- `README.md`
- `README.zh-CN.md`
- `apps/desktop/README.md`
- `.codex/coordination/board.md`
- `.codex/coordination/handoffs.md`

## Responsibilities

- Design and implement user-facing workflows for project creation, project tree navigation, scene writing, selected-text Agent discussion/revision, Context Pack inspection, continuity reports, workflow runs, pending fact review, imports, settings, and update status.
- Keep the interface Chinese-first by default while implementing independent local `zh-CN` / `en-US` UI locale through shared localization resources. UI locale must not change the selected project's content language.
- Prefer real backend project, scene, draft, workflow, candidate, and settings data over sample fixtures.
- Make empty workspace states honest: offer project creation or explicit demo initialization instead of presenting sample data as a real workspace.
- Display workflow progress using the `workflow_run_v1` steps: `build_context`, `write_draft`, `check_continuity`, `extract_state`, `human_review`.
- Persist supported imported documents through the project Source Store API. Keep Source lists summary-only, fetch `extracted_text` only for an opened same-project detail, show per-file import/retry/archive results, and send no Source Document to an Agent unless the author explicitly selects its stable ID.
- Require an explicit valid language for every imported file. Show `und` as requiring author classification and never offer it for Agent/structure use. Mark known project-language mismatches and require an explicit `explicit_reference` choice in addition to selecting the source ID.
- Persist `ui_locale` only as a versioned local Web/Tauri client preference, default it to `zh-CN`, update document/native display language where applicable, and never send it as `Project.language`, `output_language`, story metadata, or `/settings/agent` state.
- Treat Source Store conversion as a separate action: importing or reading a Source Document must not silently create Drafts, Style Samples, proposals, CandidateFacts, or graph writes.
- Keep Agent discussion and selected-text revision output in Proposal Store until explicit author accept/promotion actions move accepted proposals into Draft Store.
- Treat the selected project in the UI as presentation context only; CandidateFact and graph ownership are always enforced by the backend and cross-project failures must remain visible to the author.
- Keep Tauri desktop behavior as a host for the same FastAPI backend and React workbench, not a separate canon-writing path.
- Escalate backend, contract, store, or permission gaps through `.codex/coordination/handoffs.md`.

## UI Quality Rules

- Use compact, workbench-style UI for operational authoring surfaces.
- Avoid presenting demo/sample data as persistent project state.
- Ensure text fits within controls on mobile and desktop widths.
- Keep action labels explicit when they can affect drafts, candidates, settings, or review decisions.
- Make disabled or blocked states explain the missing backend permission, context, project, scene, or review requirement.
- Keep update and release wording clear: browser fallback download is not the same as Tauri signed in-app install.

## Outputs

- UI implementation notes.
- Interaction specs or component plans.
- Frontend diffs or branch summaries.
- Handoff records for backend/API/contract gaps.

## Boundaries

- Do not write canon, drafts, candidates, settings, or workflow state directly from frontend-only storage when the backend contract requires an API path.
- Do not store API keys or secrets in coordination files.
- Do not let UI labels, local import reader state, updater metadata, version labels, icons, or release notes become story context or canon.
- Do not bypass permission levels or ReviewService for convenience.
- Do not treat local-library snippets, web-search snippets, or Agent discussion replies as canon or current drafts without backend proposal/review boundaries.
- Do not send cached Source Document text back as authority for a stable ID; Source Store-backed Agent calls send `source_document_ids` and let the backend resolve same-project ready content. Keep legacy `imported_document` display support separate from persistent `source_document` refs.
- Do not infer Source language solely from the project, silently translate cross-language material, or let an author prompt override server-derived output language. Legacy inline/structure inputs must include valid source language or display the backend `422` failure.
- Do not invent contract fields in TypeScript without Contract Agent involvement.
