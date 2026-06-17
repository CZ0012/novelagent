import pytest

from storygraph.core.errors import GraphStoreError
from storygraph.core.time import utc_now
from storygraph.models.graph import GraphNode
from storygraph.stores.graph_neo4j import Neo4jGraphStore


def test_neo4j_backend_unavailable_without_driver_or_service():
    with pytest.raises(GraphStoreError) as exc_info:
        Neo4jGraphStore(
            uri="bolt://127.0.0.1:1",
            user="neo4j",
            password="bad-password",
        )

    assert exc_info.value.category == "backend_unavailable"


def test_neo4j_rejects_unsupported_labels_without_driver_connection():
    store = Neo4jGraphStore(
        uri="bolt://unused",
        user="neo4j",
        password="unused",
        driver=NoopDriver(),
        verify_connectivity=False,
    )
    node = GraphNode(
        id="bad",
        type="BadLabel",
        status="DRAFT_FACT",
        created_at=utc_now(),
        updated_at=utc_now(),
        source_ref="test",
        properties={},
    )

    with pytest.raises(GraphStoreError) as exc_info:
        store.create_node(node)

    assert exc_info.value.category == "conflict_detected"


def test_neo4j_automated_create_node_cannot_write_canon_without_driver_connection():
    store = Neo4jGraphStore(
        uri="bolt://unused",
        user="neo4j",
        password="unused",
        driver=NoopDriver(),
        verify_connectivity=False,
    )
    node = GraphNode(
        id="character_auto",
        type="Character",
        status="CANON",
        created_at=utc_now(),
        updated_at=utc_now(),
        source_ref="test",
        properties={"name": "Auto"},
    )

    with pytest.raises(GraphStoreError) as exc_info:
        store.create_node(node)

    assert exc_info.value.category == "canon_write_forbidden"


class NoopDriver:
    def verify_connectivity(self):
        return None

    def close(self):
        return None

    def session(self, database=None):
        raise AssertionError("session should not be opened for label validation")
