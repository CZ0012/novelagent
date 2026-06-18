"""Configured GraphStore selection for local runtimes."""

from __future__ import annotations

from dataclasses import dataclass

from storygraph.core.config import StoryGraphSettings
from storygraph.core.errors import GraphStoreError
from storygraph.stores.graph_base import GraphStore
from storygraph.stores.graph_neo4j import Neo4jGraphStore
from storygraph.stores.json_graph import load_json_graph, save_json_graph
from storygraph.stores.memory_graph import InMemoryGraphStore


@dataclass(frozen=True)
class ConfiguredGraphStore:
    graph: GraphStore
    backend: str


def open_configured_graph_store(
    settings: StoryGraphSettings,
    *,
    default_backend: str | None = None,
    seed_demo: bool = False,
) -> ConfiguredGraphStore:
    backend = _effective_backend(settings, default_backend)
    if backend == "json":
        return ConfiguredGraphStore(load_json_graph(settings.graph_path), backend)
    if backend == "memory":
        from storygraph.demo import build_fantasy_demo_graph

        graph = build_fantasy_demo_graph() if seed_demo else InMemoryGraphStore()
        return ConfiguredGraphStore(graph, backend)
    if backend == "neo4j":
        uri = _required(settings.neo4j_uri, "STORYGRAPH_NEO4J_URI")
        user = _required(settings.neo4j_user, "STORYGRAPH_NEO4J_USER")
        password = _required(settings.neo4j_password, "STORYGRAPH_NEO4J_PASSWORD")
        return ConfiguredGraphStore(
            Neo4jGraphStore(
                uri=uri,
                user=user,
                password=password,
                database=settings.neo4j_database,
            ),
            backend,
        )
    raise GraphStoreError("backend_unavailable", f"Unsupported graph backend: {backend}")


def save_configured_graph_store(
    configured: ConfiguredGraphStore,
    settings: StoryGraphSettings,
) -> None:
    if configured.backend != "json":
        return
    if not isinstance(configured.graph, InMemoryGraphStore):
        raise GraphStoreError("backend_unavailable", "JSON graph backend expected InMemoryGraphStore")
    save_json_graph(configured.graph, settings.graph_path)


def close_configured_graph_store(configured: ConfiguredGraphStore) -> None:
    close = getattr(configured.graph, "close", None)
    if callable(close):
        close()


def _effective_backend(settings: StoryGraphSettings, default_backend: str | None) -> str:
    if settings.graph_backend_explicit:
        return settings.graph_backend
    return (default_backend or settings.graph_backend).lower()


def _required(value: str | None, env_name: str) -> str:
    if value:
        return value
    raise GraphStoreError("backend_unavailable", f"{env_name} is required for Neo4j backend")
