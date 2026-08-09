# StoryGraph Desktop Shell

This directory contains the Tauri v2 desktop package for the StoryGraph Workbench.

## Current Status

The desktop shell is a buildable source-level Tauri project. It includes npm scripts, a Rust crate, Tauri capabilities, a sci-fi Windows icon, hidden backend sidecar packaging, backend process commands, system-tray lifecycle handling, Tauri signed-updater configuration, and NSIS bundle configuration.

It can produce a local Windows executable, updater artifacts, and NSIS installer. The generated `.exe`, backend sidecar, NSIS setup executable, and `setup.exe.sig` Tauri updater signature are local build outputs, not checked-in or published release artifacts.

## 中文优先与本地化入口

桌面包复用 `apps/web` 构建出的同一个 React 工作台。SG-019 语言边界由 `contracts/language_policy_v1.md` 定义：`ui_locale` 只支持 `zh-CN` / `en-US`、默认 `zh-CN`，以版本化本地 Web/Tauri 偏好持久化；`Project.language` 则是后端项目正文与 Agent 输出语言。两者独立，不能互相覆盖。

本地化文案属于显示层。它不得写入 Graph Store、Source Store、Draft Store、Context Pack、CandidateFact、Proposal Artifact、Workflow Store 或 Event Log，也不放入 `/settings/agent`。原生窗口、托盘与 updater 文案可以镜像本地 UI locale，但不得改变项目语言。桌面 UI 默认中文优先；英文资源、切换控件和四组合验证必须与后端语言快照一起通过，才能宣告 SG-019 完成。

Use the project through one of these surfaces:

- CLI workspace for persistent command-line authoring.
- FastAPI + React/Vite workbench for browser-based local authoring.
- Tauri desktop app for direct local use after a source build.
- Signed release channel for future end users after a GitHub Release publishes `latest.json`, installer assets, and updater signatures.

GitHub Release is only the software publishing and update-delivery channel. It is not a sync mechanism for local story workspaces, Source Store documents, canon, drafts, project settings, or review state.

## Runtime Behavior

The desktop shell hosts the same React UI built from `apps/web` and talks to the local FastAPI backend at `http://127.0.0.1:8000`.

On startup, the Rust shell:

- reads desktop settings from `%LOCALAPPDATA%\StoryGraph Agent\desktop-settings.json` on Windows, with user-home fallbacks on other platforms;
- defaults the workspace to `%LOCALAPPDATA%\StoryGraph Agent\workspace`;
- creates or reuses that persistent workspace without seeding demo canon automatically;
- checks `/health` on the configured backend URL;
- reuses an already-running local backend only when it is healthy and its `/health` workspace matches the configured desktop workspace;
- reports a clear settings-panel conflict when the configured URL is occupied by a backend from another workspace;
- otherwise starts the bundled `storygraph-backend` sidecar when present, falling back to `python -m apps.api.desktop_server` during source development;
- passes `STORYGRAPH_HOME` and `STORYGRAPH_GRAPH_BACKEND=json` to that backend process;
- starts the managed backend without showing a stray Windows console window;
- writes backend stdout/stderr logs under `%LOCALAPPDATA%\StoryGraph Agent\logs`.
- keeps a system tray icon while running; closing the main window hides it to the tray instead of exiting;
- treats the tray menu item `退出 StoryGraph Agent` as the real app exit path, stopping only the backend process tree that this desktop shell started before exiting.

The desktop commands are intentionally narrow: settings load/save, backend status, backend start, backend stop, local path reporting, and signed updater checks/install through Tauri's updater plugin. They do not write canon.

Inside the hosted workbench, the project tree comes from the backend `/projects` response. A fresh persistent desktop workspace should show project creation and explicit demo initialization options; frontend placeholders must not be treated as a real workspace. If the bundled demo has already been initialized, the workbench can archive that built-in demo so the project tree returns to an empty author workspace.

Local document import uses the same project-scoped FastAPI Source Store in browser and Tauri runtimes. The local client extracts supported `.txt`, `.md`, `.markdown`, and `.docx` content and submits each file separately with its metadata. Every Source Document has a stable ID and persists under the desktop workspace across backend/app restarts. Import results remain visible per file, summary lists omit full `extracted_text`, detail is loaded only on demand, and archive is non-destructive. Import/read/archive changes Source Store only; it does not create Drafts, CandidateFacts, graph nodes, graph relations, or canon events.

Source language is independent BCP 47 metadata. `und` is never eligible for Agent or structure prompts. Language mismatches are rejected by default; `explicit_reference` requires a known language plus an explicit stable-source selection, does not translate the source, and does not change the server-derived project output language. Legacy inline/structure text requests without valid source language fail with `422`.

RTF, PDF, OCR, images, and PSD are not supported by the initial Source Store. They are later importer work and must be shown as skipped/failed rather than silently treated as successful text imports. A ready Source Document may be analyzed through the source-backed structure route, but that action creates only a non-canon `project_structure_draft`; Chapter/Scene creation still requires explicit author acceptance and apply.

The hosted workbench includes `协作草稿箱`, backed by the same FastAPI Proposal Store routes used in the browser. Proposal artifacts are non-canon project data: accepting one does not write canon, and promotion to Draft Store or pending CandidateFacts still goes through backend permission and review boundaries.

The hosted workbench also includes the `Agent` discussion tab. Source Store documents are unselected by default. Only documents the author explicitly selects are sent as stable `source_document_ids`; the backend resolves ready text inside the same project. It must not automatically send the whole library or cached snippets, and disabling current-draft inclusion must also omit editor text from `base_text`. Optional web search remains a separate explicit choice. The result is saved only as a Proposal Store `scene_rebuild` or `scene_draft` artifact; it does not overwrite Draft Store, create CandidateFacts, or write Graph Store canon.

## Build Commands

Install desktop dependencies:

```powershell
npm --prefix apps/desktop install
```

Build with the existing `apps/web/dist` assets:

```powershell
npm --prefix apps/desktop run build
```

Build the full installer after rebuilding the web assets:

```powershell
npm --prefix apps/desktop run build:installer
```

`build:installer` creates updater artifacts and requires a Tauri updater signing key. This workspace uses `apps/desktop/.tauri/storygraph-agent.key`, which is ignored by git. Release machines should set `TAURI_SIGNING_PRIVATE_KEY` or `TAURI_SIGNING_PRIVATE_KEY_PATH` to the private key that matches the public key in `src-tauri/tauri.conf.json`. If the updater key changes, rotate the committed public key and release process together.

Build only the backend sidecar:

```powershell
npm --prefix apps/desktop run build:backend
```

Run Tauri build without regenerating the backend sidecar:

```powershell
npm --prefix apps/desktop run build:tauri-only
```

Rebuild the web assets explicitly:

```powershell
npm --prefix apps/desktop run build:web
```

Run a full web rebuild followed by Tauri build:

```powershell
npm --prefix apps/desktop run build:with-web
```

Run Tauri development mode:

```powershell
npm --prefix apps/desktop run dev
```

`npm --prefix apps/desktop run build:installer` was verified in this workspace and produced:

```text
apps/desktop/src-tauri/binaries/storygraph-backend-x86_64-pc-windows-msvc.exe
apps/desktop/src-tauri/target/release/storygraph-backend.exe
apps/desktop/src-tauri/target/release/storygraph-agent-desktop.exe
apps/desktop/src-tauri/target/release/bundle/nsis/StoryGraph Agent_0.1.9_x64-setup.exe
apps/desktop/src-tauri/target/release/bundle/nsis/StoryGraph Agent_0.1.9_x64-setup.exe.sig
apps/desktop/src-tauri/target/release/bundle/nsis/StoryGraph.Agent_0.1.9_x64-setup.exe
apps/desktop/src-tauri/target/release/bundle/nsis/StoryGraph.Agent_0.1.9_x64-setup.exe.sig
apps/desktop/src-tauri/target/release/bundle/nsis/latest.json
```

If `build:with-web` fails before Tauri starts, fix the `apps/web` build first. The desktop package owns Tauri packaging and backend process orchestration; the React/Vite workbench remains owned by `apps/web`.

The backend sidecar is built with pinned PyInstaller 6.21.0 from `apps.api.desktop_server` using `--noconsole`, the app icon, and explicit data-file inclusion for `storygraph/prompts` plus `storygraph/localization`. The Rust shell also starts the backend process with Windows `CREATE_NO_WINDOW`. The generated sidecar and PyInstaller work directory are ignored by git.

## Version And Updates

The repository version source is `VERSION`. It must stay synchronized with:

- `pyproject.toml`
- the FastAPI version in `apps/api/main.py`
- `apps/web/package.json` and its root `package-lock.json` entry
- `apps/web/src/version.ts`
- `apps/desktop/package.json` and its root `package-lock.json` entry
- `apps/desktop/src-tauri/Cargo.toml`
- the `storygraph-agent-desktop` entry in `apps/desktop/src-tauri/Cargo.lock`
- `apps/desktop/src-tauri/tauri.conf.json`

The settings panel includes a zh-CN/en-US localized `Version & Updates` card. In the Tauri runtime, it uses `@tauri-apps/plugin-updater` and `tauri-plugin-updater` to check the configured signed endpoint:

```text
https://github.com/CZ0012/novelagent/releases/latest/download/latest.json
```

When a signed update is available, the UI can stop the managed backend, download and install the update, and restart the app. In a plain browser runtime, the UI falls back to a GitHub Release check and links to the Windows installer asset when one exists.

For published updates, the GitHub Release must include the NSIS setup executable, the matching `setup.exe.sig` Tauri updater signature, and a valid `latest.json` matching Tauri's static JSON format. Source-built local outputs, updater artifacts, and a published signed release channel are separate states. Do not document a `nsis.zip` artifact unless the build actually produces one.

Tauri updater signing is separate from Windows Authenticode code signing. The updater signature lets the app verify and install a release through the configured endpoint; Authenticode signing is still required separately for production Windows trust prompts and publisher identity.

## Icon Assets

The desktop icon lives under `src-tauri/icons/`:

- `icon.ico`: Windows/Tauri/PyInstaller icon.
- `icon-1024.png`: source preview image.

Regenerate both with:

```powershell
python apps\desktop\scripts\generate-icon.py
```

The icon generator uses only the Python standard library and should not add image-generation or raster dependencies to the project.

## Backend Command

Run the persistent desktop-target backend directly:

```powershell
python -m apps.api.desktop_server
```

That entrypoint starts `apps.api.desktop:app`, uses a persistent StoryGraph workspace, defaults to the JSON graph backend, and does not seed canon automatically. The workbench should guide authors to create a project, persist an existing manuscript in the project Source Store, explicitly run source-backed structure analysis to create a non-canon `project_structure_draft`, and apply it only after author review. Use `POST /demo/seed` only when you want to explicitly initialize the bundled fantasy demo for development/onboarding, and use `POST /demo/archive` or the workbench demo removal action to archive the built-in demo without touching real author-created projects.

Agent settings persist with the backend workspace. Saving the permission level in the Web or desktop settings panel is treated as explicit local operator authorization, so it can lower or raise the backend `permission_level` immediately. Canon-changing routes still require `full` permission plus reviewer/rationale/source provenance, and generated or imported facts still go through CandidateFact review. Saving an API key only stores the credential reference; LLM drafting also requires selecting the LLM writing mode, saving settings, having `read_generate` or `full` permission, and running with a valid project, scene, and Context Pack.

## Boundary Rules

- The desktop layer must not write canon directly.
- Canon writes must still go through backend human seed APIs or CandidateFact review APIs.
- Generated drafts, summaries, proposal artifacts, imported text, frontend placeholders, and model hypotheses must not be promoted to canon by the desktop process.
- Web workbench graph/timeline previews must come from backend APIs and must not be treated as the desktop workspace, Context Pack input, Draft Store source, CandidateFact evidence, or Graph Store state unless the backend returned them.
- Source Store import, retry, detail, list, and archive operations must not create Proposal Store artifacts, Draft Store drafts, StyleSample Store samples, CandidateFacts, graph data, or events. Source-backed structure analysis is the explicit exception that may create only a `project_structure_draft` proposal.
- Import does not implicitly create Drafts or CandidateFacts. A separate author action may save a loaded ready detail through the normal Draft, Proposal, or Style Sample route; any fact flow still requires a real Draft Store source plus pending CandidateFact review provenance before canon can change.
- Agent discussion and selected-text rewrite output may become Proposal Store artifacts only; accepting and promoting an accepted proposal is still the explicit backend path before Draft Store changes.
- The Agent workflow run button follows `build_context`, `write_draft`, `check_continuity`, `extract_state`, and `human_review`; the review pause is not itself a canon commit.
- The desktop layer may orchestrate processes, settings, health checks, logs, workspace selection, and windows.
- UI locale remains a local client preference and never becomes project/runtime story data. The four `ui_locale × Project.language` combinations must preserve independent UI and Agent-output behavior.
- The desktop layer may orchestrate signed updater checks and installation, but updater metadata must not be treated as story data.
- The desktop layer must not bypass `ReviewService`, `GraphStore`, or the versioned contracts under `contracts/`.

## Remaining Integration Work

- Add automated desktop smoke tests for start/connect, health reporting, workbench load, workspace persistence, and installer install/uninstall.
- Add automated updater-channel smoke tests against a test `latest.json` and signed fixture artifact.
