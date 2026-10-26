# StoryGraph Agent

StoryGraph Agent is a local MVP for long-form fiction workflows built around structured canon, draft isolation, human review, graph retrieval, and continuity checks.

Chinese documentation is available in [README.zh-CN.md](README.zh-CN.md).

Windows update repair: v0.1.13 checks backend shutdown and file replacement before installation, and reports the connected backend version separately from the desktop version. If an older update showed a backend write error, save your work, quit through the tray menu, and run the latest installer over the same installation directory. A newer interface alone does not prove the backend was updated. See [update recovery](docs/windows-update-recovery.md).

Windows update preparation: v0.1.15 waits for temporary sharing locks after backend shutdown. If a 0.1.13/0.1.14 client stops with `os error 32`, save your edits, quit from the tray and run the latest installer in the existing installation directory once. See [update recovery](docs/windows-update-recovery.md).

## Start writing

The writing workspace keeps the **outline on the left, manuscript in the middle, and Agent on the right**. Fold chapters and open scenes as documents. Continue a scene or discuss a selection without leaving the editor; inspect generated changes in **Proposals** before adopting them. Sources and advanced review tools remain separate views, and the right panel can close for focused writing.

1. Create a project and choose its story language. Add a chapter/scene, or import a TXT, Markdown, RTF, or DOCX manuscript into Sources and review a proposed structure.
2. Open **Settings** and save your provider endpoint, key, exact model ID, and explicit protocol (Chat Completions, Responses, or Anthropic Messages). **Refresh available models** checks the provider's own listing. A model label does not establish its vendor or model family; missing/unsupported listing never changes your model automatically.
3. Choose a writing preset: **Concise Chinese**, **Balanced narrative**, **Precise English**, or create your own System prompt. Presets persist in the local workspace and are shared by CLI, API, and desktop. Built-ins can be duplicated; custom presets can be edited and deleted.
4. Save your scene, choose **Continue story**, describe what should happen, and check the input list. The Agent uses that exact saved version and explicitly selected sources. The server appends only new text to a separate proposal and preserves the original draft.
5. Read the proposal and its version diff, edit it if needed, then explicitly adopt it as a scene draft. Candidate facts still require their own human review before canon changes. **Export text** downloads the visible draft or proposal without changing stored content.

Unsaved drafts and proposals are protected when changing projects, scenes, or connections. Saving while typing preserves newer local edits. A failed draft load remains locked until a successful retry. Changing the interface language never translates the manuscript or changes project output language.

Historical English outline titles or summaries can be corrected through **Outline tools → Repair outline language**. This uses the configured provider and the project's story language to propose chapter/scene metadata changes. Compare the original and suggested text, submit for review, accept, then explicitly apply. Graph/timeline views refresh together; manuscript text, stable IDs and relationships remain unchanged. Known graph node and relationship labels have independent Chinese/English display translations.

For localization extension, runtime boundaries, and verified behavior, see [Model routing and imports](docs/acceptance-0.1.17.md), [Manuscript acceptance](docs/acceptance-0.1.16.md), [Localization](docs/localization.md), [Update and outline repair acceptance](docs/acceptance-0.1.15.md), [Workbench acceptance](docs/acceptance-0.1.14.md), [Provider and preset acceptance](docs/acceptance-0.1.12.md), and [Agent runtime contract](contracts/agent_runtime_v1.md).

## Manuscript and Agent revisions (0.1.16)

- Select a chapter to read its saved scene drafts, or open a scene in **Preview / Edit**. Empty scenes offer writing, exact source-range adoption and Agent drafting actions.
- Ask about or revise a prose selection. Results remain separate proposals with red deletions, green additions and accessible text markers. Review and explicitly adopt the result.
- **New chapter / New volume** generates a reviewable structure and initial scene drafts from the author's instruction. Accept and apply before it enters the project; volume grouping uses the existing chapter volume index.
- Historical outline-only imports require explicit source adoption or new generation. Summaries are never treated as manuscript text. Verbatim source adoption requires matching source/project languages; other languages may be explicitly selected as Agent references.

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
- `contracts/source_document_v1.md`
- `contracts/language_policy_v1.md`
- `contracts/agent_runtime_v1.md`

A scene with incomplete planning metadata can still discuss and continue its saved draft; missing context is reported without inventing canon. Full scene generation retains its required-context checks.

## Current MVP Capabilities

- Pydantic contract models for graph state, context packs, candidate facts, drafts, workflow runs, review payloads, style samples, and continuity reports.
- Canon-safe graph stores with explicit provenance and event log entries, including the local JSON graph backend and optional Neo4j backend.
- SQLite stores for drafts, proposal artifacts, candidate facts, workflow runs, and deterministic local style samples.
- Context Pack builder with P0-P7 budgeting metadata, graph and draft provenance, retrieved style samples, and `missing_context` gap reports.
- Rule-based compatibility tools plus configured model writing, evidence-grounded semantic continuity/style review, and natural prose state extraction into human-reviewed candidates.
- Review service that keeps generated `CandidateFact` records pending until a human accept, edit-accept, reject, or defer decision.
- Human seed paths plus read-only project option lists for story-bible Characters, Locations, and graph relationships. Seed paths write canon only when the user supplies reviewer, rationale, source reference, and provenance.
- Read-only graph query API and CLI commands for inspecting canon neighbors and relationships.
- Local CLI workspace commands for context building, scene drafting, continuity checks, state extraction, workflow runs, and pending fact review.
- Workflow run checkpoints and projections with API run listing, run event inspection, review-pause resume, proposal-output runs, persisted stores, and optional LangGraph runtime/checkpointer support.
- FastAPI routes for the authoring workflow plus persisted agent settings for model provider, API key reference, JSON mode, scene writer mode, and API permission level.
- Chinese-localized React/Vite author workbench for real API-backed project trees, empty-workspace onboarding, chapter/scene metadata editing, scene drafting, selected-text Agent discussion/revision proposals, Proposal Workspace collaboration, Context Pack inspection, continuity QA, workflow events, graph/timeline preview, pending fact review, a persistent project Source Library for txt/md/markdown/docx imports, agent settings, and update checks through the API or desktop shell.
- Desktop-target FastAPI entrypoint (`apps.api.desktop_server`) that uses a persistent local workspace and the JSON graph backend.
- Buildable Tauri desktop package under `apps/desktop`, including npm scripts, a Rust entrypoint, hidden PyInstaller backend sidecar packaging, backend start/stop/status commands, system-tray lifecycle handling, Tauri capabilities, signed-updater configuration, a sci-fi app icon, and NSIS installer configuration.
- Fantasy demo fixture and regression tests for the canon safety loop.

## UI And Project Language Boundaries

`contracts/language_policy_v1.md` defines the SG-019 target. UI locale and
project content language are independent:

- local `ui_locale` supports `zh-CN` and `en-US`, defaults to `zh-CN`, and is
  persisted only as a versioned Web/Tauri client preference;
- `Project.language` supports `zh-CN` and `en-US` and is authoritative for new
  project content and Agent output;
- the backend freezes `output_language` from `Project.language` for Context
  Packs, generated Drafts/Proposals, and WorkflowRuns;
- Source Document language is a valid canonical BCP 47 tag or `und`; `und`
  cannot enter model prompts until the author assigns a known language; and
- cross-language reference is rejected by default. It requires both an explicit
  stable source selection and `cross_language_policy = explicit_reference`,
  never translates the source, and never changes output language.

The workbench remains Chinese-first by default. SG-019 is complete only after
the `en-US` resource, locale control, backend snapshots, migration paths, and all
four UI/project language combinations are implemented and verified together.

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

Run those commands in one PowerShell terminal. If `STORYGRAPH_HOME` is not set, the desktop-target backend uses `%LOCALAPPDATA%\StoryGraph Agent\workspace` on Windows when available, or the user home directory fallback. It creates the workspace directory and uses the JSON graph backend. It does not silently seed demo canon; an empty persistent or desktop workspace should show project creation first, then let authors import an existing manuscript and generate a non-canon `project_structure_draft` before applying confirmed chapters/scenes. The bundled fantasy demo is still available through `POST /demo/seed` for development/onboarding, and `POST /demo/archive` archives it from the current project tree.

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
apps/desktop/src-tauri/target/release/bundle/nsis/StoryGraph Agent_0.1.17_x64-setup.exe
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
apps/desktop/src-tauri/target/release/bundle/nsis/StoryGraph Agent_0.1.17_x64-setup.exe
apps/desktop/src-tauri/target/release/bundle/nsis/StoryGraph Agent_0.1.17_x64-setup.exe.sig
apps/desktop/src-tauri/target/release/bundle/nsis/StoryGraph.Agent_0.1.17_x64-setup.exe
apps/desktop/src-tauri/target/release/bundle/nsis/StoryGraph.Agent_0.1.17_x64-setup.exe.sig
apps/desktop/src-tauri/target/release/bundle/nsis/latest.json
```

The full installer build regenerates the PyInstaller backend sidecar with `--noconsole`, rebuilds the React/Vite workbench, and runs `tauri build`. The Tauri shell also starts the sidecar with Windows `CREATE_NO_WINDOW`, so the packaged app should not show a stray backend terminal window. Closing the main desktop window hides it to the system tray; use the tray menu item `退出 StoryGraph Agent` to stop the managed backend process tree and exit the app. If port 8000 already has a healthy backend with a different workspace, the desktop settings panel reports the conflict instead of treating that process as the current desktop workspace. The generated installer, `setup.exe.sig` updater signature, backend sidecar, and release executables are local outputs, not checked-in release artifacts.

The in-app settings panel includes a `Version & Updates` section. In the Tauri desktop runtime it uses `tauri-plugin-updater` to check the signed endpoint `https://github.com/CZ0012/novelagent/releases/latest/download/latest.json`, stop the managed backend, install the update, and restart the app. In a plain browser runtime it falls back to a GitHub Release check and, when available, links to the Windows installer asset.

Version updates must keep `VERSION`, `pyproject.toml`, the FastAPI version in `apps/api/main.py`, both Web/Desktop package manifests and root lockfile entries, `apps/web/src/version.ts`, the desktop package entry in `apps/desktop/src-tauri/Cargo.lock`, `apps/desktop/src-tauri/Cargo.toml`, and `apps/desktop/src-tauri/tauri.conf.json` synchronized. GitHub usage here is only the software release/update channel; local story workspaces, Source Store documents, canon, drafts, project settings, and review state are not synchronized to GitHub.

For the verified Windows build, the updater-relevant local artifacts are the NSIS setup executable and its Tauri updater signature, `StoryGraph Agent_0.1.17_x64-setup.exe.sig`, plus the no-space GitHub Release copies and `latest.json`. The backend sidecar is built with pinned PyInstaller 6.21.0. Do not document a `nsis.zip` updater artifact unless the build output changes. This Tauri updater signature is separate from Windows Authenticode code signing; production Authenticode signing for the sidecar and installer is still a separate release step.

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

## Persistent Source Library

The React/Vite workbench can import local `.txt`, `.md`, `.markdown`, and `.docx` files, including files selected from a browser-supported folder picker. The local client extracts text and import metadata and submits each file separately to the project-scoped Source Store. Each Source Document receives a stable ID and persists in the workspace, so it reappears after the API or desktop app restarts.

The Source Library is a private reference layer, not a browser-memory tree and not Draft Store or canon:

- Import results remain visible per file, so one failed file does not hide successful imports and can be retried.
- `GET /projects/{project_id}/sources` returns metadata summaries only; it never returns full `extracted_text`.
- The workbench requests one project-scoped detail only when the author opens or uses that document.
- Archiving removes a Source Document from normal library views without destructively deleting it or invalidating stable proposal provenance.
- Import, list, detail, retry, and archive operations do not create Drafts, CandidateFacts, graph nodes, graph relations, or canon events.
- Source language is independent from project language. `und` remains storable
  but cannot be sent to an Agent or structure analyzer under any language policy.
  Authors may correct language metadata without changing source identity or text.

On desktop-width layouts, the author can drag the Source panel's bottom edge and
the divider between the Source list and detail reader. Both separators also
support arrow keys, Shift for larger steps, Home/End, and double-click reset.
Only versioned UI dimensions are kept in local browser/Tauri storage; no source
ID, path, text, project, or scene data is stored with that preference. At narrow
widths the handles disappear and the list/reader return to an automatic stacked
layout.

`Use with Agent` is a selection-and-navigation shortcut. It carries only the
stable Source Document ID into the Agent panel and does not copy source text,
call a provider, create an artifact, or change `cross_language_policy`. A known
other-language source remains visible but blocks sending under `project_only`
until the author explicitly chooses `explicit_reference`; `und` remains blocked.

Structure analysis is a separate explicit action. `POST /projects/{project_id}/sources/{source_document_id}/structure-draft` reads one ready Source Document and creates only a non-canon, author-editable `project_structure_draft` Proposal Artifact. It does not create Chapter or Scene nodes until the author accepts the proposal and invokes the existing explicit apply action. New proposal provenance uses stable `source_document` refs; old `imported_document` refs remain legacy opaque records rather than persistent Source Store IDs. The language policy defaults to `project_only`; an explicit known-language mismatch requires `explicit_reference`, while `und` is always blocked.

The Source Library supports TXT, Markdown, DOCX, and plain-text extraction from RTF. PDF, OCR, images, and PSD remain unsupported and are skipped. RTF formatting, embedded objects, and images are not imported. Empty files and invalid containers have distinct diagnostics; Office temporary files beginning with `~$` are skipped. Import itself never creates another store record. After loading a ready detail, the author may separately and explicitly save that text as a current-scene Draft, a non-canon Proposal, or a Style Sample. This creates the normal target-store boundary; CandidateFacts still require a real Draft Store source and the existing pending human-review path.

## Agent Discussion And Selected-Text Revision

The Web and desktop-hosted workbench include an `Agent` tab for discussing the current scene with the configured task connection. The author can highlight a draft span, paste a marked passage, ask for a focused discussion, request a selected-span rewrite, or request a full-scene rewrite. Source Library documents are unselected by default. Only stable IDs that the author explicitly checks are sent as `source_document_ids`; the backend resolves those ready documents inside the route project. It never silently sends every library document or cached snippets from a previous request. The current Context Pack, current draft text, and optional web search remain separate explicit controls; disabling current-draft inclusion also prevents the editor text from being sent as `base_text`. Legacy inline sources must carry a valid source language; missing/invalid language is `422`, not a project-language default.

Before sending, the Agent panel shows an input manifest with the target Scene,
project output language, exact saved Draft ID/version or explicit omission,
Context Pack rebuild behavior, selected Source names/languages, cross-language
policy, and web-search state. If current-draft inclusion is enabled while the
editor differs from that exact saved Draft, every Agent mode is blocked until
the author saves or discards the local edit. The workbench submits that exact
Draft ID, and the backend uses the same scoped Draft for the provider input and
the resulting Proposal source ref; it never silently substitutes a newer
Draft. The no-ID latest-Draft fallback exists only for legacy API clients.

`POST /projects/{project_id}/scenes/{scene_id}/agent-discussion` requires `read_generate` permission and LLM credentials. It creates a non-canon `scene_rebuild` or `scene_draft` proposal in Proposal Store and returns the Agent reply, search snippets, and whether a selected-span replacement was applied to produce a full proposal body. It does not overwrite Draft Store, create CandidateFacts, or write Graph Store canon. Authors still review the proposal in `协作草稿箱`; only an explicit accept/promotion action can turn an accepted `scene_draft` proposal into a Draft Store draft.

The Proposal Workspace exposes content/status history and computes a local
side-by-side diff only when the selected Proposal version records one unique
Draft source ref. Zero refs are shown as no baseline and multiple refs as
ambiguous; it never substitutes the latest Draft. Unsaved Proposal title/body
edits are visibly dirty and block review decisions, promotion, and
proposal/scene/project switching until saved, discarded, or cancelled. Actions
follow state: editable versions submit for review, ready versions accept/reject,
and accepted artifacts expose only their applicable explicit promotion. A
scene-draft promotion validates its declared Scene target, reuses the same
already-derived Draft on a retry, and never writes canon.

CLI file inputs are still intentionally narrow:

```powershell
python -m apps.cli.main add-style-sample --workspace .storygraph-demo --project project_fantasy_demo --text-file .\samples\style.txt --source-ref author_style:style_txt
python -m apps.cli.main write-scene --workspace .storygraph-demo --project project_fantasy_demo --scene scene_003 --text-file .\drafts\scene_003.txt --summary "Author-provided draft."
```

These CLI commands read single UTF-8 text files. They do not use the project Source Library, import a folder tree, split chapters automatically, parse rich document formats, or promote extracted content to canon. Persistent multi-document import remains a Web/Tauri + FastAPI workflow. Imported material must never write canon without human review and provenance.

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

In the Web or desktop settings panel, entering an API key only stores the credential reference. It does not enable LLM drafting by itself. The author must choose the LLM writing mode, save settings, have `read_generate` or `full` permission, and run with a valid project, scene, and Context Pack.

The LLM writer reads `storygraph/prompts/scene_writer.md`, asks for JSON output, saves only to Draft Store, and locally rejects drafts that omit `must_include` items or contain literal `must_not_violate` constraints. Under `language_policy_v1`, its prose, title, summary, self-check, and deterministic fallback output use the server-derived `ContextPack.output_language`; author instructions and source language cannot override that snapshot. Desktop sidecar builds package `storygraph/prompts` and `storygraph/localization` as data files. It never receives a Graph Store handle; generated state changes still have to pass through CandidateFact extraction and human review.

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

The API can also run `scene_generation` with `output_target=proposal_workspace`. That mode calls the configured writer, stores the result as a `scene_draft` proposal artifact, and skips continuity checking, state extraction, and human review because no Draft Store draft exists yet. The default `draft_store` mode remains compatible for legacy projects. Projects opting into semantic review require `proposal_workspace` and a current passing review before adoption.

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

## License

StoryGraph Agent is licensed under the MIT License. See [LICENSE](LICENSE).


## Model roles and imports (0.1.17)

Keep one default connection for simple use, or expand **Model connections and task assignments** in Settings. Add named connections and assign planning, writing/continuation, revision, discussion, and fact extraction independently. Unassigned tasks inherit the default. Planning includes new chapter/volume structure and its initial prose in one request. The existing continuity/style check endpoint remains rule-based; source development also supports a separate continuity assignment for explicit semantic review and whole-book planning. All generated proposals expose the requested model and protocol; switching a connection never rewrites historical provenance.

Each connection explicitly selects Chat Completions, Responses, or Anthropic Messages. A model name does not choose the protocol or verify the actual upstream vendor. Existing settings migrate to Chat Completions without changing the model or key. Save a newly entered key only in the local backend workspace; a blank key keeps an existing key. Delete/clear actions are explicit, and no credentials are included in software releases. CLI scene generation loads the same saved task assignments.

Responses uses completed text output and `store: false`; Anthropic uses its native headers, top-level system prompt and Messages body. These are synchronous text adapters for the existing local Agent workflow. Hosted tool execution, server-side memory and response-ID continuation are not enabled. Model listing is read-only and is not proof of generation or tool support. Unsupported protocols, truncated output and malformed JSON fail without switching models, paid retries or canon changes.

RTF (Rich Text Format) is a rich-text document format. Imports retain readable text and paragraph breaks, including Unicode and supported Chinese code pages, with bounded local parsing. A 0-byte DOCX has no content to extract; retrying cannot restore bytes missing from the original file.

## Long-form planning and semantic review (source development)

The author workbench now includes a project-level planning workspace. Start with a new project, describe the novel, and choose a target such as 500,000 Chinese characters. The Agent proposes a world/character/style blueprint and volume budgets. Review and accept that proposal, then explicitly apply it. Expand chapters in batches of at most five, review/apply each batch, and resume from the saved proposals after a restart. Planned character budgets are not generated manuscript word counts. Blueprint application selects a reviewed project StyleProfile; scene generation, revision and composition use that voice across configured models.

Saved prose and exact proposal versions can receive an explicit **semantic review**, using the separate continuity model assignment. Reports show grounded text/canon evidence, scope, coverage and stale-input status. A passing scene report covers its selected scene evidence; it is not a proof that the entire novel has no contradictions. Long-form projects require a fresh passing report before adopting Agent prose from a scene proposal. Manual author saves remain available. **Extract prose state** uses the exact saved Draft to propose evidence-backed state changes; those remain fact proposals and still require CandidateFact human review before canon changes.

This source change runs through the local FastAPI + React workbench. Rebuilding the desktop from the current checkout hosts that same backend workflow; existing local package files do not pick up later edits automatically. It does not update an installed desktop app by itself or publish a signed release. The CLI retains its existing scene workflow; the new planning/review controls currently use the API/workbench. GitHub remains solely the software update channel. Semantic accuracy, literary quality and complete long-novel acceptance require the separate evidence recorded for this development task.

### Independent whole-book planning

Each planning batch now receives exact prior story-time anchors and an all-prior
outcome ledger, alongside the richer recent twelve scenes. This retains earlier
sealed-original/copy status and character/location identities without inventing
state summaries or treating plans as completed events. Explicit flashbacks remain
possible; batch boundaries do not restart the story clock. The final ledger also
includes scene time and required characters. Changed context makes later reports
stale and requires review; an unchanged opening batch retains its prior binding.

Planning-run reviews have an explicit 200,000-character target limit, justified
by complete-framework size measurements; ordinary scene/general review remains
at 100,000. Earlier-outcome ledgers also have fixed record/size bounds. Exceeding
a limit pauses rather than silently deleting old evidence or declaring success.
These are capacity checks, not proof of a completed real 200-scene novel.

Scene context uses bounded **AUTO 8,000–16,000 tokens** for approved long-form/
protected projects and remains 4,000 for legacy projects. Omitting a target (or
passing null) starts at 8,000 and grows in 2,000-token steps with small headroom
only when required context needs it, up to 16,000. An explicit target, including
8,000 or 4,000 through
the context API or CLI `build-context --target-tokens`, remains strict. Required
canon, scene plans, knowledge and style are preserved; if they exceed the target,
full drafting stops before a model call. This is a context estimate, not a total
request/token allowance. See [Context Pack rules](contracts/context_pack_v1.md).

Choose **Whole-book planning → Plan the complete book** to run a bounded background task that produces the world/style blueprint and all chapter batches before any canon application. Select the maximum model calls and repair attempts; stop/resume is explicit and progress survives restart. Uncertain external calls require a separate retry choice. Existing unapplied blueprints can be reused by exact version. A completed bundle pins all plans and reports; inspect and accept it, then explicitly apply the entire structure once. This generates a framework, not a 500,000-character manuscript.

Reviewed temporal state records preserve life, condition, location and ownership at each scene. Historical mistakes can be corrected from exact saved same-scene evidence through a pending correction and normal human review; the previous record remains auditable. Plain author saves remain available, while generated prose in protected projects must pass its current semantic review. The UI distinguishes observations that do not change state.

DeepSeek official Chat Completions connections now expose an explicit thinking switch. Provider default is preserved unless the author changes it; an incompatible host/protocol is rejected before a call. Call budgets do not claim a universal currency estimate across third-party providers.

### Explicit reasoning, uncertain calls and writing context

Configured CLI, API and source-built desktop backends default to a **300-second
provider HTTP socket timeout**, allowing multi-minute thinking and semantic
review responses. Set `STORYGRAPH_LLM_TIMEOUT_SECONDS` before starting the
backend to override it; an explicit `60` is preserved. This is not a whole-job
deadline, an automatic retry or a model change. A timed-out paid call can still
have an unknown outcome and follows the explicit recovery rules below.

Official HTTPS `api.deepseek.com` Chat Completions connections support an optional **low / high / max** reasoning effort. Leaving effort unset preserves provider behavior; effort with thinking disabled is rejected. Provider default plus an explicit effort is allowed. Default and named connections retain omitted settings, while explicit clearing removes the effort override. Saved execution provenance records an explicit effort and omits an unset value, preserving historical records and frozen run fingerprints. See [agent runtime contract](contracts/agent_runtime_v1.md).

The service exposes its complete reasoning-plus-output ceiling before a model call. Explicit low/high effort, or explicitly enabled thinking without an effort, normally adds 32,768 tokens to the service baseline, capped at 65,536 total. Planning uses a 52,768-token ceiling; semantic review explicitly opts into 65,536 after observed length exhaustion. Default/disabled requests without an explicit effort retain their previous ceilings. These are maxima, not expected usage or a currency quote; no provider silently enlarges a request behind the call/cost guard. Structured plan review sends the full parsed plan once with hash/metadata and exact citation sources; the untouched original remains local for strict evidence validation.

A timeout or lost connection leaves the paid call's outcome unknown. The planner saves its diagnostic report, retains the original pending-call reservation and requires an explicit uncertain-call retry choice. A complete but invalid or truncated response is a known failure: it remains inconclusive and may receive an explicit recheck without being misrepresented as still in flight. Neither path retries automatically. Both consume their reserved call count. [Planning-run rules](contracts/planning_run_v1.md) define stop, recovery and retry behavior.

Writing context distinguishes **scene entry**, **approved plan** and **realized state**. Knowledge first acquired during a scene is excluded at its opening; only explicitly reviewed starting knowledge and prior reachable acquisitions are available. Optional `scene_plan` supplies the current approved scene summary, intended ending, emotional turn, length budget, up to 30 direct causal predecessor plans and explicit seed/payoff actions using stable graph IDs. The summary is included only for an existing plan; a legacy summary alone does not create approval. These are protected semantic writing beats, not facts already realized or phrases to copy literally. Seed actions withhold their hidden payoff. Missing, foreign or over-budget protected planning context blocks full drafting rather than inventing a prerequisite. See [context-pack contract](contracts/context_pack_v1.md).

Current real-model coverage is recorded separately in [0.2.0 acceptance](docs/acceptance-0.2.0.md). Allocated 500,000-character budgets, a 100-chapter grid and offline synthetic tests do not by themselves establish completed real-model acceptance of a whole book. These controls use the same local backend from API/Web and source-built desktop; they do not publish a release or change the CLI's existing scene entrypoints.


Planning runs default to 80 model calls and allow an explicit per-run ceiling of
512 through creation or resume. Existing stored limits do not change automatically.
Resume cannot set a limit below cumulative reserved calls; increasing the limit
preserves call counts, outputs and history. The Web controls use the same ceiling.
This technical per-run bound is separate from any shared monetary or global-call
guard and does not authorize additional spending or automatic retries. Desktop
builds need a rebuilt backend and Web bundle to include this source change.


Plan semantic review supplies the frozen author instruction as a separate trusted
style source, including manual expansions through their exact parent blueprint.
Style findings still need exact target and applicable style evidence. Registry
aliases prioritize style/canon sources before target segments; full target input
is preserved. The brief participates in currentness checks, so earlier plan
reports may need explicit fresh review. Existing failed responses are unchanged;
no review is retried automatically. Rebuild the desktop backend to include this
source change in a local candidate.
