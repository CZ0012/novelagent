# StoryGraph Agent

StoryGraph Agent is a local MVP for long-form fiction workflows built around structured canon, draft isolation, human review, and continuity checks.

The implementation follows:

- `docs/architecture.md`
- `contracts/graph_store_v1.md`
- `contracts/context_pack_v1.md`
- `contracts/candidate_fact_v1.md`
- `contracts/continuity_report_v1.md`

Current MVP capabilities:

- Pydantic contract models for graph state, context packs, candidate facts, drafts, and continuity reports.
- Canon-safe in-memory graph store with explicit provenance and event log entries.
- SQLite draft store.
- Context Pack builder with P0-P7 budgeting metadata.
- Rule-based scene writer, continuity checker, and candidate fact extractor for deterministic local testing.
- Review service that keeps candidate facts pending until a human accept/edit decision commits them to canon.
- Minimal FastAPI and CLI entry points.
- Fantasy demo fixture and regression tests for the canon safety loop.

## Local Verification

```powershell
python -m pytest
```

Neo4j backend smoke tests are opt-in because they require a running Neo4j service:

```powershell
$env:STORYGRAPH_RUN_NEO4J_TESTS="1"
$env:STORYGRAPH_NEO4J_URI="bolt://localhost:7687"
$env:STORYGRAPH_NEO4J_USER="neo4j"
$env:STORYGRAPH_NEO4J_PASSWORD="password"
python -m pytest tests/test_graph_neo4j_integration.py
```

## Demo CLI

```powershell
python -m apps.cli.main demo
python -m apps.cli.main review-demo --action accept --reviewer editor --note "approved via cli"
```

If Typer is installed, the CLI uses Typer. Without Typer, the demo command falls back to `argparse`.
