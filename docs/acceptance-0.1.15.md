# v0.1.15 verification scope

This release fixes overly strict Windows update preparation and completes graph label localization. It also adds an explicit, reviewed repair flow for historical chapter/scene metadata that was generated in the wrong story language.

## Update preparation

The 0.1.13 native preparation path stopped the managed backend and immediately attempted an exclusive file probe. A transient Windows sharing violation could abort before the installer was launched. The new path retries only sharing/lock violations (32/33) for at most ten seconds; permanent errors fail immediately. Work runs off the UI thread. The installer retains its existing persistent-lock guard, and errors distinguish download, preparation, installation and recovery stages.

The reported error identifies a sharing violation in preparation, but does not establish which process held that earlier lock. A preliminary real PyInstaller onefile lifecycle run observed one immediate probe failure in ten runs before recovery; the instrumented final 35-run fixture completed successfully. A separate deterministic shared-reader test proves error 32 is retried after release and rejected when persistent. No broad process kill or forced file replacement was added.

Clients already blocked on the old one-shot check need a one-time manual bootstrap: save work, quit StoryGraph through its tray menu, and install the latest signed release in the existing directory. They do not need to uninstall or remove their novel workspace. This release was not installed over the author's running application during testing.

## Graph and outline language

All 12 known graph node types and 27 relationship types have separate Chinese/English display labels. Unknown custom labels and author content remain unchanged. Switching the interface does not translate historical prose or metadata.

The new outline repair action sends only eligible chapter/scene metadata to the configured provider, then creates a strict `outline_language_patch_v1` Proposal. The author sees a field-by-field comparison, submits it for review, accepts it, and explicitly applies it. The server checks the stored baseline, project language, allowed fields, ownership, proposal version and status. It stages graph changes and provenance atomically and supports idempotent retry and receipt recovery. Drafts, sources, stable IDs, relations and character facts are excluded. Neo4j is rejected until an equivalent atomic application path exists.

A complete Markdown JSON fence from compatible third-party services is accepted only when the entire response contains that one fence; prose, multiple blocks and malformed data remain rejected. Provider failures have safe actionable categories and never silently change the selected model or trigger a paid retry. Language validation remains conservative and cannot establish translation quality for every proper name.

## Validation

- Python: **377 passed / 1 skipped**, including 60 outline-repair tests covering review/permission boundaries, stale data, malformed input, atomic persistence, retries and concurrent application.
- Web: **75 tests**, TypeScript and production build passed. Chinese and English catalogs remain independent production chunks.
- Native: **11 Rust tests** and formatting passed, including transient/persistent lock behavior and missing-file failure.
- Installer guard: **5 real NSIS checks** passed: production guard order, unlocked and missing-backend update, persistent-lock refusal preserving both old binaries, and exact-path process scope preserving an unrelated process.
- Packaged lifecycle: **35 real PyInstaller parent/worker exits** passed using the maintained isolated fixture. The fixture calls the production process-stop/probe code and never touches the installed author application.

Production-browser acceptance used an isolated synthetic project: an unsaved draft blocked generation until saved; 13 metadata revisions remained non-canon through generation and acceptance; explicit application updated outline, graph and timeline together. The saved draft remained byte-for-byte unchanged, node IDs and relationships remained stable, and three provenance events were written. Final Chinese/English checks confirmed the disabled applied state, localized reference labels and folded advanced controls. The comparison tables remained readable at widths 1080 and 900 without horizontal overflow.

The authorized private novel test used isolated copies of its graph and provider settings. The originally configured model identifier returned HTTP 404 and was absent from the provider's current listing. Only the test copy was switched to the provider-listed `glm-5.3-flash`. One successful real response generated 29 revisions across nine chapter/scene nodes. After adding strict full-fence compatibility, that exact recorded response was replayed through generation, acceptance, application and retry without another paid call. Review boundaries, unchanged IDs/relationships, idempotency, and unchanged hashes of the original graph/settings were verified. The provider identifier does not verify the underlying model vendor. Private text, keys and test responses are excluded from publication.

## Package and publication

The 32,307,882-byte installer has SHA256 `f164766c50c7ea54115dd37289e72db0d8439d4db68b957e579ddd078f458130`. Its Tauri updater signature verifies against the same pinned public key used by v0.1.14; a one-byte tampered copy is rejected. The updater metadata signature, version and download URL match. Tauri signing is separate from Windows Authenticode signing.

The installer backend matches the final sidecar byte for byte; five relevant Python modules match current source semantics. All seven embedded Web resources match the final distribution and HTML asset URLs, including independent Chinese/English catalogs. Native binary differences from the build are limited to Tauri's expected three-byte NSIS bundle marker. The packaged installer guard matches the unchanged source hooks.

The 54 changed/new source and documentation files, 21 installer-level entries and 4,123 decoded backend items were checked against actual local credential values, encoded forms, sensitive paths and high-confidence secret patterns. No actual credential or private workspace file was found. Generic source candidates were documentation and synthetic test placeholders. Private test inputs and provider responses remain in ignored local directories.

Software commit `7715712` and tag `v0.1.15` were synchronized to GitHub. The stable release contains exactly the installer, `.exe.sig` and `latest.json`. All three were downloaded again and matched the verified local files byte for byte; GitHub reports v0.1.15 as the latest non-draft, non-prerelease release. Novel workspaces, credentials and private acceptance fixtures were excluded. The running local application was left untouched; older clients blocked by preparation should use the one-time manual recovery described above.
