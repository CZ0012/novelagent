import pytest

from storygraph.core.errors import GraphStoreError
from storygraph.core.time import utc_now
from storygraph.demo import ITEM_ID, LOCATION_ID, PROJECT_ID, SCENE_ID, build_fantasy_demo_graph
from storygraph.models.graph import GraphNode, GraphRelationship
from storygraph.services.state_extraction import RuleBasedStateExtractor
from storygraph.stores.draft_store import SQLiteDraftStore
from storygraph.stores.graph_neo4j import Neo4jGraphStore


def test_neo4j_backend_unavailable_when_connectivity_fails():
    with pytest.raises(GraphStoreError) as exc_info:
        Neo4jGraphStore(
            uri="bolt://127.0.0.1:1",
            user="neo4j",
            password="bad-password",
            driver=FailingConnectivityDriver(),
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


def test_neo4j_automated_create_relation_cannot_write_canon_without_driver_connection():
    store = Neo4jGraphStore(
        uri="bolt://unused",
        user="neo4j",
        password="unused",
        driver=NoopDriver(),
        verify_connectivity=False,
    )
    relation = GraphRelationship(
        id="rel_auto",
        type="KNOWS",
        status="CANON",
        created_at=utc_now(),
        updated_at=utc_now(),
        source_ref="test",
        source_id="character_a",
        target_id="character_b",
        properties={},
    )

    with pytest.raises(GraphStoreError) as exc_info:
        store.create_relation(relation)

    assert exc_info.value.category == "canon_write_forbidden"


def test_neo4j_public_relationship_read_respects_canon_status(monkeypatch):
    store = Neo4jGraphStore(
        uri="bolt://unused",
        user="neo4j",
        password="unused",
        driver=NoopDriver(),
        verify_connectivity=False,
    )
    relation = GraphRelationship(
        id="rel_hypothesis",
        type="KNOWS",
        status="HYPOTHESIS",
        created_at=utc_now(),
        updated_at=utc_now(),
        source_ref="test",
        source_id="character_a",
        target_id="character_b",
        properties={"project_id": "project_test"},
    )
    monkeypatch.setattr(store, "_get_relationship", lambda relation_id: relation)

    assert store.get_relationship(
        relation.id,
        include_non_canon=True,
    ) == relation
    with pytest.raises(GraphStoreError) as exc_info:
        store.get_relationship(relation.id)

    assert exc_info.value.category == "not_found"


def test_candidate_update_and_all_provenance_events_share_one_write_transaction(monkeypatch):
    graph = build_fantasy_demo_graph()
    candidate = _reviewed_candidate(
        graph,
        (
            f"[[fact:fact_type=ItemState;subject={ITEM_ID};relation=HAS_STATE;"
            "operation=update_node;current_status=found;confidence=0.95]]"
        ),
    )
    driver = AtomicWriteDriver()
    store = Neo4jGraphStore(
        uri="bolt://unused",
        user="neo4j",
        password="unused",
        driver=driver,
        verify_connectivity=False,
    )
    monkeypatch.setattr(store, "_snapshot", lambda: graph)

    final_event = store.commit_candidate_fact(
        candidate,
        reviewer="author",
        rationale="Reviewed update.",
    )

    assert driver.execute_write_calls == 1
    assert len(driver.committed) == 3
    node_write = next(params for _, params in driver.committed if params.get("id") == ITEM_ID)
    event_writes = [params for _, params in driver.committed if "event_id" in params]
    assert {params["props"]["operation"] for params in event_writes} == {
        "update_node",
        "commit_candidate_fact",
    }
    assert node_write["props"]["event_id"] in {
        params["event_id"] for params in event_writes
    }
    assert final_event.event_id in {params["event_id"] for params in event_writes}


def test_candidate_relation_and_event_share_one_write_transaction(monkeypatch):
    graph = build_fantasy_demo_graph()
    candidate = _reviewed_candidate(
        graph,
        (
            f"[[fact:fact_type=ItemState;subject={ITEM_ID};relation=LOCATED_AT;"
            f"object={LOCATION_ID};confidence=0.95]]"
        ),
    )
    driver = AtomicWriteDriver()
    store = Neo4jGraphStore(
        uri="bolt://unused",
        user="neo4j",
        password="unused",
        driver=driver,
        verify_connectivity=False,
    )
    monkeypatch.setattr(store, "_snapshot", lambda: graph)

    event = store.commit_candidate_fact(candidate, reviewer="author", rationale="Reviewed relation.")

    assert driver.execute_write_calls == 1
    assert len(driver.committed) == 2
    relation_write = next(params for _, params in driver.committed if "source_id" in params)
    event_write = next(params for _, params in driver.committed if "event_id" in params)
    assert relation_write["props"]["event_id"] == event.event_id
    assert event_write["event_id"] == event.event_id


def test_candidate_transaction_failure_rolls_back_graph_and_events(monkeypatch):
    graph = build_fantasy_demo_graph()
    candidate = _reviewed_candidate(
        graph,
        (
            f"[[fact:fact_type=ItemState;subject={ITEM_ID};relation=HAS_STATE;"
            "operation=update_node;current_status=found;confidence=0.95]]"
        ),
    )
    driver = AtomicWriteDriver(fail_at=2)
    store = Neo4jGraphStore(
        uri="bolt://unused",
        user="neo4j",
        password="unused",
        driver=driver,
        verify_connectivity=False,
    )
    monkeypatch.setattr(store, "_snapshot", lambda: graph)

    with pytest.raises(GraphStoreError, match="candidate commit failed") as exc_info:
        store.commit_candidate_fact(candidate, reviewer="author", rationale="Must roll back.")

    assert exc_info.value.category == "backend_unavailable"
    assert driver.execute_write_calls == 1
    assert driver.rollbacks == 1
    assert driver.committed == []


def _reviewed_candidate(graph, text):
    draft = SQLiteDraftStore().create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
        content_language="en-US",
        text=text,
        summary="Neo4j transaction candidate.",
    )
    candidate = RuleBasedStateExtractor().extract(project_id=PROJECT_ID, draft=draft)[0]
    candidate = graph.validate_candidate_scope(candidate)
    return candidate.model_copy(
        update={
            "status": "ACCEPTED_FOR_CANON",
            "review": candidate.review.model_copy(
                update={
                    "status": "accepted",
                    "reviewer": "author",
                    "reviewed_at": utc_now(),
                }
            ),
        }
    )


class FailingConnectivityDriver:
    def verify_connectivity(self):
        raise RuntimeError("service unavailable")

    def close(self):
        return None


class NoopDriver:
    def verify_connectivity(self):
        return None

    def close(self):
        return None

    def session(self, database=None):
        raise AssertionError("session should not be opened for label validation")


class AtomicWriteDriver:
    def __init__(self, *, fail_at=None):
        self.fail_at = fail_at
        self.committed = []
        self.execute_write_calls = 0
        self.rollbacks = 0

    def close(self):
        return None

    def session(self, database=None):
        return AtomicWriteSession(self)


class AtomicWriteSession:
    def __init__(self, driver):
        self.driver = driver

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute_write(self, callback, *args):
        self.driver.execute_write_calls += 1
        staged = []
        transaction = AtomicTransaction(staged, fail_at=self.driver.fail_at)
        try:
            result = callback(transaction, *args)
        except Exception:
            self.driver.rollbacks += 1
            raise
        self.driver.committed.extend(staged)
        return result


class AtomicTransaction:
    def __init__(self, staged, *, fail_at=None):
        self.staged = staged
        self.fail_at = fail_at
        self.calls = 0

    def run(self, query, params):
        self.calls += 1
        self.staged.append((query, params))
        if self.fail_at == self.calls:
            raise RuntimeError("transaction write failed")
        return AtomicResult()


class AtomicResult:
    def single(self):
        return {"ok": True}
