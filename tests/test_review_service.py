from storygraph.demo import ITEM_ID, LOCATION_ID, PROJECT_ID, SCENE_ID, build_fantasy_demo_graph
from storygraph.services.review_service import ReviewService
from storygraph.services.state_extraction import RuleBasedStateExtractor
from storygraph.stores.candidate_store import InMemoryCandidateStore
from storygraph.stores.draft_store import SQLiteDraftStore


def test_candidate_fact_requires_review_before_canon_commit():
    graph = build_fantasy_demo_graph()
    draft_store = SQLiteDraftStore()
    draft = draft_store.create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
        text=(
            "Lin Jin finds the clue. "
            f"[[fact:fact_type=ItemState;subject={ITEM_ID};relation=LOCATED_AT;"
            f"object={LOCATION_ID};confidence=0.95]]"
        ),
        summary="Item found.",
    )
    candidates = RuleBasedStateExtractor().extract(project_id=PROJECT_ID, draft=draft)
    review = ReviewService(InMemoryCandidateStore(), graph)
    review.submit(candidates)

    assert len(review.pending(project_id=PROJECT_ID)) == 1
    assert not any(
        relation.type == "LOCATED_AT" and relation.source_id == ITEM_ID
        for relation in graph.relationships.values()
    )

    accepted = review.accept(candidates[0].id, reviewer="author", note="Seen in draft.")

    assert accepted.status == "ACCEPTED_FOR_CANON"
    assert accepted.review.status == "accepted"
    assert any(
        relation.type == "LOCATED_AT"
        and relation.source_id == ITEM_ID
        and relation.target_id == LOCATION_ID
        for relation in graph.relationships.values()
    )
    assert graph.event_log.list()

