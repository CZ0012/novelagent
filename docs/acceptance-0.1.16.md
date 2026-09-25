# v0.1.16 verification scope

This release makes saved manuscript text the primary reading surface, adds Preview/Edit and precise selection-driven Agent requests, and provides explicit source adoption plus reviewed new chapter/volume composition. Historical outlines without saved prose receive actionable empty states instead of an unlabelled blank editor.

## Implementation boundaries

Chapter preview reads each scene's saved Draft and distinguishes empty scenes from failed reads. Scene preview and editing share the same protected draft state. Selection requests pin the saved Draft ID and exact UTF-16 range/text, including repeated passages and non-BMP characters. Agent-generated revisions remain independent proposals. The red/green comparison adds signs, semantic insertion/deletion markup and accessible labels, preserves text verbatim, and bounds long-text diff work.

Source adoption uses a selected exact range with source freshness and current-Draft checks; it preserves provenance and never changes canon. Verbatim adoption requires matching source/project languages. A foreign-language source may be explicitly used as an Agent reference instead. No automatic mapping from opaque historical import references, summary-to-prose conversion or silent translation occurs.

New chapter/volume generation creates a bounded composition proposal containing plans and initial prose. It does not write graph nodes or drafts during generation. Explicit accepted application creates new chapter/scene identities and their initial drafts, with volume grouping represented through the existing chapter volume index. Existing story content is preserved.

## Verification

- Backend: full Python suite **418 passed / 1 skipped**, followed by **45 targeted regressions** after the final provenance guard and two additional bilingual tests; **420 distinct passing tests** across these runs. The 49-test independent review subset and Ruff passed.
- Web: **117 tests**, TypeScript and production build passed, including **22 difference-rendering tests**, exact selection, strict composition parsing, proposal origin and application policy. Chinese and English catalogs remain independently loaded.
- Native lifecycle and installer hooks are unchanged from the independently verified v0.1.15 implementation; that release's 11 Rust, 35 packaged lifecycle and 5 real NSIS checks are prior evidence, not newly rerun claims.

Production-browser acceptance used an isolated synthetic workspace. It exercised chapter reading, preview/edit preservation, navigation with unsaved prose, exact selection of the second repeated paragraph, red/green proposal review and adoption, empty-scene drafting, source-range adoption including a non-BMP character, and a reviewed two-chapter volume with initial prose. Continuation preserves the saved manuscript and highlights only appended text. An applied composition is visibly disabled against duplicate application. Model origin stays tied to the first proposal version through review and acceptance.

The source panel's advanced actions are folded and its text remains scrollable. Difference content now owns its layout height instead of overflowing onto action buttons. Final production views were inspected at widths 1280, 1080 and 900; the latter two had no horizontal document overflow. English UI labels changed independently of Chinese manuscript content. Foreign-language material visibly blocks verbatim adoption and remains available as an explicitly selected Agent reference.

The authorized private-novel test used an isolated copy and the configured third-party endpoint with its listed model identifier `glm-5.3-flash`. One real call generated a chapter plan and **837 characters of Chinese prose** from an explicitly selected English reference. A second real call revised an exact **93-unit UTF-16 selection**. Generation preserved graph and saved drafts; acceptance alone did not apply structure. Explicit application created one chapter, one scene and one initial draft, retained existing nodes/relationships, and remained idempotent after backend restart. The revision left the saved draft unchanged and preserved the unselected suffix. No further paid calls were made for replay. The identifier does not establish the underlying model vendor.

The author's original project still has no saved scene drafts: the old import produced outline nodes, not mapped prose. Original graph nodes/relationships match the initial test copy; settings match except for the model deliberately selected only in the test copy. No original manuscript or running installation was modified. Private inputs, outputs, keys and acceptance workspaces remain ignored.

A read-only follow-up passed **29 persistence checks** against the browser fixture. A separate final-code replay passed **10 checks** for exact second-occurrence UTF-16 selection, its first-version Draft/range/hash evidence, unchanged original text and unchanged graph, using a local test provider with zero external calls. The earlier browser revision fixture predates the final span-provenance addition and is not used as proof of that new field.

## Persistence and scope

Composition application is recoverable staged persistence, not a transaction across JSON and SQLite. Graph nodes and their creation events are atomically published first; draft batches and proposal receipts follow. A later failure returns an explicit retryable error. Retry requires full creation evidence and matching identities, types, ownership and payload; it cannot overwrite unrelated or partially evidenced nodes. JSON/memory backends are supported; Neo4j is rejected for this path until equivalent atomic graph application exists.

Source adoption and first-time proposal promotion use current-Draft compare-and-set checks. A stale suggestion cannot replace a draft saved while generation or review was underway. A new-scene proposal freezes even an empty baseline in its first version. Generated prose remains draft material; story facts still require their own canon review.

## Package and publication

The signed installer is **32,348,309 bytes**, SHA256 `53cd8e36afd6d8396a5c40a924b8b7516fe9075a5159d9b0a527bea40285e7cd`. Its Tauri updater signature verifies against the public key pinned by v0.1.15, and a one-byte tampered copy is rejected. `latest.json` version, signature and download URL match. Tauri updater signing is separate from Windows Authenticode signing.

The packaged backend matches the final sidecar byte for byte. Twelve runtime modules match current Python source semantics, two prompt files match byte for byte, and the new routes/schema are present. All seven embedded Web resources match the final distribution, including independent language catalogs. Native binary differences are limited to the expected three-byte NSIS bundle marker. The unchanged installer guard and lifecycle source match v0.1.15.

Independent checks scanned 4,126 decoded backend items, 21 installer-layer entries, and the changed/new source and documentation files against actual local credentials, encoded variants, high-confidence secret patterns and sensitive paths. No actual credential or private workspace file was found. Generic source candidates were documentation placeholders and synthetic fixtures. All 13 version locations agree on 0.1.16.

Software commit `510df35` and tag `v0.1.16` were synchronized to GitHub. The stable release contains exactly the installer, `.exe.sig` and `latest.json`. All three were downloaded again and matched the independently verified local files byte for byte; GitHub reports v0.1.16 as the latest non-draft, non-prerelease release. The running author application has not been replaced. Private novels, credentials and local acceptance fixtures were excluded.
