"""Minimal FastAPI surface for the StoryGraph MVP."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from storygraph.core.errors import GraphStoreError
from storygraph.core.ids import slug_id
from storygraph.demo import PROJECT_ID, SCENE_ID, build_fantasy_demo_graph
from storygraph.services import (
    ContextPackBuilder,
    ReviewService,
    RuleBasedContinuityChecker,
    RuleBasedSceneWriter,
    RuleBasedStateExtractor,
)
from storygraph.stores import InMemoryCandidateStore, SQLiteDraftStore


class CreateProjectRequest(BaseModel):
    title: str
    genre: str = "fantasy"
    language: str = "zh-CN"


class ReviewRequest(BaseModel):
    reviewer: str = "author"
    note: str | None = None


def create_app() -> FastAPI:
    app = FastAPI(title="StoryGraph Agent", version="0.1.0")
    graph = build_fantasy_demo_graph()
    draft_store = SQLiteDraftStore()
    candidate_store = InMemoryCandidateStore()
    context_builder = ContextPackBuilder(graph, draft_store)
    writer = RuleBasedSceneWriter(draft_store)
    checker = RuleBasedContinuityChecker()
    extractor = RuleBasedStateExtractor()
    review = ReviewService(candidate_store, graph)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/projects")
    def create_project(request: CreateProjectRequest) -> dict:
        project_id = slug_id("project", request.title)
        try:
            graph.seed_canon_node(
                node_id=project_id,
                node_type="Project",
                properties={
                    "title": request.title,
                    "genre": request.genre,
                    "language": request.language,
                },
                source_ref="api:projects",
                reviewer="author",
                rationale="Author created project through API.",
            )
        except GraphStoreError as exc:
            raise HTTPException(status_code=409, detail={"category": exc.category, "message": str(exc)})
        return {"project_id": project_id}

    @app.get("/demo")
    def demo() -> dict:
        return {"project_id": PROJECT_ID, "scene_id": SCENE_ID}

    @app.post("/projects/{project_id}/scenes/{scene_id}/context-pack")
    def build_context(project_id: str, scene_id: str) -> dict:
        return context_builder.build(project_id=project_id, scene_id=scene_id).model_dump()

    @app.post("/projects/{project_id}/scenes/{scene_id}/draft")
    def write_draft(project_id: str, scene_id: str) -> dict:
        context_pack = context_builder.build(project_id=project_id, scene_id=scene_id)
        return writer.write_and_save(context_pack).model_dump()

    @app.post("/projects/{project_id}/scenes/{scene_id}/check-continuity")
    def check_continuity(project_id: str, scene_id: str) -> dict:
        context_pack = context_builder.build(project_id=project_id, scene_id=scene_id)
        draft = draft_store.latest_for_scene(project_id, scene_id)
        if draft is None:
            raise HTTPException(status_code=404, detail="No draft for scene")
        return checker.check(context_pack=context_pack, draft=draft).model_dump()

    @app.post("/projects/{project_id}/scenes/{scene_id}/extract-state")
    def extract_state(project_id: str, scene_id: str) -> dict:
        draft = draft_store.latest_for_scene(project_id, scene_id)
        if draft is None:
            raise HTTPException(status_code=404, detail="No draft for scene")
        candidates = extractor.extract(project_id=project_id, draft=draft)
        review.submit(candidates)
        return {"candidates": [candidate.model_dump() for candidate in candidates]}

    @app.get("/projects/{project_id}/facts/pending")
    def pending_facts(project_id: str) -> dict:
        return {"facts": [fact.model_dump() for fact in review.pending(project_id=project_id)]}

    @app.post("/projects/{project_id}/facts/{fact_id}/accept")
    def accept_fact(project_id: str, fact_id: str, request: ReviewRequest) -> dict:
        fact = review.accept(fact_id, reviewer=request.reviewer, note=request.note)
        return fact.model_dump()

    @app.post("/projects/{project_id}/facts/{fact_id}/reject")
    def reject_fact(project_id: str, fact_id: str, request: ReviewRequest) -> dict:
        fact = review.reject(fact_id, reviewer=request.reviewer, note=request.note)
        return fact.model_dump()

    return app


app = create_app()

