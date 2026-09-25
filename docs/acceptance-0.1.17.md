# 0.1.17 acceptance: task models, protocols and imports

This release preserves the manuscript workspace and adds named model connections with explicit planning, writing, revision, discussion and extraction assignments. Unassigned tasks inherit the existing default. Chat Completions, Responses and Anthropic Messages are selected per connection; model identifiers are never inferred from a vendor name.

## Verification

- Backend full regression: 460 passed, one optional integration skipped. Subsequent error-classification, damaged-config privacy and explicit-planning-connection guards passed their focused 81- and 51-test runs. Rule-based output clears prior model attribution; manual review preserves original model provenance.
- Frontend: 199 tests, production build and TypeScript checks passed. Profile payloads preserve blank keys, explicitly clear keys, reject invalid references, and protect settings from stale loads and backend switching.
- Independent review found and fixed unsafe URL error echo, obsolete model attribution after rule-based regeneration, and silent rule fallback for an explicitly assigned incomplete planning connection. Provider/config snapshots, strict completion validation, and legacy settings migration passed independent no-network checks.
- RTF private-fixture verification: all 62 non-temporary documents parsed successfully, totaling 153,678 characters, including 126,882 CJK characters, with no replacement characters. Original files were only read. Synthetic committed fixtures cover Unicode, Chinese code pages, skipped destinations, hidden/deleted text, malformed input and resource limits.
- The reported DOCX was independently verified to have zero bytes on disk, with the empty SHA-256 matching its stored import record. It contains no document payload for the importer to recover. Both new imports and legacy zero-byte records show the specific localized explanation. Office temporary files beginning with `~$` are skipped.
- Production-browser checks used an isolated synthetic workspace: task assignments saved correctly; Chinese/English UI remained independent; mixed RTF, empty DOCX and temporary-file import produced one readable RTF, one precise failed-file record and one skip. No browser console errors were observed during that import.

## Authorized third-party verification

All paid calls used the author's existing third-party endpoint and exact configured model identifier `claude-opus-4-6`; no alternate model was substituted. Each protocol returned completed text and the same reported model identifier in bounded synthetic probes. This verifies compatibility with the tested endpoint, not independent proof of the upstream model vendor.

A Responses continuation on an isolated copy of a prior novel-writing acceptance draft succeeded and appended 394 characters while preserving the complete baseline. Its persisted execution snapshot named the writing role, Responses protocol and exact model identifier. Original author settings, graph, sources and drafts remained unchanged.

Two task outputs were rejected because the provider returned invalid JSON containing unescaped quotes: an initial Responses continuation and an Anthropic revision. After explicit JSON-serialization guidance was added, the separate Responses acceptance succeeded. Anthropic transport completed, but this revision did not produce an accepted proposal. Cached-response replay against final code verifies `model_output_invalid`, no draft overwrite and no canon write. There are no automatic paid retries or permissive JSON repairs. Nine paid calls were made in total: six bounded protocol probes and three workflow calls. Private prompts, generated prose, source files, credentials and endpoint addresses remain in ignored local acceptance storage only.

## Boundaries

Responses sends `store: false`; Anthropic uses its native Messages headers and system field. These are synchronous text adapters. They do not enable hosted tools, cloud memory or response-ID continuation. Strict local JSON validation still applies, even when a service accepts a JSON preference. Quality/continuity checking remains rule-based; planning a new chapter/volume and its initial prose is one planning task.

RTF is imported as text and paragraph breaks. Formatting, embedded objects and images are not rendered. PDF/OCR remain unsupported. Neither imports nor generated proposals directly mutate canon. No update automatically reimports historical files or changes task assignments.

## Package verification

The final installer was statically unpacked and independently audited; it was not executed or installed. Its backend matches all 24 audited Python source modules, its production Web assets match the final build, and its updater guard matches source. Tauri signature verification passed and a tampered copy was rejected; the public key is unchanged from 0.1.16. Credential and private-path scans found no matches in the installer, embedded assets or 4,127 backend items. Native update lifecycle/guard source is unchanged from the previously verified release.

- Installer: `StoryGraph.Agent_0.1.17_x64-setup.exe`
- Bytes: 32364963
- SHA-256: `985088c16d601550e5cc87fe66112a4133c0d5b9476903c9653e449248fb2096`
- Tauri updater signing is separate from Windows Authenticode signing.

GitHub publication and re-download verification are pending. The author installation and workspaces remain untouched.
