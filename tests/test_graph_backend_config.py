import pytest
from fastapi.testclient import TestClient

from apps.api.main import create_app
from apps.cli.main import _runtime
from storygraph.core.config import StoryGraphSettings
from storygraph.core.errors import GraphStoreError
from storygraph.demo import PROJECT_ID
from storygraph.stores.graph_factory import open_configured_graph_store
from storygraph.stores.json_graph import load_json_graph
from storygraph.stores.memory_graph import InMemoryGraphStore


def test_cli_graph_backend_defaults_to_json_without_env(monkeypatch, tmp_path):
    monkeypatch.delenv("STORYGRAPH_GRAPH_BACKEND", raising=False)
    settings = StoryGraphSettings(tmp_path)

    configured = open_configured_graph_store(settings)

    assert configured.backend == "json"
    assert isinstance(configured.graph, InMemoryGraphStore)


def test_api_default_backend_uses_seeded_memory_without_env(monkeypatch, tmp_path):
    monkeypatch.delenv("STORYGRAPH_GRAPH_BACKEND", raising=False)
    settings = StoryGraphSettings(tmp_path)

    configured = open_configured_graph_store(
        settings,
        default_backend="memory",
        seed_demo=True,
    )

    assert configured.backend == "memory"
    assert configured.graph.get_node(PROJECT_ID).id == PROJECT_ID


def test_neo4j_backend_requires_connection_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("STORYGRAPH_GRAPH_BACKEND", "neo4j")
    monkeypatch.delenv("STORYGRAPH_NEO4J_URI", raising=False)
    monkeypatch.delenv("STORYGRAPH_NEO4J_USER", raising=False)
    monkeypatch.delenv("STORYGRAPH_NEO4J_PASSWORD", raising=False)
    settings = StoryGraphSettings(tmp_path)

    with pytest.raises(GraphStoreError) as exc_info:
        open_configured_graph_store(settings)

    assert exc_info.value.category == "backend_unavailable"
    assert "STORYGRAPH_NEO4J_URI" in str(exc_info.value)


def test_neo4j_backend_uses_configured_store_without_live_service(monkeypatch, tmp_path):
    created = {}

    class FakeNeo4jGraphStore:
        def __init__(self, **kwargs):
            created.update(kwargs)

    monkeypatch.setenv("STORYGRAPH_GRAPH_BACKEND", "neo4j")
    monkeypatch.setenv("STORYGRAPH_NEO4J_URI", "bolt://neo4j.example:7687")
    monkeypatch.setenv("STORYGRAPH_NEO4J_USER", "neo4j")
    monkeypatch.setenv("STORYGRAPH_NEO4J_PASSWORD", "secret")
    monkeypatch.setenv("STORYGRAPH_NEO4J_DATABASE", "story")
    monkeypatch.setattr(
        "storygraph.stores.graph_factory.Neo4jGraphStore",
        FakeNeo4jGraphStore,
    )
    settings = StoryGraphSettings(tmp_path)

    configured = open_configured_graph_store(settings)

    assert configured.backend == "neo4j"
    assert isinstance(configured.graph, FakeNeo4jGraphStore)
    assert created == {
        "uri": "bolt://neo4j.example:7687",
        "user": "neo4j",
        "password": "secret",
        "database": "story",
    }


def test_api_and_cli_reject_unknown_configured_backend(monkeypatch, tmp_path):
    monkeypatch.setenv("STORYGRAPH_GRAPH_BACKEND", "unknown")
    settings = StoryGraphSettings(tmp_path)

    with pytest.raises(GraphStoreError) as api_exc:
        create_app(settings)
    with pytest.raises(GraphStoreError) as cli_exc:
        _runtime(tmp_path)

    assert api_exc.value.category == "backend_unavailable"
    assert cli_exc.value.category == "backend_unavailable"


def test_api_json_backend_persists_project_create(monkeypatch, tmp_path):
    monkeypatch.setenv("STORYGRAPH_GRAPH_BACKEND", "json")
    settings = StoryGraphSettings(tmp_path)
    client = TestClient(create_app(settings))

    response = client.post(
        "/projects",
        json={"title": "Persisted API Project", "genre": "fantasy", "language": "zh-CN"},
    )

    assert response.status_code == 200
    project_id = response.json()["project_id"]
    graph = load_json_graph(settings.graph_path)
    assert graph.get_node(project_id).properties["title"] == "Persisted API Project"
