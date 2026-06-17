"""StoryGraph CLI.

Typer is preferred when installed. A small argparse fallback keeps the demo runnable in
minimal local environments.
"""

from __future__ import annotations

import argparse
import json

from storygraph.demo import ITEM_ID, LOCATION_ID, PROJECT_ID, SCENE_ID, build_fantasy_demo_graph
from storygraph.services import (
    ContextPackBuilder,
    ReviewService,
    RuleBasedContinuityChecker,
    RuleBasedSceneWriter,
    RuleBasedStateExtractor,
)
from storygraph.stores import SQLiteCandidateStore, SQLiteDraftStore
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


def run_review_demo(
    action: str = "pending",
    *,
    reviewer: str = "author",
    note: str | None = None,
) -> dict:
    graph = build_fantasy_demo_graph()
    draft_store = SQLiteDraftStore()
    candidate_store = SQLiteCandidateStore()
    extractor = RuleBasedStateExtractor()
    review = ReviewService(candidate_store, graph)
    marker = (
        f"[[fact:id=fact_cli_review;fact_type=ItemState;subject={ITEM_ID};"
        f"relation=LOCATED_AT;object={LOCATION_ID};confidence=0.95]]"
    )
    draft = draft_store.create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
        text=f"Lin Jin finds the half black wax seal. {marker}",
        summary="CLI review demo draft.",
    )
    candidates = review.submit(extractor.extract(project_id=PROJECT_ID, draft=draft))
    candidate = candidates[0]
    result = candidate
    if action == "accept":
        result = review.accept(
            candidate.id,
            reviewer=reviewer,
            note=note or "CLI accepted demo fact.",
        )
    elif action == "edit":
        result = review.edit_and_accept(
            candidate.id,
            reviewer=reviewer,
            patch_properties={"review_note": "CLI edited before canon commit."},
            note=note or "CLI edited and accepted demo fact.",
        )
    elif action == "reject":
        result = review.reject(
            candidate.id,
            reviewer=reviewer,
            note=note or "CLI rejected demo fact.",
        )
    elif action == "defer":
        result = review.defer(
            candidate.id,
            reviewer=reviewer,
            note=note or "CLI deferred demo fact.",
        )
    elif action != "pending":
        raise ValueError(f"Unknown review demo action: {action}")

    committed_relations = [
        relation.model_dump()
        for relation in graph.relationships.values()
        if relation.properties.get("candidate_fact_id") == candidate.id
    ]
    return {
        "action": action,
        "candidate": result.model_dump(),
        "pending_count": len(review.pending(project_id=PROJECT_ID)),
        "event_count": len(graph.event_log.list()),
        "committed_relations": committed_relations,
    }


def _main_argparse() -> None:
    parser = argparse.ArgumentParser(prog="storygraph")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("demo")
    review_demo_parser = subparsers.add_parser("review-demo")
    review_demo_parser.add_argument(
        "--action",
        choices=["pending", "accept", "edit", "reject", "defer"],
        default="pending",
    )
    review_demo_parser.add_argument("--reviewer", default="author")
    review_demo_parser.add_argument("--note", default=None)
    args = parser.parse_args()
    if args.command == "demo":
        print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
    elif args.command == "review-demo":
        print(
            json.dumps(
                run_review_demo(action=args.action, reviewer=args.reviewer, note=args.note),
                ensure_ascii=False,
                indent=2,
            )
        )


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

    @app.command("review-demo")
    def review_demo(
        action: str = typer.Option(
            "pending",
            help="Review action: pending, accept, edit, reject, or defer.",
        ),
        reviewer: str = typer.Option("author", help="Reviewer name recorded on the decision."),
        note: str | None = typer.Option(None, help="Review note recorded on the decision."),
    ) -> None:
        """Run a local CandidateFact review demo."""

        typer.echo(
            json.dumps(
                run_review_demo(action=action, reviewer=reviewer, note=note),
                ensure_ascii=False,
                indent=2,
            )
        )

    app()


if __name__ == "__main__":
    main()
