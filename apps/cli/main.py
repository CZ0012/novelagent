"""StoryGraph CLI.

Typer is preferred when installed. A small argparse fallback keeps the core
commands runnable in minimal local environments.
"""

from __future__ import annotations

import argparse
import json
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from storygraph.core.config import StoryGraphSettings
from storygraph.core.errors import ContractError
from storygraph.core.ids import slug_id
from storygraph.demo import ITEM_ID, LOCATION_ID, PROJECT_ID, SCENE_ID, build_fantasy_demo_graph
from storygraph.services import (
    ContextPackBuilder,
    ReviewService,
    RuleBasedContinuityChecker,
    RuleBasedSceneWriter,
    RuleBasedStateExtractor,
)
from storygraph.stores import SQLiteCandidateStore, SQLiteDraftStore
from storygraph.stores.json_graph import load_json_graph, save_json_graph
from storygraph.stores.memory_graph import InMemoryGraphStore
from storygraph.stores.workflow_store import SQLiteWorkflowStore
from storygraph.workflows import SceneGenerationWorkflow


@dataclass
class CliRuntime:
    settings: StoryGraphSettings
    graph: InMemoryGraphStore
    draft_store: SQLiteDraftStore
    candidate_store: SQLiteCandidateStore
    workflow_store: SQLiteWorkflowStore
    review: ReviewService

    def close(self) -> None:
        for store in [self.draft_store, self.candidate_store, self.workflow_store]:
            with suppress(Exception):
                store.close()


def _runtime(workspace: str | Path | None = None) -> CliRuntime:
    settings = StoryGraphSettings(workspace)
    settings.ensure_workspace()
    graph = load_json_graph(settings.graph_path)
    draft_store = SQLiteDraftStore(settings.draft_store_path)
    candidate_store = SQLiteCandidateStore(settings.candidate_store_path)
    workflow_store = SQLiteWorkflowStore(settings.workflow_store_path)
    review = ReviewService(candidate_store, graph)
    return CliRuntime(
        settings=settings,
        graph=graph,
        draft_store=draft_store,
        candidate_store=candidate_store,
        workflow_store=workflow_store,
        review=review,
    )


def _dump(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def init_workspace(
    *,
    title: str = "Fantasy Demo",
    genre: str = "fantasy",
    language: str = "zh-CN",
    workspace: str | Path | None = None,
    force: bool = False,
    empty: bool = False,
) -> dict:
    settings = StoryGraphSettings(workspace)
    settings.ensure_workspace()
    if settings.graph_path.exists() and not force:
        graph = load_json_graph(settings.graph_path)
        project_ids = [
            node.id
            for node in sorted(graph.nodes.values(), key=lambda item: item.id)
            if node.type == "Project"
        ]
        return {
            "workspace": str(settings.workspace_dir),
            "graph_path": str(settings.graph_path),
            "created": False,
            "project_id": project_ids[0] if project_ids else None,
            "node_count": len(graph.nodes),
            "relationship_count": len(graph.relationships),
        }
    if force:
        for state_path in [
            settings.graph_path,
            settings.draft_store_path,
            settings.candidate_store_path,
            settings.workflow_store_path,
        ]:
            if state_path.exists():
                state_path.unlink()

    if empty:
        graph = InMemoryGraphStore()
        project_id = slug_id("project", title)
        graph.seed_canon_node(
            node_id=project_id,
            node_type="Project",
            properties={"title": title, "genre": genre, "language": language},
            source_ref="cli:init",
            reviewer="author",
            rationale="Author initialized an empty StoryGraph project.",
        )
    else:
        graph = build_fantasy_demo_graph()
        graph.update_node(
            PROJECT_ID,
            {"title": title, "genre": genre, "language": language},
            reviewer="author",
            rationale="Author initialized the local StoryGraph demo workspace.",
            source_ref="cli:init",
        )
        project_id = PROJECT_ID

    save_json_graph(graph, settings.graph_path)
    return {
        "workspace": str(settings.workspace_dir),
        "graph_path": str(settings.graph_path),
        "draft_store_path": str(settings.draft_store_path),
        "candidate_store_path": str(settings.candidate_store_path),
        "workflow_store_path": str(settings.workflow_store_path),
        "created": True,
        "project_id": project_id,
        "demo_seeded": not empty,
        "node_count": len(graph.nodes),
        "relationship_count": len(graph.relationships),
    }


def build_context_command(
    *,
    project_id: str = PROJECT_ID,
    scene_id: str = SCENE_ID,
    workspace: str | Path | None = None,
    target_tokens: int = 4000,
) -> dict:
    runtime = _runtime(workspace)
    try:
        pack = ContextPackBuilder(runtime.graph, runtime.draft_store).build(
            project_id=project_id,
            scene_id=scene_id,
            target_tokens=target_tokens,
        )
        return pack.model_dump()
    finally:
        runtime.close()


def write_scene_command(
    *,
    project_id: str = PROJECT_ID,
    scene_id: str = SCENE_ID,
    workspace: str | Path | None = None,
    text: str | None = None,
    text_file: str | Path | None = None,
    summary: str | None = None,
) -> dict:
    if text and text_file:
        raise ContractError("Use either text or text_file, not both")
    runtime = _runtime(workspace)
    try:
        if text_file:
            text = Path(text_file).read_text(encoding="utf-8")
        if text is not None:
            draft = runtime.draft_store.create_draft(
                project_id=project_id,
                scene_id=scene_id,
                text=text,
                summary=summary,
            )
            return draft.model_dump()
        context_pack = ContextPackBuilder(runtime.graph, runtime.draft_store).build(
            project_id=project_id,
            scene_id=scene_id,
        )
        return RuleBasedSceneWriter(runtime.draft_store).write_and_save(context_pack).model_dump()
    finally:
        runtime.close()


def check_continuity_command(
    *,
    project_id: str = PROJECT_ID,
    scene_id: str = SCENE_ID,
    workspace: str | Path | None = None,
) -> dict:
    runtime = _runtime(workspace)
    try:
        draft = runtime.draft_store.latest_for_scene(project_id, scene_id)
        if draft is None:
            raise ContractError(f"No draft found for scene: {scene_id}")
        context_pack = ContextPackBuilder(runtime.graph, runtime.draft_store).build(
            project_id=project_id,
            scene_id=scene_id,
        )
        return RuleBasedContinuityChecker().check(context_pack=context_pack, draft=draft).model_dump()
    finally:
        runtime.close()


def extract_state_command(
    *,
    project_id: str = PROJECT_ID,
    scene_id: str = SCENE_ID,
    workspace: str | Path | None = None,
) -> dict:
    runtime = _runtime(workspace)
    try:
        draft = runtime.draft_store.latest_for_scene(project_id, scene_id)
        if draft is None:
            raise ContractError(f"No draft found for scene: {scene_id}")
        candidates = RuleBasedStateExtractor().extract(project_id=project_id, draft=draft)
        submitted = runtime.review.submit(candidates)
        return {"candidates": [candidate.model_dump() for candidate in submitted]}
    finally:
        runtime.close()


def run_scene_command(
    *,
    project_id: str = PROJECT_ID,
    scene_id: str = SCENE_ID,
    workspace: str | Path | None = None,
) -> dict:
    runtime = _runtime(workspace)
    try:
        workflow = SceneGenerationWorkflow(
            context_builder=ContextPackBuilder(runtime.graph, runtime.draft_store),
            writer=RuleBasedSceneWriter(runtime.draft_store),
            checker=RuleBasedContinuityChecker(),
            extractor=RuleBasedStateExtractor(),
            workflow_store=runtime.workflow_store,
            review_service=runtime.review,
        )
        result = workflow.run(project_id=project_id, scene_id=scene_id)
        return {
            "context_pack": result.context_pack.model_dump(),
            "draft": result.draft.model_dump(),
            "continuity_report": result.continuity_report.model_dump(),
            "candidates": [candidate.model_dump() for candidate in result.candidates],
            "workflow_run": result.workflow_run.model_dump() if result.workflow_run else None,
        }
    finally:
        runtime.close()


def review_facts_command(
    *,
    project_id: str = PROJECT_ID,
    workspace: str | Path | None = None,
    action: str = "pending",
    fact_id: str | None = None,
    reviewer: str = "author",
    note: str | None = None,
    patch_json: str | None = None,
) -> dict:
    runtime = _runtime(workspace)
    try:
        if action == "pending":
            return {
                "facts": [
                    fact.model_dump()
                    for fact in runtime.review.pending(project_id=project_id)
                ]
            }

        candidate_id = fact_id or _single_pending_fact_id(runtime, project_id)
        if action == "accept":
            fact = runtime.review.accept(candidate_id, reviewer=reviewer, note=note)
            save_json_graph(runtime.graph, runtime.settings.graph_path)
        elif action == "edit-accept":
            patch_properties = json.loads(patch_json or "{}")
            if not isinstance(patch_properties, dict):
                raise ContractError("patch_json must decode to a JSON object")
            fact = runtime.review.edit_and_accept(
                candidate_id,
                reviewer=reviewer,
                patch_properties=patch_properties,
                note=note,
            )
            save_json_graph(runtime.graph, runtime.settings.graph_path)
        elif action == "reject":
            fact = runtime.review.reject(candidate_id, reviewer=reviewer, note=note)
        elif action == "defer":
            fact = runtime.review.defer(candidate_id, reviewer=reviewer, note=note)
        else:
            raise ContractError(f"Unknown review action: {action}")

        committed_relations = [
            relation.model_dump()
            for relation in runtime.graph.relationships.values()
            if relation.properties.get("candidate_fact_id") == candidate_id
        ]
        return {
            "action": action,
            "candidate": fact.model_dump(),
            "pending_count": len(runtime.review.pending(project_id=project_id)),
            "event_count": len(runtime.graph.event_log.list()),
            "committed_relations": committed_relations,
        }
    finally:
        runtime.close()


def _single_pending_fact_id(runtime: CliRuntime, project_id: str) -> str:
    pending = runtime.review.pending(project_id=project_id)
    if not pending:
        raise ContractError("No pending CandidateFact records")
    if len(pending) > 1:
        raise ContractError("Multiple pending CandidateFact records; pass fact_id explicitly")
    return pending[0].id


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

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--title", default="Fantasy Demo")
    init_parser.add_argument("--genre", default="fantasy")
    init_parser.add_argument("--language", default="zh-CN")
    init_parser.add_argument("--workspace", default=None)
    init_parser.add_argument("--force", action="store_true")
    init_parser.add_argument("--empty", action="store_true")

    for name in ["build-context", "write-scene", "check-continuity", "extract-state", "run-scene"]:
        command_parser = subparsers.add_parser(name)
        command_parser.add_argument("--project", default=PROJECT_ID)
        command_parser.add_argument("--scene", default=SCENE_ID)
        command_parser.add_argument("--workspace", default=None)
        if name == "write-scene":
            command_parser.add_argument("--text", default=None)
            command_parser.add_argument("--text-file", default=None)
            command_parser.add_argument("--summary", default=None)

    review_parser = subparsers.add_parser("review-facts")
    review_parser.add_argument("--project", default=PROJECT_ID)
    review_parser.add_argument("--workspace", default=None)
    review_parser.add_argument(
        "--action",
        choices=["pending", "accept", "edit-accept", "reject", "defer"],
        default="pending",
    )
    review_parser.add_argument("--fact", default=None)
    review_parser.add_argument("--reviewer", default="author")
    review_parser.add_argument("--note", default=None)
    review_parser.add_argument("--patch-json", default=None)

    review_demo_parser = subparsers.add_parser("review-demo")
    review_demo_parser.add_argument(
        "--action",
        choices=["pending", "accept", "edit", "reject", "defer"],
        default="pending",
    )
    review_demo_parser.add_argument("--reviewer", default="author")
    review_demo_parser.add_argument("--note", default=None)
    args = parser.parse_args()

    payload: dict[str, Any]
    if args.command == "demo":
        payload = run_demo()
    elif args.command == "init":
        payload = init_workspace(
            title=args.title,
            genre=args.genre,
            language=args.language,
            workspace=args.workspace,
            force=args.force,
            empty=args.empty,
        )
    elif args.command == "build-context":
        payload = build_context_command(
            project_id=args.project,
            scene_id=args.scene,
            workspace=args.workspace,
        )
    elif args.command == "write-scene":
        payload = write_scene_command(
            project_id=args.project,
            scene_id=args.scene,
            workspace=args.workspace,
            text=args.text,
            text_file=args.text_file,
            summary=args.summary,
        )
    elif args.command == "check-continuity":
        payload = check_continuity_command(
            project_id=args.project,
            scene_id=args.scene,
            workspace=args.workspace,
        )
    elif args.command == "extract-state":
        payload = extract_state_command(
            project_id=args.project,
            scene_id=args.scene,
            workspace=args.workspace,
        )
    elif args.command == "run-scene":
        payload = run_scene_command(
            project_id=args.project,
            scene_id=args.scene,
            workspace=args.workspace,
        )
    elif args.command == "review-facts":
        payload = review_facts_command(
            project_id=args.project,
            workspace=args.workspace,
            action=args.action,
            fact_id=args.fact,
            reviewer=args.reviewer,
            note=args.note,
            patch_json=args.patch_json,
        )
    elif args.command == "review-demo":
        payload = run_review_demo(action=args.action, reviewer=args.reviewer, note=args.note)
    else:
        raise ContractError(f"Unknown command: {args.command}")
    print(_dump(payload))


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

        typer.echo(_dump(run_demo()))

    @app.command("init")
    def init_cmd(
        title: str = typer.Option("Fantasy Demo", help="Project title to seed."),
        genre: str = typer.Option("fantasy", help="Project genre."),
        language: str = typer.Option("zh-CN", help="Project language."),
        workspace: str | None = typer.Option(None, help="Local StoryGraph workspace directory."),
        force: bool = typer.Option(False, help="Overwrite the existing local graph file."),
        empty: bool = typer.Option(False, help="Seed only an empty Project node."),
    ) -> None:
        """Initialize a local StoryGraph workspace."""

        typer.echo(
            _dump(
                init_workspace(
                    title=title,
                    genre=genre,
                    language=language,
                    workspace=workspace,
                    force=force,
                    empty=empty,
                )
            )
        )

    @app.command("build-context")
    def build_context_cmd(
        project: str = typer.Option(PROJECT_ID, help="Project ID."),
        scene: str = typer.Option(SCENE_ID, help="Scene ID."),
        workspace: str | None = typer.Option(None, help="Local StoryGraph workspace directory."),
        target_tokens: int = typer.Option(4000, help="Context budget target."),
    ) -> None:
        """Build a Context Pack for a scene."""

        typer.echo(
            _dump(
                build_context_command(
                    project_id=project,
                    scene_id=scene,
                    workspace=workspace,
                    target_tokens=target_tokens,
                )
            )
        )

    @app.command("write-scene")
    def write_scene_cmd(
        project: str = typer.Option(PROJECT_ID, help="Project ID."),
        scene: str = typer.Option(SCENE_ID, help="Scene ID."),
        workspace: str | None = typer.Option(None, help="Local StoryGraph workspace directory."),
        text: str | None = typer.Option(None, help="Draft text to save instead of generating."),
        text_file: str | None = typer.Option(None, help="UTF-8 file containing draft text."),
        summary: str | None = typer.Option(None, help="Optional draft summary."),
    ) -> None:
        """Generate or save a scene draft."""

        typer.echo(
            _dump(
                write_scene_command(
                    project_id=project,
                    scene_id=scene,
                    workspace=workspace,
                    text=text,
                    text_file=text_file,
                    summary=summary,
                )
            )
        )

    @app.command("check-continuity")
    def check_continuity_cmd(
        project: str = typer.Option(PROJECT_ID, help="Project ID."),
        scene: str = typer.Option(SCENE_ID, help="Scene ID."),
        workspace: str | None = typer.Option(None, help="Local StoryGraph workspace directory."),
    ) -> None:
        """Check the latest draft against context and canon."""

        typer.echo(
            _dump(
                check_continuity_command(
                    project_id=project,
                    scene_id=scene,
                    workspace=workspace,
                )
            )
        )

    @app.command("extract-state")
    def extract_state_cmd(
        project: str = typer.Option(PROJECT_ID, help="Project ID."),
        scene: str = typer.Option(SCENE_ID, help="Scene ID."),
        workspace: str | None = typer.Option(None, help="Local StoryGraph workspace directory."),
    ) -> None:
        """Extract pending CandidateFact records from the latest draft."""

        typer.echo(
            _dump(
                extract_state_command(
                    project_id=project,
                    scene_id=scene,
                    workspace=workspace,
                )
            )
        )

    @app.command("run-scene")
    def run_scene_cmd(
        project: str = typer.Option(PROJECT_ID, help="Project ID."),
        scene: str = typer.Option(SCENE_ID, help="Scene ID."),
        workspace: str | None = typer.Option(None, help="Local StoryGraph workspace directory."),
    ) -> None:
        """Run the local scene generation workflow."""

        typer.echo(_dump(run_scene_command(project_id=project, scene_id=scene, workspace=workspace)))

    @app.command("review-facts")
    def review_facts_cmd(
        project: str = typer.Option(PROJECT_ID, help="Project ID."),
        workspace: str | None = typer.Option(None, help="Local StoryGraph workspace directory."),
        action: str = typer.Option(
            "pending",
            help="Review action: pending, accept, edit-accept, reject, or defer.",
        ),
        fact: str | None = typer.Option(None, help="CandidateFact ID. Optional if exactly one is pending."),
        reviewer: str = typer.Option("author", help="Reviewer name recorded on the decision."),
        note: str | None = typer.Option(None, help="Review note recorded on the decision."),
        patch_json: str | None = typer.Option(None, help="JSON object merged into the graph patch."),
    ) -> None:
        """List or decide pending CandidateFact records."""

        typer.echo(
            _dump(
                review_facts_command(
                    project_id=project,
                    workspace=workspace,
                    action=action,
                    fact_id=fact,
                    reviewer=reviewer,
                    note=note,
                    patch_json=patch_json,
                )
            )
        )

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

        typer.echo(_dump(run_review_demo(action=action, reviewer=reviewer, note=note)))

    app()


if __name__ == "__main__":
    main()
