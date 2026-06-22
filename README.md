# StoryGraph Agent

StoryGraph Agent is a local MVP for long-form fiction workflows built around structured canon, draft isolation, human review, graph retrieval, and continuity checks.

Chinese documentation is available in [README.zh-CN.md](README.zh-CN.md).

The implementation follows:

- `docs/architecture.md`
- `contracts/graph_store_v1.md`
- `contracts/context_pack_v1.md`
- `contracts/candidate_fact_v1.md`
- `contracts/continuity_report_v1.md`
- `contracts/workflow_run_v1.md`
- `contracts/review_payload_v1.md`
- `contracts/style_sample_store_v1.md`
- `contracts/proposal_artifact_v1.md`

## Current MVP Capabilities

- Pydantic contract models for graph state, context packs, candidate facts, drafts, workflow runs, review payloads, style samples, and continuity reports.
- Canon-safe graph stores with explicit provenance and event log entries, including the local JSON graph backend and optional Neo4j backend.
- SQLite stores for drafts, proposal artifacts, candidate facts, workflow runs, and deterministic local style samples.
- Context Pack builder with P0-P7 budgeting metadata, graph and draft provenance, retrieved style samples, and `missing_context` gap reports.
- Rule-based scene writer, optional OpenAI-compatible LLM scene writer, rule-based continuity checker, and rule-based candidate fact extractor.
- Review service that keeps generated `CandidateFact` records pending until a human accept, edit-accept, reject, or defer decision.
- Human seed paths for story-bible Characters, Locations, and graph relationships. These write canon only when the user supplies reviewer, rationale, source reference, and provenance.
- Read-only graph query API and CLI commands for inspecting canon neighbors and relationships.
- Local CLI workspace commands for context building, scene drafting, continuity checks, state extraction, workflow runs, and pending fact review.
- Workflow run checkpoints and projections with API run listing, run event inspection, review-pause resume, proposal-output runs, persisted stores, and optional LangGraph runtime/checkpointer support.
- FastAPI routes for the authoring workflow plus persisted agent settings for model provider, API key reference, JSON mode, scene writer mode, and API permission level.
- Chinese-localized React/Vite author workbench for real API-backed project trees, empty-workspace onboarding, scene drafting, Proposal Workspace collaboration, Context Pack inspection, continuity QA, workflow events, graph/timeline preview, pending fact review, local txt/md/docx file or folder import, agent settings, and update checks through the API or desktop shell.
- Desktop-target FastAPI entrypoint (`apps.api.desktop_server`) that uses a persistent local workspace and the JSON graph backend.
- Buildable Tauri desktop package under `apps/desktop`, including npm scripts, a Rust entrypoint, hidden PyInstaller backend sidecar packaging, backend start/stop/status commands, system-tray lifecycle handling, Tauri capabilities, signed-updater configuration, a sci-fi app icon, and NSIS installer configuration.
- Fantasy demo fixture and regression tests for the canon safety loop.

## Runtime Status

This MVP can be used through CLI, browser, or a locally built Windows desktop package. The repository does not check in signed release binaries, but `apps/desktop` can build a local Tauri executable and NSIS installer. The desktop package is configured for Tauri signed updater artifacts, while published update delivery still depends on a GitHub Release that provides the installer, updater signatures, and `latest.json`.

Use one of these surfaces:

- CLI workspace: best for persistent local MVP runs. It stores JSON and SQLite state under `.storygraph`, `STORYGRAPH_HOME`, or the directory passed with `--workspace`.
- Persistent FastAPI + React/Vite workbench: best for local authoring and real API demonstrations through the browser. Start the persistent API backend and the web dev server separately. It reads the real project tree from `/projects`; frontend fixtures are not treated as a workspace.
- Explicit seeded demo mode: useful only for quick UI experiments or regression checks. The default `apps.api.main:app` uvicorn entrypoint uses in-memory stores and a bundled fantasy seed unless created with explicit settings, so it is not the real local authoring path.
- Tauri desktop app: best for direct local use after a source build. It hosts the React workbench, starts or connects to the local FastAPI backend without showing a backend console window, keeps the app running in the system tray when the main window is closed, and can check signed desktop updates from the configured release channel.

All examples below are PowerShell commands. They also work in Windows PowerShell unless your local execution policy, Python launcher, or Node installation differs.

## Install For Local Development

Install the Python package with development dependencies:

```powershell
python -m pip install -e ".[dev]"
```

Install web dependencies:

```powershell
npm --prefix apps/web install
```

Optional extras:

```powershell
python -m pip install -e ".[neo4j]"
python -m pip install -e ".[langgraph]"
```

After installation, either run `python -m apps.cli.main ...` or use the `storygraph` console script.

## Start The Web Workbench

For persistent local authoring, start the desktop-target backend:

```powershell
$env:STORYGRAPH_HOME="D:\storygraph-workspaces\demo"
python -m apps.api.desktop_server
```

Run those commands in one PowerShell terminal. If `STORYGRAPH_HOME` is not set, the desktop-target backend uses `%LOCALAPPDATA%\StoryGraph Agent\workspace` on Windows when available, or the user home directory fallback. It creates the workspace directory and uses the JSON graph backend. It does not silently seed demo canon; an empty persistent or desktop workspace should show project creation and explicit demo initialization options. Click `Seed Demo` in the workbench or call `POST /demo/seed` only when you want to initialize the bundled fantasy demo. If the demo was already initialized, use the workbench demo removal action or call `POST /demo/archive` to archive the Old Bell Tower demo from the current project tree.

For a quick seeded in-memory API for development experiments only, run:

```powershell
python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
```

Start the React/Vite workbench in another PowerShell terminal:

```powershell
npm --prefix apps/web run dev
```

Open `http://127.0.0.1:5173` and point the API field at `http://127.0.0.1:8000`.

Build the web workbench assets with:

```powershell
npm --prefix apps/web run build
```

## Desktop Install And Build

Current desktop-related files are:

- `apps/api/desktop.py`: persistent FastAPI app factory for a desktop-hosted runtime. It selects a local workspace and uses the JSON graph backend without automatic canon seeding.
- `apps/api/desktop_server.py`: local server entrypoint for that persistent API.
- `apps/desktop/package.json`: npm scripts for Tauri development, backend sidecar generation, and build.
- `apps/desktop/scripts/build-backend-sidecar.ps1`: Windows PowerShell script that packages `apps.api.desktop_server` as the Tauri backend sidecar.
- `apps/desktop/scripts/build-installer.ps1`: Windows PowerShell script that rebuilds web assets, rebuilds the backend sidecar, and runs the signed Tauri installer build.
- `apps/desktop/scripts/prepare-release-assets.ps1`: Windows PowerShell script that copies no-space GitHub Release asset names and writes the current-version `latest.json`.
- `apps/desktop/scripts/generate-icon.py`: dependency-free icon generator for the sci-fi app icon source PNG and `.ico` file.
- `apps/desktop/src-tauri/Cargo.toml` and `src/main.rs`: Rust shell with commands for desktop settings, backend status, backend start, backend stop, local path reporting, and tray minimize/quit lifecycle.
- `apps/desktop/src-tauri/capabilities/default.json`: Tauri v2 capability boundary for the main window.
- `apps/desktop/src-tauri/tauri.conf.json`: Tauri configuration pointing at `apps/web`, an NSIS bundle target, and the signed updater endpoint.

Build and run locally:

```powershell
npm --prefix apps/desktop install
npm --prefix apps/desktop run build:installer
```

`build:installer` creates updater artifacts and therefore requires a Tauri updater signing key. This workspace keeps the local private key in `apps/desktop/.tauri/storygraph-agent.key`, which is ignored by git. For a new release machine, provide `TAURI_SIGNING_PRIVATE_KEY` or `TAURI_SIGNING_PRIVATE_KEY_PATH` for the private key that matches the public key committed in `apps/desktop/src-tauri/tauri.conf.json`. If the updater key is intentionally rotated, update the committed public key and release process together.

The generated installer is:

```text
apps/desktop/src-tauri/target/release/bundle/nsis/StoryGraph Agent_0.1.5_x64-setup.exe
```

Other useful desktop commands:

```powershell
npm --prefix apps/desktop run build:backend
npm --prefix apps/desktop run build:installer
npm --prefix apps/desktop run build:tauri-only
npm --prefix apps/desktop run build:web
npm --prefix apps/desktop run build:with-web
npm --prefix apps/desktop run dev
```

Verified local build output from `npm --prefix apps/desktop run build:installer`:

```text
apps/desktop/src-tauri/binaries/storygraph-backend-x86_64-pc-windows-msvc.exe
apps/desktop/src-tauri/target/release/storygraph-backend.exe
apps/desktop/src-tauri/target/release/storygraph-agent-desktop.exe
apps/desktop/src-tauri/target/release/bundle/nsis/StoryGraph Agent_0.1.5_x64-setup.exe
apps/desktop/src-tauri/target/release/bundle/nsis/StoryGraph Agent_0.1.5_x64-setup.exe.sig
```

The full installer build regenerates the PyInstaller backend sidecar with `--noconsole`, rebuilds the React/Vite workbench, and runs `tauri build`. The Tauri shell also starts the sidecar with Windows `CREATE_NO_WINDOW`, so the packaged app should not show a stray backend terminal window. Closing the main desktop window hides it to the system tray; use the tray menu item `退出 StoryGraph Agent` to stop the managed backend process tree and exit the app. If port 8000 already has a healthy backend with a different workspace, the desktop settings panel reports the conflict instead of treating that process as the current desktop workspace. The generated installer, `setup.exe.sig` updater signature, backend sidecar, and release executables are local outputs, not checked-in release artifacts.

The in-app settings panel includes a `Version & Updates` section. In the Tauri desktop runtime it uses `tauri-plugin-updater` to check the signed endpoint `https://github.com/CZ0012/novelagent/releases/latest/download/latest.json`, stop the managed backend, install the update, and restart the app. In a plain browser runtime it falls back to a GitHub Release check and, when available, links to the Windows installer asset.

Version updates must keep `VERSION`, `pyproject.toml`, `apps/web/package.json`, `apps/web/src/version.ts`, `apps/desktop/package.json`, `apps/desktop/src-tauri/Cargo.toml`, and `apps/desktop/src-tauri/tauri.conf.json` synchronized. GitHub usage here is only the software release/update channel; local story workspaces, canon, drafts, imported documents, project settings, and review state are not synchronized to GitHub.

For the verified Windows build, the updater-relevant local artifacts are the NSIS setup executable and its Tauri updater signature, `StoryGraph Agent_0.1.5_x64-setup.exe.sig`. Do not document a `nsis.zip` updater artifact unless the build output changes. This Tauri updater signature is separate from Windows Authenticode code signing; production Authenticode signing for the sidecar and installer is still a separate release step.

What is still missing or unverified:

- Automated desktop smoke tests for install, uninstall, backend health, workbench load, and workspace persistence.
- Production Authenticode code signing for the generated backend sidecar and installer.

The packaged desktop runtime must host the same React workbench, start or connect to the local FastAPI backend, persist workspace settings, and continue using backend review APIs for all canon-changing operations. The desktop layer must not write canon directly.

## Local CLI Workspace

Initialize a persistent workspace. By default, the CLI uses `.storygraph` under the current directory; set `STORYGRAPH_HOME` or pass `--workspace` to isolate runs.

```powershell
python -m apps.cli.main init --workspace .storygraph-demo --force
```

Common CLI commands:

```powershell
python -m apps.cli.main add-character --workspace .storygraph-demo --project project_fantasy_demo --id character_mara --name "Mara" --properties-json '{"role":"scout"}' --reviewer editor --rationale "Seeded from story bible." --source-ref author_seed:story_bible_v1
python -m apps.cli.main add-location --workspace .storygraph-demo --project project_fantasy_demo --id location_harbor --name "Harbor" --properties-json '{"type":"port"}' --reviewer editor --rationale "Seeded from story bible." --source-ref author_seed:story_bible_v1
python -m apps.cli.main add-relation --workspace .storygraph-demo --project project_fantasy_demo --id rel_mara_located_at_harbor --type LOCATED_AT --source character_mara --target location_harbor --properties-json '{"scene_id":"scene_seed"}' --reviewer editor --rationale "Author placed Mara at the harbor." --source-ref author_seed:story_bible_v1
python -m apps.cli.main add-style-sample --workspace .storygraph-demo --project project_fantasy_demo --id style_tower --text "Cold restrained tower prose with short lines and subtext." --source-ref author_style:chapter_001 --pov "third-person limited" --tone "cold and restrained" --dialogue-style "short lines with subtext" --tags tower,clue
python -m apps.cli.main get-node --workspace .storygraph-demo --project project_fantasy_demo --id character_mara
python -m apps.cli.main query-graph --workspace .storygraph-demo --project project_fantasy_demo --source character_mara --hop-limit 1 --edge-labels LOCATED_AT --statuses CANON
python -m apps.cli.main build-context --workspace .storygraph-demo --project project_fantasy_demo --scene scene_003
python -m apps.cli.main write-scene --workspace .storygraph-demo --project project_fantasy_demo --scene scene_003
python -m apps.cli.main check-continuity --workspace .storygraph-demo --project project_fantasy_demo --scene scene_003
python -m apps.cli.main extract-state --workspace .storygraph-demo --project project_fantasy_demo --scene scene_003
python -m apps.cli.main run-scene --workspace .storygraph-demo --project project_fantasy_demo --scene scene_003
python -m apps.cli.main review-facts --workspace .storygraph-demo --project project_fantasy_demo
```

`extract-state` only creates pending `CandidateFact` records. Canon changes still require an explicit human review decision:

```powershell
python -m apps.cli.main review-facts --workspace .storygraph-demo --project project_fantasy_demo --fact fact_id --action accept --reviewer editor --note "approved"
python -m apps.cli.main review-facts --workspace .storygraph-demo --project project_fantasy_demo --fact fact_id --action edit-accept --reviewer editor --patch-json '{"confidence":0.8}' --note "accepted with edit"
python -m apps.cli.main review-facts --workspace .storygraph-demo --project project_fantasy_demo --fact fact_id --action reject --reviewer editor --note "not canon"
python -m apps.cli.main review-facts --workspace .storygraph-demo --project project_fantasy_demo --fact fact_id --action defer --reviewer editor --note "decide later"
```

The `add-character`, `add-location`, and `add-relation` commands are a separate explicit story-bible seed path. They write canon directly only because the human command supplies `--reviewer`, `--rationale`, and `--source-ref`; generated draft facts must still go through `extract-state` and review.

`get-node` and `query-graph` are read-only. By default they return canon state only; pass `--statuses` or `--include-non-canon` explicitly to inspect non-canon states.

`add-style-sample` writes to the local style sample store (`style_samples.sqlite`). Retrieved style samples are soft P6 context and never mutate graph canon.

## Document And Folder Import

The React/Vite workbench can import local `.txt`, `.md`, `.markdown`, and `.docx` files, including a browser-supported folder selection. Imported documents appear in an expandable local library tree and reader. By default this is still a browser-memory reader: imported content does not write drafts, facts, or canon.

From the reader, the author may explicitly send a ready imported document through backend stores:

- Save as the current scene draft in Draft Store.
- Save as a `proposal_artifact_v1` collaboration draft in Proposal Store.
- Save as a StyleSample Store style sample for P6 soft style retrieval.
- Use the configured OpenAI-compatible LLM to read imported source material and create an editable `fact_draft` proposal plus CandidateFact previews. This stores a source Draft for provenance, but it does not write canon.
- Save as the current scene draft and then run state extraction, which can create pending `CandidateFact` records.

Proposal artifacts are non-canon workspace records. Accepted `scene_draft` proposals can be explicitly promoted to Draft Store; accepted `fact_draft` proposals can submit pending CandidateFacts only from a real Draft Store `source_draft_id`. When promoting a `fact_draft`, the backend reads the explicit fact markers from the author-editable proposal body rather than bypassing it. These paths require the normal backend project/scene and permission checks. They still do not write Graph Store canon directly; extracted candidates remain pending until human review accepts or edit-accepts them with provenance.

CLI file inputs are still intentionally narrow:

```powershell
python -m apps.cli.main add-style-sample --workspace .storygraph-demo --project project_fantasy_demo --text-file .\samples\style.txt --source-ref author_style:style_txt
python -m apps.cli.main write-scene --workspace .storygraph-demo --project project_fantasy_demo --scene scene_003 --text-file .\drafts\scene_003.txt --summary "Author-provided draft."
```

These CLI commands read single UTF-8 text files. They do not import a folder tree, split chapters automatically, parse rich document formats, or promote extracted content to canon. Any importer path that creates drafts, style samples, or pending candidate facts must preserve the same safety rule: imported material must not write canon without human review and provenance.

## API Permission Levels

The FastAPI runtime has a local operator authorization switch at `/settings/agent`. This is not authentication; it is a local permission tier used to prevent accidental generation or canon writes from the API surface.

- `read_only`: allows read-style operations such as health, settings reads, graph queries, proposal listing, context building, continuity reads, and pending fact listing; blocks draft generation, proposal creation, state extraction, workflow runs, story-bible seed writes, and review decisions.
- `read_generate`: allows draft generation or save, proposal creation/revision, style sample insertion, state extraction, and scene workflow runs; blocks canon seed writes, proposal accept/reject, promotion actions, and candidate fact review decisions.
- `full`: allows the full local API surface, including human seed writes, proposal decisions/promotions, and accept/edit-accept/reject/defer review decisions.

Saving `/settings/agent` is treated as explicit local operator authorization. The Web or desktop settings panel and the same local API can both lower and raise `permission_level`, and the new level applies immediately. This does not let generated drafts, imported documents, or model output bypass CandidateFact review; canon-changing routes still require `full` permission plus reviewer, rationale, source reference, and the normal backend review/provenance path.

Set the level with PowerShell:

```powershell
Invoke-RestMethod -Method Put -Uri "http://127.0.0.1:8000/settings/agent" -ContentType "application/json" -Body '{"scene_writer":"rule_based","permission_level":"read_generate"}'
```

Agent settings are persisted to `agent_config.json` only when the API is started with persistent settings, such as through `python -m apps.api.desktop_server` or `create_app(StoryGraphSettings(...))`.

## LLM Scene Writer

Scene drafting uses the deterministic rule-based writer by default. To use a third-party OpenAI-compatible API for draft generation, inject credentials through local environment variables:

```powershell
$env:STORYGRAPH_SCENE_WRITER="llm"
$env:STORYGRAPH_LLM_BASE_URL="https://your-provider.example/v1"
$env:STORYGRAPH_LLM_API_KEY="<your provider key>"
$env:STORYGRAPH_LLM_MODEL="deepseek-chat"
```

In the Web or desktop settings panel, entering an API key only stores the credential reference. It does not enable LLM drafting by itself. The author must choose the OpenAI-compatible LLM writing mode, save settings, have `read_generate` or `full` permission, and run with a valid project, scene, and Context Pack.

The LLM writer reads `storygraph/prompts/scene_writer.md`, asks for JSON output, saves only to Draft Store, and locally rejects drafts that omit `must_include` items or contain literal `must_not_violate` constraints. Desktop sidecar builds package `storygraph/prompts` and `storygraph/localization` as data files. It never receives a Graph Store handle; generated state changes still have to pass through CandidateFact extraction and human review.

## Graph Backend

The local CLI uses the JSON graph backend by default. The real browser and desktop authoring paths should use the persistent desktop-target backend above; the seeded in-memory API is only a quick development/demo surface. To point API or CLI graph operations at Neo4j, install the optional dependency and set:

```powershell
python -m pip install -e ".[neo4j]"
$env:STORYGRAPH_GRAPH_BACKEND="neo4j"
$env:STORYGRAPH_NEO4J_URI="bolt://localhost:7687"
$env:STORYGRAPH_NEO4J_USER="neo4j"
$env:STORYGRAPH_NEO4J_PASSWORD="password"
$env:STORYGRAPH_NEO4J_DATABASE="neo4j"
```

Neo4j backend smoke tests are opt-in because they require a running Neo4j service:

```powershell
$env:STORYGRAPH_RUN_NEO4J_TESTS="1"
$env:STORYGRAPH_NEO4J_URI="bolt://localhost:7687"
$env:STORYGRAPH_NEO4J_USER="neo4j"
$env:STORYGRAPH_NEO4J_PASSWORD="password"
python -m pytest tests/test_graph_neo4j_integration.py
```

## Workflow Runtime

Scene workflows use the dependency-free local runtime by default:

```powershell
$env:STORYGRAPH_WORKFLOW_RUNTIME="local"
```

The workbench `Run` Agent workflow button follows the `scene_generation` steps from `workflow_run_v1`: `build_context`, `write_draft`, `check_continuity`, `extract_state`, and `human_review`. The review step is a pause around pending candidates, not a canon write by itself.

The API can also run `scene_generation` with `output_target=proposal_workspace`. That mode calls the configured writer, stores the result as a `scene_draft` proposal artifact, and skips continuity checking, state extraction, and human review because no Draft Store draft exists yet. The default `draft_store` mode remains compatible with existing CLI/API behavior.

To run the same `scene_generation` flow through a real LangGraph `StateGraph` with SQLite checkpoints, install the optional extra and set:

```powershell
python -m pip install -e ".[langgraph]"
$env:STORYGRAPH_WORKFLOW_RUNTIME="langgraph"
```

LangGraph checkpoints are stored at `langgraph_checkpoints.sqlite` inside the StoryGraph workspace. Public API/CLI run panels still read the stable `workflow_run_v1` projection from `workflows.sqlite`; canon writes remain gated by explicit ReviewService decisions.

## Canon Safety Rules

- The Graph Store is the source of truth for canon state.
- Draft text, generated summaries, imported text, style samples, frontend placeholders, and model hypotheses must not directly mutate canon.
- Proposal artifacts are non-canon collaboration records; accepting a proposal does not commit canon and promotion is a separate backend action.
- Automated extraction may only produce `CandidateFact` records or proposed graph patches.
- A candidate fact becomes canon only after explicit human review.
- Every canon write must have provenance: source scene, source draft or author seed, rationale, reviewer decision, and event log entry.
- Vector or style retrieval may assist context construction, but it must never override graph canon.
- The desktop layer must not bypass backend `ReviewService`, `GraphStore`, or the versioned contracts under `contracts/`.

## Demo CLI

```powershell
python -m apps.cli.main demo
python -m apps.cli.main review-demo --action accept --reviewer editor --note "approved via cli"
```

If Typer is installed, the CLI uses Typer. Without Typer, the core local commands fall back to `argparse`.

## Local Verification

Run the Python test suite:

```powershell
python -m pytest
```

Run the web build check:

```powershell
npm --prefix apps/web run build
```

Useful focused checks:

```powershell
python -m pytest tests/test_api_agent_settings.py tests/test_api_workflow_runs.py tests/test_cli_task12.py
```
