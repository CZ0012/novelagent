# StoryGraph Desktop Shell

This directory contains the Tauri v2 desktop package for the StoryGraph Workbench.

## Current Status

The desktop shell is a buildable source-level Tauri project. It includes npm scripts, a Rust crate, Tauri capabilities, a Windows icon, backend sidecar packaging, backend process commands, and NSIS bundle configuration.

It can produce a local Windows executable and NSIS installer. The generated `.exe`, backend sidecar, and installer are local build outputs, not checked-in or signed release artifacts.

Use the project through one of these surfaces:

- CLI workspace for persistent command-line authoring.
- FastAPI + React/Vite workbench for browser-based local authoring.
- Tauri desktop app for direct local use after a source build.

## Runtime Behavior

The desktop shell hosts the same React UI built from `apps/web` and talks to the local FastAPI backend at `http://127.0.0.1:8000`.

On startup, the Rust shell:

- reads desktop settings from `%LOCALAPPDATA%\StoryGraph Agent\desktop-settings.json` on Windows, with user-home fallbacks on other platforms;
- defaults the workspace to `%LOCALAPPDATA%\StoryGraph Agent\workspace`;
- checks `/health` on the configured backend URL;
- reuses an already-running local backend when it is healthy;
- otherwise starts the bundled `storygraph-backend` sidecar when present, falling back to `python -m apps.api.desktop_server` during source development;
- passes `STORYGRAPH_HOME` and `STORYGRAPH_GRAPH_BACKEND=json` to that backend process;
- writes backend stdout/stderr logs under `%LOCALAPPDATA%\StoryGraph Agent\logs`.

The desktop commands are intentionally narrow: settings load/save, backend status, backend start, backend stop, and local path reporting. They do not write canon.

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
```

If `build:with-web` fails before Tauri starts, fix the `apps/web` build first. The desktop package owns Tauri packaging and backend process orchestration; the React/Vite workbench remains owned by `apps/web`.

The backend sidecar is built with PyInstaller from `apps.api.desktop_server`. The generated sidecar and PyInstaller work directory are ignored by git.

## Backend Command

Run the persistent desktop-target backend directly:

```powershell
python -m apps.api.desktop_server
```

That entrypoint starts `apps.api.desktop:app`, uses a persistent StoryGraph workspace, defaults to the JSON graph backend, and does not seed canon automatically. Use the workbench `Seed Demo` action or `POST /demo/seed` when you want to explicitly initialize the bundled fantasy demo.

## Boundary Rules

- The desktop layer must not write canon directly.
- Canon writes must still go through backend human seed APIs or CandidateFact review APIs.
- Generated drafts, summaries, imported text, sample UI data, and model hypotheses must not be promoted to canon by the desktop process.
- The desktop layer may orchestrate processes, settings, health checks, logs, workspace selection, and windows.
- The desktop layer must not bypass `ReviewService`, `GraphStore`, or the versioned contracts under `contracts/`.

## Remaining Integration Work

- Wire the React settings UI to Tauri commands for backend status, workspace path, and desktop process controls. Model provider, API key reference, writer mode, and permission level are currently managed through the backend `/settings/agent` API.
- Add automated desktop smoke tests for start/connect, health reporting, workbench load, workspace persistence, and installer install/uninstall.
- Replace the minimal generated icon with final product artwork.
