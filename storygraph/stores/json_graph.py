"""JSON persistence for the local in-memory graph store.

This is a small CLI/workbench persistence adapter. It keeps the MVP local and
inspectable while the production graph backend remains behind `GraphStore`.
"""

from __future__ import annotations

import json
from pathlib import Path

from storygraph.models.graph import EventLogEntry, GraphNode, GraphRelationship
from storygraph.stores.event_log import InMemoryEventLog
from storygraph.stores.memory_graph import InMemoryGraphStore


def load_json_graph(path: str | Path) -> InMemoryGraphStore:
    graph_path = Path(path)
    if not graph_path.exists():
        return InMemoryGraphStore()
    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    event_log = InMemoryEventLog()
    for event_payload in payload.get("event_log", []):
        event_log.append(EventLogEntry.model_validate(event_payload))
    graph = InMemoryGraphStore(event_log=event_log)
    graph.nodes = {
        node_payload["id"]: GraphNode.model_validate(node_payload)
        for node_payload in payload.get("nodes", [])
    }
    graph.relationships = {
        relation_payload["id"]: GraphRelationship.model_validate(relation_payload)
        for relation_payload in payload.get("relationships", [])
    }
    return graph


def save_json_graph(graph: InMemoryGraphStore, path: str | Path) -> None:
    graph_path = Path(path)
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "nodes": [
            node.model_dump()
            for node in sorted(graph.nodes.values(), key=lambda item: item.id)
        ],
        "relationships": [
            relation.model_dump()
            for relation in sorted(graph.relationships.values(), key=lambda item: item.id)
        ],
        "event_log": [event.model_dump() for event in graph.event_log.list()],
    }
    temp_path = graph_path.with_suffix(f"{graph_path.suffix}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(graph_path)
