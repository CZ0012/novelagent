# v0.1.12 acceptance / 验收记录

Verified on Windows on 2026-09-13. This release improves the existing local CLI, API + Web, and Tauri desktop application. GitHub distributes software and signed updates; author workspaces remain local.

## Delivered behavior / 交付功能

- Everyday writing uses Write, Sources, Agent, and Proposals. Planning controls and advanced review tools are collapsible. The editor uses the available space and protects unsaved text when changing projects, scenes, connections, or refreshing.
- English and Simplified Chinese have separate dynamically loaded Web catalogs. English has no runtime dependency on the Chinese catalog. Native desktop labels and errors live in separate JSON resources. See [localization](localization.md) for adding languages.
- Workspace Agent presets can be created, edited, copied, selected, and deleted. Built-ins include concise Chinese writing with fewer adverbial phrases, balanced narrative, and precise English. Creative requests freeze the selected System prompt; language, structured output, canon, and review rules remain enforced.
- Provider settings use the configured third-party service. Model discovery shows that endpoint's identifiers without assuming an underlying vendor or changing the saved model. Connection/list success is distinct from a successful generation.
- Continue scene pins the saved Draft ID and appends new prose to the complete original in a reviewable Proposal. Draft export, Proposal export, revision history, exact baseline diff, and explicit adoption remain accessible.
- Explicit API workspaces now default to a persistent JSON graph. Structure application checks predictable ID conflicts before writing and supports a verified retry after a lost success response. Editor load/save responses cannot overwrite a different scene or newer local edits.

## Automated verification / 自动检查

| Check | Result |
| --- | --- |
| Python `python -m pytest -q` | 269 passed, 1 skipped |
| Python `python -m ruff check .` | Passed |
| Web `npm --prefix apps/web test` | 46 passed in 6 files |
| Web production build | Passed; separate zh-CN and en-US chunks |
| Rust `cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml --no-default-features` | 3 passed |
| Windows `npm --prefix apps/desktop run build:installer` | Passed; NSIS executable, updater signature, and latest.json produced |
| Packaged backend smoke test | v0.1.12 schema, healthy persistent JSON backend, isolated workspace, 3 built-in presets; hidden process |
| Updater artifact verification | Configured public-key signature valid; one-bit tamper rejected; release asset and original installer bytes identical |

The Python skip is the optional external Neo4j integration check. Dependency deprecation warnings do not represent failed tests.

## Browser verification / 界面检查

The production Web bundle was exercised against an isolated persistent backend:

- English reload requested the main bundle and only the English catalog. Language selection survived reload; Chinese story text was preserved when the interface changed to English.
- Chinese and English layouts were checked at desktop and narrow widths. At 1440 pixels the editor had 507 pixels of height; at a 390-pixel viewport the Chinese page had no horizontal overflow and retained a usable 280-pixel editor.
- A temporary custom preset was created, selected, reloaded, edited, then removed through the API. The built-in concise Chinese preset was restored. Provider settings and the original user workspace were preserved.
- The saved-draft manifest, continuation entry point, Proposal versions, exact original-draft diff, and cancelable unsaved-change guard were exercised. The browser backend address survived a reload.
- Text export was triggered without an application error and its download implementation was reviewed. The in-app browser did not report a completed download event, so downloaded-file bytes are not claimed as browser-verified.

## Real manuscript exercise / 真实原稿实测

A user-authorized Chinese DOCX chapter containing 1,755 characters was copied into an ignored, isolated local workspace. The original document was untouched. No manuscript title, prose, credential, or private filesystem path is included in the software release.

1. Imported the chapter, verified persistent storage and repeat-import idempotency, and confirmed import did not change graph canon.
2. Queried the configured third-party service's actual model list. The previously saved identifier was absent; test calls selected available identifiers only in the isolated test runtime.
3. Generated a structure Proposal using the endpoint identifier `deepseek-v3.2` in 28.58 seconds. A continuation attempt with that identifier exceeded the 120-second test timeout. No automatic fallback was performed by the application.
4. Explicitly selected the endpoint identifier `glm-5.3-flash` for the next test. It generated 1,229 continuation characters in 33.79 seconds under the concise Chinese preset.
5. Reviewed physical continuity and wording, then recorded a second Proposal version with 1,217 continuation characters. The complete original remained an exact prefix. The saved Draft was not overwritten, no CandidateFacts were created, and graph canon stayed unchanged.
6. Reopened the persistent stores and recovered the source, original Draft, and both Proposal versions. The selected preset ID and prompt hash were present in the creative result's provenance.

These are identifiers reported by the third-party endpoint, not verified claims about the underlying model vendor. Private generated text and the local acceptance scripts remain under ignored `.storygraph/acceptance/` for the author to inspect.

## Scope of evidence / 验证范围

This is a chapter-level import, generation, revision, and persistence exercise, not a whole-novel or extended autonomous-writing benchmark. Model preferences guide prose but do not guarantee literary quality; the actual continuation received an editorial revision.

The existing explicit review boundary remains: proposals and imported material cannot automatically become canon. Cross-store recovery from a hard crash or storage failure during structure application remains separate from the conflict preflight and completed-operation retry covered here. Rich-document import expansion and novel-scale chunking remain future work.

The 32,270,593-byte installer carries a verified Tauri updater signature. Its SHA256 is `9bcdecdfc94f69f762617b567391dc7a503a1082582842f9ed8b7b1637bc895b`. This is separate from Windows Authenticode signing; the current executable is not Authenticode-signed. The backend archive and NSIS file list were inspected: no author workspace, runtime credentials, private manuscripts, or acceptance scripts were bundled. Local build outputs are not a published update channel until the corresponding GitHub Release assets and signed `latest.json` are uploaded.

## 中文交付摘要

本次完成分层导航、中英独立语言资源、Agent System prompt 预设、第三方模型发现和精确原稿续写，并修复工作区持久化、编辑器异步覆盖和结构应用冲突问题。真实测试使用经授权的中文章节，生成并修订了 1,217 字符的续写候选稿，原稿和正典均未自动变更。测试文本与密钥仅留在本地；上述表格列出自动检查和安装包验证结果。
