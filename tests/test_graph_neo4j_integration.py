import os

import pytest

pytest.importorskip("neo4j")

from storygraph.core.time import utc_now
from storygraph.models.graph import GraphNode
from storygraph.stores.graph_neo4j import Neo4jGraphStore


if os.environ.get("STORYGRAPH_RUN_NEO4J_TESTS") != "1":
    pytest.skip("Neo4j integration tests are opt-in.", allow_module_level=True)


def test_neo4j_store_persists_node_round_trip():
    store = Neo4jGraphStore(
        uri=os.environ["STORYGRAPH_NEO4J_URI"],
        user=os.environ["STORYGRAPH_NEO4J_USER"],
        password=os.environ["STORYGRAPH_NEO4J_PASSWORD"],
        database=os.environ.get("STORYGRAPH_NEO4J_DATABASE"),
    )
    node_id = f"test_character_{os.getpid()}"
    node = GraphNode(
        id=node_id,
        type="Character",
        status="DRAFT_FACT",
        created_at=utc_now(),
        updated_at=utc_now(),
        source_ref="test_graph_neo4j_integration",
        properties={"name": "Integration Test Character"},
    )

    try:
        created = store.create_node(node)
        loaded = store.get_node(created.id, include_non_canon=True)
        assert loaded == created
    finally:
        _cleanup_test_node(store, node_id)
        store.close()


def _cleanup_test_node(store: Neo4jGraphStore, node_id: str) -> None:
    with store.driver.session(database=store.database) as session:
        session.run("MATCH (n:StoryGraphNode {id: $id}) DETACH DELETE n", {"id": node_id})
