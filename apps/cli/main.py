"""StoryGraph CLI.

Typer is preferred when installed. A small argparse fallback keeps the demo runnable in
minimal local environments.
"""

from __future__ import annotations

import argparse
import json

from storygraph.demo import PROJECT_ID, SCENE_ID, build_fantasy_demo_graph
from storygraph.services import (
    ContextPackBuilder,
    RuleBasedContinuityChecker,
    RuleBasedSceneWriter,
    RuleBasedStateExtractor,
)
from storygraph.stores import SQLiteDraftStore
from storygraph.workflows import SceneGenerationWorkflow


def run_demo() -> dict:
    graph = build_fantasy_demo_graph()
    draft_store = SQLiteDraftStore()
    workflow = SceneGenerationWorkflow(
        context_builder=ContextPackBuilder(graph, draft_store),
        writer=RuleBasedSceneWriter(draft_store),
        checker=RuleBasedContinuityChecker(),
        extractor=RuleBasedStateExtractor(),
    )
    result = workflow.run(project_id=PROJECT_ID, scene_id=SCENE_ID)
    return {
        "context_pack": result.context_pack.model_dump(),
        "draft": result.draft.model_dump(),
        "continuity_report": result.continuity_report.model_dump(),
        "candidate_count": len(result.candidates),
    }


def _main_argparse() -> None:
    parser = argparse.ArgumentParser(prog="storygraph")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("demo")
    args = parser.parse_args()
    if args.command == "demo":
        print(json.dumps(run_demo(), ensure_ascii=False, indent=2))


def main() -> None:
    try:
        import typer
    except ImportError:
        _main_argparse()
        return

    app = typer.Typer(help="StoryGraph Agent MVP CLI")

    @app.command()
    def demo() -> None:
        """Run the local fantasy demo workflow."""

        typer.echo(json.dumps(run_demo(), ensure_ascii=False, indent=2))

    app()


if __name__ == "__main__":
    main()

