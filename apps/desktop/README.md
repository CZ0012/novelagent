# StoryGraph Desktop Shell

This directory contains the Tauri v2 desktop package for the StoryGraph Workbench.

## Current Status

The desktop shell is a buildable source-level Tauri project. It includes npm scripts, a Rust crate, Tauri capabilities, a sci-fi Windows icon, hidden backend sidecar packaging, backend process commands, Tauri signed-updater configuration, and NSIS bundle configuration.

It can produce a local Windows executable, updater artifacts, and NSIS installer. The generated `.exe`, backend sidecar, NSIS setup executable, and `setup.exe.sig` Tauri updater signature are local build outputs, not checked-in or published release artifacts.

Use the project through one of these surfaces:

- CLI workspace for persistent command-line authoring.
- FastAPI + React/Vite workbench for browser-based local authoring.
- Tauri desktop app for direct local use after a source build.
- Signed release channel for future end users after a GitHub Release publishes `latest.json`, installer assets, and updater signatures.

GitHub Release is only the software publishing and update-delivery channel. It is not a sync mechanism for local story workspaces, canon, drafts, imported documents, project settings, or review state.

## Runtime Behavior

The desktop shell hosts the same React UI built from `apps/web` and talks to the local FastAPI backend at `http://127.0.0.1:8000`.

On startup, the Rust shell:

- reads desktop settings from `%LOCALAPPDATA%\StoryGraph Agent\desktop-settings.json` on Windows, with user-home fallbacks on other platforms;
- defaults the workspace to `%LOCALAPPDATA%\StoryGraph Agent\workspace`;
- creates or reuses that persistent workspace without seeding demo canon automatically;
- checks `/health` on the configured backend URL;
- reuses an already-running local backend when it is healthy;
- otherwise starts the bundled `storygraph-backend` sidecar when present, falling back to `python -m apps.api.desktop_server` during source development;
- passes `STORYGRAPH_HOME` and `STORYGRAPH_GRAPH_BACKEND=json` to that backend process;
- starts the managed backend without showing a stray Windows console window;
- writes backend stdout/stderr logs under `%LOCALAPPDATA%\StoryGraph Agent\logs`.

The desktop commands are intentionally narrow: settings load/save, backend status, backend start, backend stop, local path reporting, and signed updater checks/install through Tauri's updater plugin. They do not write canon.

Inside the hosted workbench, the project tree comes from the backend `/projects` response. A fresh persistent desktop workspace should show project creation and explicit demo initialization options; UI fixture/sample data must not be treated as a real workspace.

Local document import remains a browser-memory reader by default. From the reader, an author can explicitly save a ready document as the current scene Draft Store draft, save it as a StyleSample Store style sample, or save it as a draft and then extract pending `CandidateFact` records. None of those paths directly writes Graph Store canon.

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
apps/desktop/src-tauri/target/release/bundle/nsis/StoryGraph Agent_0.1.0_x64-setup.exe
apps/desktop/src-tauri/target/release/bundle/nsis/StoryGraph Agent_0.1.0_x64-setup.exe.sig
```

If `build:with-web` fails before Tauri starts, fix the `apps/web` build first. The desktop package owns Tauri packaging and backend process orchestration; the React/Vite workbench remains owned by `apps/web`.

The backend sidecar is built with PyInstaller from `apps.api.desktop_server` using `--noconsole` and the app icon. The Rust shell also starts the backend process with Windows `CREATE_NO_WINDOW`. The generated sidecar and PyInstaller work directory are ignored by git.

## Version And Updates

The repository version source is `VERSION`. It must stay synchronized with:

- `pyproject.toml`
- `apps/web/package.json`
- `apps/web/src/version.ts`
- `apps/desktop/package.json`
- `apps/desktop/src-tauri/Cargo.toml`
- `apps/desktop/src-tauri/tauri.conf.json`

The settings panel includes a Chinese-localized `Version & Updates` card. In the Tauri runtime, it uses `@tauri-apps/plugin-updater` and `tauri-plugin-updater` to check the configured signed endpoint:

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

That entrypoint starts `apps.api.desktop:app`, uses a persistent StoryGraph workspace, defaults to the JSON graph backend, and does not seed canon automatically. Use the workbench `Seed Demo` action or `POST /demo/seed` when you want to explicitly initialize the bundled fantasy demo.

Agent settings persist with the backend workspace. Saving an API key only stores the credential reference; LLM drafting also requires selecting the LLM writing mode, saving settings, having `read_generate` or `full` permission, and running with a valid project, scene, and Context Pack.

## Boundary Rules

- The desktop layer must not write canon directly.
- Canon writes must still go through backend human seed APIs or CandidateFact review APIs.
- Generated drafts, summaries, imported text, sample UI data, and model hypotheses must not be promoted to canon by the desktop process.
- Web workbench sampleData/fixture previews must not be treated as the desktop workspace, Context Pack input, Draft Store source, CandidateFact evidence, or Graph Store state.
- Imported documents may become Draft Store drafts, StyleSample Store samples, or pending CandidateFacts only through explicit backend actions; review is still required before any extracted fact becomes canon.
- The Agent workflow run button follows `build_context`, `write_draft`, `check_continuity`, `extract_state`, and `human_review`; the review pause is not itself a canon commit.
- The desktop layer may orchestrate processes, settings, health checks, logs, workspace selection, and windows.
- The desktop layer may orchestrate signed updater checks and installation, but updater metadata must not be treated as story data.
- The desktop layer must not bypass `ReviewService`, `GraphStore`, or the versioned contracts under `contracts/`.

## Remaining Integration Work

- Add automated desktop smoke tests for start/connect, health reporting, workbench load, workspace persistence, and installer install/uninstall.
- Add automated updater-channel smoke tests against a test `latest.json` and signed fixture artifact.
