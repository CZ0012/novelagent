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
- Make Source-to-Agent handoff select only the stable Source Document ID and navigate; do not copy extracted text, persist a second source payload, call an Agent, or change cross-language policy until the author acts explicitly in the Agent panel.
- Show an Agent input manifest before send and submit its exact saved Draft ID as `included_draft_id`; the displayed ID, backend/provider input, and resulting Proposal Draft ref must match. Resolve Proposal review baselines only from one unique recorded Draft source ref through the exact scoped Draft route. Treat zero/multiple refs as unavailable/ambiguous, never as permission to use latest Draft.
- Keep diff, expanded-history, and dirty editor state client-only. Block Agent sends that would omit or replace unsaved Draft text; while Proposal title/body edits are dirty, visibly guard Proposal lifecycle actions and proposal/scene/project navigation until save, discard, or cancel.
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
- Follow `agent_runtime_v1` for preset create/edit/select/delete and explicit provider model discovery. Localize built-in display labels through separately loaded catalogs, preserve custom prompt content, never auto-switch models, and send a saved exact `included_draft_id` for `continue_scene`; display the resulting appended Proposal for author review.
- Load locale catalogs through `localeRegistry` lazy imports and await bootstrap/content catalogs before rendering them. Keep the browser backend URL as a local UI preference distinct from provider configuration and desktop backend management. Preserve Draft scope/revision gates across navigation, reads and saves; author-text exports are client-only downloads.
- Do not persist diff hunks or dirty flags into Proposal/Draft/Source records, and do not offer promotion to a Scene that conflicts with a proposal's unique declared target.

## SG-024 update consistency

Keep connected backend version distinct from desktop version, with /health.version and legacy OpenAPI fallback; unknown/mismatch must not read as fully current. Download before stopping the backend, reuse dirty edit guards, call prepare_backend_update before install, and cancel the gate before restoring only a previously managed backend.


## SG-025 novel editor workspace

Use real chapter disclosure controls and document leaf buttons. Activating any scene opens prose through existing navigation guards, including the already-selected scene. Keep one parent Draft/Proposal state shared by editor and Agent sidebar; do not chain state-setting save and send through a stale closure. Keep blocking dirty/language feedback visible outside collapsed input controls. Translate only known display enums, never author titles.

Missing nullable scene planning fields project to empty Context Pack strings with explicit gaps under context_pack_v1. Discussion and saved-Draft continuation may use that pack; full scene generation retains its required-context gate. Never write projected defaults back to canon.
