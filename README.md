# StoryGraph Agent

StoryGraph Agent is a local MVP for long-form fiction workflows built around structured canon, draft isolation, human review, and continuity checks.

The implementation follows:

- `docs/architecture.md`
- `contracts/graph_store_v1.md`
- `contracts/context_pack_v1.md`
- `contracts/candidate_fact_v1.md`
- `contracts/continuity_report_v1.md`
- `contracts/workflow_run_v1.md`
- `contracts/review_payload_v1.md`
- `contracts/style_sample_store_v1.md`

Current MVP capabilities:

- Pydantic contract models for graph state, context packs, candidate facts, drafts, and continuity reports.
- Canon-safe in-memory graph store with explicit provenance and event log entries.
- SQLite draft store.
- Context Pack builder with P0-P7 budgeting metadata, stable retrieval provenance, and `missing_context` gap reports.
- Rule-based scene writer, optional OpenAI-compatible LLM scene writer, continuity checker, and candidate fact extractor.
- Review service that keeps candidate facts pending until a human accept/edit decision commits them to canon.
- Minimal FastAPI and CLI entry points.
- Local CLI workspace commands for context building, scene drafting, continuity checks, state extraction, workflow runs, and pending fact review.
- Workflow run checkpoints with API run listing, run event inspection, persisted settings-backed stores, review-pause resume, and optional LangGraph runtime/checkpointer support.
- Explicit human seed commands and API routes for story-bible Characters, Locations, and graph relationships.
- Read-only graph query API and CLI surfaces for inspecting canon neighbors and relationships.
- Local deterministic style sample store feeding `ContextPack.retrieved_style_samples`.
- React/Vite author workbench for scene drafting, Context Pack inspection, continuity QA, workflow events, graph/timeline preview, and pending fact review through the API.
- Tauri desktop shell configuration that hosts the same web workbench over the local FastAPI backend; the desktop layer does not write canon directly.
- Fantasy demo fixture and regression tests for the canon safety loop.

## Local Verification

```powershell
python -m pytest
```

Build and run the web workbench:

```powershell
npm --prefix apps/web install
npm --prefix apps/web run build
npm --prefix apps/web run dev
```

Open `http://127.0.0.1:5173` and point the API field at the FastAPI backend, usually `http://127.0.0.1:8000`.

The Tauri shell under `apps/desktop` is configuration-only in this MVP. It is intended to host the same React workbench and continue using backend review APIs for all canon-changing operations.

Neo4j backend smoke tests are opt-in because they require a running Neo4j service:

```powershell
$env:STORYGRAPH_RUN_NEO4J_TESTS="1"
$env:STORYGRAPH_NEO4J_URI="bolt://localhost:7687"
$env:STORYGRAPH_NEO4J_USER="neo4j"
$env:STORYGRAPH_NEO4J_PASSWORD="password"
python -m pytest tests/test_graph_neo4j_integration.py
```

The local CLI uses the JSON graph backend by default. API runs use the seeded in-memory demo graph unless `STORYGRAPH_GRAPH_BACKEND` is set. To point API/CLI runtime graph operations at Neo4j, set:

```powershell
$env:STORYGRAPH_GRAPH_BACKEND="neo4j"
$env:STORYGRAPH_NEO4J_URI="bolt://localhost:7687"
$env:STORYGRAPH_NEO4J_USER="neo4j"
$env:STORYGRAPH_NEO4J_PASSWORD="password"
$env:STORYGRAPH_NEO4J_DATABASE="neo4j"
```

Scene workflows use the dependency-free local runtime by default:

```powershell
$env:STORYGRAPH_WORKFLOW_RUNTIME="local"
```

To run the same `scene_generation` flow through a real LangGraph `StateGraph` with SQLite checkpoints, install the optional extra and set:

```powershell
python -m pip install -e ".[langgraph]"
$env:STORYGRAPH_WORKFLOW_RUNTIME="langgraph"
```

LangGraph checkpoints are stored at `langgraph_checkpoints.sqlite` inside the StoryGraph workspace. Public API/CLI run panels still read the stable `workflow_run_v1` projection from `workflows.sqlite`; canon writes remain gated by explicit ReviewService decisions.

Scene drafting uses the deterministic rule-based writer by default. To use a third-party OpenAI-compatible API for draft generation, inject credentials through local environment variables:

```powershell
$env:STORYGRAPH_SCENE_WRITER="llm"
$env:STORYGRAPH_LLM_BASE_URL="https://your-provider.example/v1"
$env:STORYGRAPH_LLM_API_KEY="<your provider key>"
$env:STORYGRAPH_LLM_MODEL="deepseek-chat"
```

The LLM writer reads `storygraph/prompts/scene_writer.md`, asks for JSON output, saves only to Draft Store, and locally rejects drafts that omit `must_include` items or contain literal `must_not_violate` constraints. It never receives a Graph Store handle; generated state changes still have to pass through CandidateFact extraction and human review.

## Demo CLI

```powershell
python -m apps.cli.main demo
python -m apps.cli.main review-demo --action accept --reviewer editor --note "approved via cli"
```

If Typer is installed, the CLI uses Typer. Without Typer, the core local commands fall back to `argparse`.

## Local CLI Workspace

The CLI can persist a local MVP workspace. By default it uses `.storygraph` under the current directory; set `STORYGRAPH_HOME` or pass `--workspace` to isolate runs.

```powershell
python -m apps.cli.main init --workspace .storygraph-demo --force
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
python -m apps.cli.main review-facts --workspace .storygraph-demo --project project_fantasy_demo --fact fact_id --action reject --reviewer editor --note "not canon"
```

The `add-character`, `add-location`, and `add-relation` commands are a separate explicit story-bible seed path. They write canon directly only because the human command supplies `--reviewer`, `--rationale`, and `--source-ref`; generated draft facts must still go through `extract-state` and review.

`get-node` and `query-graph` are read-only. By default they return canon state only; pass `--statuses` explicitly to inspect non-canon states.

`add-style-sample` writes to the local style sample store (`style_samples.sqlite`). Retrieved style samples are soft P6 context and never mutate graph canon.
