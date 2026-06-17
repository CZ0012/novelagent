from storygraph.core.errors import GraphStoreError
from storygraph.core.time import utc_now
from storygraph.demo import PROJECT_ID, build_fantasy_demo_graph
from storygraph.models.graph import GraphNode
from storygraph.stores.memory_graph import InMemoryGraphStore


def test_automated_create_node_cannot_write_canon():
    graph = InMemoryGraphStore()
    now = utc_now()
    node = GraphNode(
        id="character_auto",
        type="Character",
        status="CANON",
        created_at=now,
        updated_at=now,
        source_ref="test",
        properties={"name": "Auto"},
    )

    try:
        graph.create_node(node)
    except GraphStoreError as exc:
        assert exc.category == "canon_write_forbidden"
    else:
        raise AssertionError("Expected canon_write_forbidden")


def test_canon_reads_exclude_non_canon_nodes():
    graph = build_fantasy_demo_graph()
    now = utc_now()
    graph.create_node(
        GraphNode(
            id="character_hypothesis",
            type="Character",
            status="HYPOTHESIS",
            created_at=now,
            updated_at=now,
            source_ref="test",
            properties={"name": "Maybe"},
        )
    )

    assert graph.get_node(PROJECT_ID).id == PROJECT_ID
    try:
        graph.get_node("character_hypothesis")
    except GraphStoreError as exc:
        assert exc.category == "not_found"
    else:
        raise AssertionError("Expected non-canon node to be hidden")

