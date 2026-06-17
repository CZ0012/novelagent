from storygraph.demo import PROJECT_ID, SCENE_ID, build_fantasy_demo_graph
from storygraph.services.review_service import ReviewService
from storygraph.services.state_extraction import RuleBasedStateExtractor
from storygraph.stores.candidate_store import InMemoryCandidateStore
from storygraph.stores.draft_store import SQLiteDraftStore


def test_create_node_candidate_uses_graph_node_type_property():
    graph = build_fantasy_demo_graph()
    draft_store = SQLiteDraftStore()
    draft = draft_store.create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
        text=(
            "[[fact:fact_type=ItemState;subject=item_new_key;relation=EXISTS;"
            "operation=create_node;node_type=Item;name=New Key;confidence=0.9]]"
        ),
        summary="New item appears.",
    )
    candidates = RuleBasedStateExtractor().extract(project_id=PROJECT_ID, draft=draft)
    review = ReviewService(InMemoryCandidateStore(), graph)
    review.submit(candidates)

    review.accept(candidates[0].id, reviewer="author", note="The item is explicit.")

    node = graph.get_node("item_new_key")
    assert node.type == "Item"
    assert node.properties["name"] == "New Key"
