# v0.1.14 verification scope

This release reorganizes the existing author workflow as an outline, manuscript and Agent workspace. It does not add autonomous multi-file editing or implicit conversation memory. Each Agent request uses its explicit current instruction, saved Draft and selected source context.

## Findings and fixes

- Chapters were static rows while leaf scenes used disclosure arrows. Chapters now have real folding controls; scenes open prose, including an already-selected scene viewed from another surface.
- Known genre values receive display localization. Persisted chapter and scene titles remain author data; explicit title edits use existing APIs and preserve stable IDs.
- The Agent shares the editor's existing Draft/Proposal state and exact saved-Draft input. Full manifests and advanced source options are collapsible; blocking reasons remain visible. Proposal review and promotion remain explicit.
- Structure language validation now includes obvious short headings and English heading frames containing Chinese names. First application validates edited proposal content before graph writes. Completed application retries retain their existing compatibility checks.
- A minimally planned scene can use discussion and saved-Draft continuation. Missing planning values become empty Context Pack projections with explicit gaps; they do not cause an HTTP 500 or create canon defaults. Full scene generation retains its existing required-context checks.

Language detection is heuristic: short proper names can be ambiguous, and a model may still return incorrectly localized content. Rejected output is not automatically translated or retried with a paid API call. Existing outlines are not rewritten by a software update.

## Validation

The final Python suite passed with **316 passed / 1 skipped**; **62 Web tests**, TypeScript and the production Web build passed. Ruff and whitespace checks passed. Independent review identified and verified fixes for stale metadata targeting and malformed structure-language input.

Production-browser acceptance verified chapter folding, same-scene navigation with dirty text preserved, send blocking until save, exact saved-Draft continuation and selected-text revision, proposal baseline comparison, title-only rename, and a chapter A metadata save after opening a scene in chapter B. Reading the isolated stored state confirmed both original Drafts were unchanged by generation, proposals referenced the displayed Draft IDs, the renamed chapter title survived a later summary edit, and the other chapter remained unchanged. Chinese/English switching preserved story content and translated known genre values. At widths 1080 and 900, content fit horizontally and the narrower layout placed the Agent below the editor without overlap.

Browser acceptance uses an isolated synthetic workspace and deterministic provider responses; it is not a model-quality benchmark and made no external model call. The user's running desktop and novel workspace were not modified by this acceptance run. The final Windows package was independently verified by static extraction; this task did not replace or stop the running installation.

## Package verification

The 32,285,666-byte installer has SHA256 `35bffebe654a9c8272ec79dac2d9e75765721da9d554549bd52d36d8d49191b8`. Its Tauri updater signature verifies with the pinned public key; a one-byte tampered copy is rejected. The updater metadata signature and download URL match. This is separate from Windows Authenticode signing.

The packaged backend matches the final sidecar exactly, including the language checks and nullable Context Pack fix. All six production JS/CSS assets, including independent Chinese/English catalogs, match the verified Web build. Native version metadata is 0.1.14; the native executable differs from the build only by Tauri's expected NSIS bundle marker. The packaged Windows update guard matches source, and the native lifecycle/installer guard implementation is unchanged from the verified 0.1.13 release.

Exact local credential comparisons and generic secret/path scans found no actual credentials or private workspace files in the changed software files or 4,143 decoded package items. Source pattern candidates were reviewed as documentation or synthetic test placeholders. These checks do not require uploading credentials or private story text.
