"""Neo4j Graph Store backend.

The first Neo4j backend favors contract parity with ``InMemoryGraphStore`` over
query cleverness. Complex reads are snapshotted into the in-memory implementation
so canon filtering and temporal scope rules stay identical while the backend
boundary becomes available for real deployments.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from storygraph.core.errors import GraphStoreError
from storygraph.core.ids import new_id
from storygraph.core.time import utc_now
from storygraph.models.candidate import CandidateFact
from storygraph.models.context import KnowledgeBoundary
from storygraph.models.graph import EDGE_LABELS, NODE_LABELS, EventLogEntry, GraphNode, GraphRelationship
from storygraph.stores.graph_base import GraphStore
from storygraph.stores.memory_graph import InMemoryGraphStore


class Neo4jGraphStore(GraphStore):
    def __init__(
        self,
        *,
        uri: str,
        user: str,
        password: str,
        database: str | None = None,
        driver: Any | None = None,
        verify_connectivity: bool = True,
    ) -> None:
        self.database = database
        if driver is None:
            try:
                from neo4j import GraphDatabase
            except Exception as exc:  # pragma: no cover - depends on optional extra
                raise GraphStoreError(
                    "backend_unavailable",
                    "Neo4j driver is not installed. Install storygraph-agent[neo4j].",
                ) from exc
            try:
                driver = GraphDatabase.driver(uri, auth=(user, password))
            except Exception as exc:  # pragma: no cover - driver-specific
                raise GraphStoreError("backend_unavailable", f"Neo4j driver unavailable: {exc}") from exc
        self.driver = driver
        if verify_connectivity:
            try:
                self.driver.verify_connectivity()
            except Exception as exc:
                raise GraphStoreError("backend_unavailable", f"Neo4j service unavailable: {exc}") from exc

    def close(self) -> None:
        self.driver.close()

    def get_node(self, node_id: str, *, include_non_canon: bool = False) -> GraphNode:
        node = self._read_one(
            "MATCH (n:StoryGraphNode {id: $id}) RETURN n",
            {"id": node_id},
            "n",
        )
        if node is None:
            raise GraphStoreError("not_found", f"Node not found: {node_id}")
        graph_node = self._node_from_entity(node)
        if graph_node.status != "CANON" and not include_non_canon:
            raise GraphStoreError("not_found", f"Node is not canon: {node_id}")
        return graph_node

    def create_node(self, node: GraphNode, *, allow_canon: bool = False) -> GraphNode:
        self._validate_node(node)
        if node.status == "CANON" and not allow_canon:
            raise GraphStoreError("canon_write_forbidden", "Automated create_node cannot write CANON")
        if self._node_exists(node.id):
            raise GraphStoreError("duplicate_id", f"Duplicate node id: {node.id}")
        label = self._safe_node_label(node.type)
        props = self._node_props(node)
        created = self._write_one(
            f"CREATE (n:StoryGraphNode:`{label}`) SET n = $props RETURN n",
            {"props": props},
            "n",
        )
        return self._node_from_entity(created)

    def update_node(
        self,
        node_id: str,
        properties: dict,
        *,
        reviewer: str,
        rationale: str,
        source_ref: str,
        event_id: str | None = None,
    ) -> GraphNode:
        node = self.get_node(node_id, include_non_canon=True)
        updated = node.model_copy(
            update={
                "properties": {**node.properties, **properties},
                "updated_at": utc_now(),
                "event_id": event_id or new_id("evt"),
                "reviewer": reviewer,
                "reviewed_at": utc_now(),
                "rationale": rationale,
                "source_ref": source_ref,
            }
        )
        entity = self._write_one(
            "MATCH (n:StoryGraphNode {id: $id}) SET n += $props RETURN n",
            {"id": node_id, "props": self._node_props(updated)},
            "n",
        )
        self._record_event(
            operation="update_node",
            target=node_id,
            source_ref=source_ref,
            reviewer=reviewer,
            rationale=rationale,
            payload=properties,
            event_id=updated.event_id,
        )
        return self._node_from_entity(entity)

    def create_relation(
        self, relation: GraphRelationship, *, allow_canon: bool = False
    ) -> GraphRelationship:
        self._validate_relation(relation)
        if relation.status == "CANON" and not allow_canon:
            raise GraphStoreError("canon_write_forbidden", "Automated create_relation cannot write CANON")
        if self._relationship_exists(relation.id):
            raise GraphStoreError("duplicate_id", f"Duplicate relationship id: {relation.id}")
        if not self._node_exists(relation.source_id) or not self._node_exists(relation.target_id):
            raise GraphStoreError("not_found", "Relationship endpoints must exist")
        rel_type = self._safe_edge_label(relation.type)
        created = self._write_one(
            (
                "MATCH (s:StoryGraphNode {id: $source_id}), (t:StoryGraphNode {id: $target_id}) "
                f"CREATE (s)-[r:`{rel_type}`]->(t) SET r = $props RETURN r"
            ),
            {
                "source_id": relation.source_id,
                "target_id": relation.target_id,
                "props": self._relationship_props(relation),
            },
            "r",
        )
        return self._relationship_from_entity(created)

    def update_relation(
        self,
        relation_id: str,
        properties: dict,
        *,
        reviewer: str,
        rationale: str,
        source_ref: str,
        event_id: str | None = None,
    ) -> GraphRelationship:
        relation = self._get_relationship(relation_id)
        updated = relation.model_copy(
            update={
                "properties": {**relation.properties, **properties},
                "updated_at": utc_now(),
                "event_id": event_id or new_id("evt"),
                "reviewer": reviewer,
                "reviewed_at": utc_now(),
                "rationale": rationale,
                "source_ref": source_ref,
            }
        )
        entity = self._write_one(
            "MATCH ()-[r {id: $id}]->() SET r += $props RETURN r",
            {"id": relation_id, "props": self._relationship_props(updated)},
            "r",
        )
        self._record_event(
            operation="update_relation",
            target=relation_id,
            source_ref=source_ref,
            reviewer=reviewer,
            rationale=rationale,
            payload=properties,
            event_id=updated.event_id,
        )
        return self._relationship_from_entity(entity)

    def query_neighbors(
        self,
        source_id: str,
        *,
        edge_labels: Iterable[str] | None = None,
        node_labels: Iterable[str] | None = None,
        statuses: Iterable[str] | None = None,
        hop_limit: int,
    ) -> dict[str, list]:
        return self._snapshot().query_neighbors(
            source_id,
            edge_labels=edge_labels,
            node_labels=node_labels,
            statuses=statuses,
            hop_limit=hop_limit,
        )

    def query_scene_context(self, scene_id: str) -> dict:
        return self._snapshot().query_scene_context(scene_id)

    def get_character_knowledge(
        self,
        character_id: str,
        *,
        scene_id: str | None = None,
        timeline_position: str | None = None,
    ) -> KnowledgeBoundary:
        return self._snapshot().get_character_knowledge(
            character_id,
            scene_id=scene_id,
            timeline_position=timeline_position,
        )

    def get_unresolved_foreshadowing(self, **filters: str) -> list[GraphNode]:
        return self._snapshot().get_unresolved_foreshadowing(**filters)

    def commit_candidate_fact(
        self, candidate: CandidateFact, *, reviewer: str, rationale: str
    ) -> EventLogEntry:
        memory = self._snapshot()
        before_relationships = set(memory.relationships)
        before_nodes = set(memory.nodes)
        event = memory.commit_candidate_fact(candidate, reviewer=reviewer, rationale=rationale)
        for node_id, node in memory.nodes.items():
            if node_id not in before_nodes:
                self.create_node(node, allow_canon=True)
            elif node != self.get_node(node_id, include_non_canon=True):
                self._write_node_model(node)
        for relation_id, relation in memory.relationships.items():
            if relation_id not in before_relationships:
                self.create_relation(relation, allow_canon=True)
            elif relation != self._get_relationship(relation_id):
                self._write_relationship_model(relation)
        self._record_event_model(event)
        return event

    def _snapshot(self) -> InMemoryGraphStore:
        memory = InMemoryGraphStore()
        for node in self._read_many("MATCH (n:StoryGraphNode) RETURN n", {}, "n"):
            graph_node = self._node_from_entity(node)
            memory.nodes[graph_node.id] = graph_node
        for relation in self._read_many("MATCH ()-[r]->() WHERE r.id IS NOT NULL RETURN r", {}, "r"):
            graph_relation = self._relationship_from_entity(relation)
            memory.relationships[graph_relation.id] = graph_relation
        for event in self._read_many("MATCH (e:StoryGraphEvent) RETURN e", {}, "e"):
            memory.event_log.append(self._event_from_entity(event))
        return memory

    def _node_exists(self, node_id: str) -> bool:
        return (
            self._read_one(
                "MATCH (n:StoryGraphNode {id: $id}) RETURN n.id AS id",
                {"id": node_id},
                "id",
            )
            is not None
        )

    def _relationship_exists(self, relation_id: str) -> bool:
        return (
            self._read_one(
                "MATCH ()-[r {id: $id}]->() RETURN r.id AS id",
                {"id": relation_id},
                "id",
            )
            is not None
        )

    def _get_relationship(self, relation_id: str) -> GraphRelationship:
        relation = self._read_one(
            "MATCH ()-[r {id: $id}]->() RETURN r",
            {"id": relation_id},
            "r",
        )
        if relation is None:
            raise GraphStoreError("not_found", f"Relationship not found: {relation_id}")
        return self._relationship_from_entity(relation)

    def _write_node_model(self, node: GraphNode) -> GraphNode:
        entity = self._write_one(
            "MATCH (n:StoryGraphNode {id: $id}) SET n += $props RETURN n",
            {"id": node.id, "props": self._node_props(node)},
            "n",
        )
        return self._node_from_entity(entity)

    def _write_relationship_model(self, relation: GraphRelationship) -> GraphRelationship:
        entity = self._write_one(
            "MATCH ()-[r {id: $id}]->() SET r += $props RETURN r",
            {"id": relation.id, "props": self._relationship_props(relation)},
            "r",
        )
        return self._relationship_from_entity(entity)

    def _record_event(
        self,
        *,
        operation: str,
        target: str,
        source_ref: str,
        reviewer: str,
        rationale: str,
        payload: dict,
        event_id: str | None = None,
    ) -> EventLogEntry:
        event = EventLogEntry(
            event_id=event_id or new_id("evt"),
            operation=operation,  # type: ignore[arg-type]
            target=target,
            source_ref=source_ref,
            reviewer=reviewer,
            rationale=rationale,
            created_at=utc_now(),
            payload=payload,
        )
        self._record_event_model(event)
        return event

    def _record_event_model(self, event: EventLogEntry) -> None:
        self._write_one(
            """
            MERGE (e:StoryGraphEvent {event_id: $event_id})
            SET e = $props
            RETURN e
            """,
            {
                "event_id": event.event_id,
                "props": {
                    "event_id": event.event_id,
                    "operation": event.operation,
                    "target": event.target,
                    "source_ref": event.source_ref,
                    "reviewer": event.reviewer,
                    "rationale": event.rationale,
                    "created_at": event.created_at,
                    "payload_json": json.dumps(event.payload),
                },
            },
            "e",
        )

    def _read_one(self, query: str, params: dict, key: str) -> Any | None:
        rows = self._read_many(query, params, key)
        return rows[0] if rows else None

    def _read_many(self, query: str, params: dict, key: str) -> list[Any]:
        try:
            with self.driver.session(database=self.database) as session:
                return [record[key] for record in session.run(query, params)]
        except GraphStoreError:
            raise
        except Exception as exc:
            raise GraphStoreError("backend_unavailable", f"Neo4j read failed: {exc}") from exc

    def _write_one(self, query: str, params: dict, key: str) -> Any:
        try:
            with self.driver.session(database=self.database) as session:
                record = session.run(query, params).single()
        except GraphStoreError:
            raise
        except Exception as exc:
            raise GraphStoreError("backend_unavailable", f"Neo4j write failed: {exc}") from exc
        if record is None:
            raise GraphStoreError("backend_unavailable", "Neo4j write returned no record")
        return record[key]

    @staticmethod
    def _node_props(node: GraphNode) -> dict:
        return {
            "id": node.id,
            "type": node.type,
            "status": node.status,
            "created_at": node.created_at,
            "updated_at": node.updated_at,
            "source_ref": node.source_ref,
            "event_id": node.event_id,
            "reviewer": node.reviewer,
            "reviewed_at": node.reviewed_at,
            "rationale": node.rationale,
            "properties_json": json.dumps(node.properties),
        }

    @staticmethod
    def _relationship_props(relation: GraphRelationship) -> dict:
        return {
            "id": relation.id,
            "type": relation.type,
            "status": relation.status,
            "created_at": relation.created_at,
            "updated_at": relation.updated_at,
            "source_ref": relation.source_ref,
            "event_id": relation.event_id,
            "reviewer": relation.reviewer,
            "reviewed_at": relation.reviewed_at,
            "rationale": relation.rationale,
            "source_id": relation.source_id,
            "target_id": relation.target_id,
            "properties_json": json.dumps(relation.properties),
        }

    @staticmethod
    def _node_from_entity(entity: Any) -> GraphNode:
        data = dict(entity)
        return GraphNode(
            id=data["id"],
            type=data["type"],
            status=data["status"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            source_ref=data["source_ref"],
            event_id=data.get("event_id"),
            reviewer=data.get("reviewer"),
            reviewed_at=data.get("reviewed_at"),
            rationale=data.get("rationale"),
            properties=json.loads(data.get("properties_json") or "{}"),
        )

    @staticmethod
    def _relationship_from_entity(entity: Any) -> GraphRelationship:
        data = dict(entity)
        return GraphRelationship(
            id=data["id"],
            type=data["type"],
            status=data["status"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            source_ref=data["source_ref"],
            event_id=data.get("event_id"),
            reviewer=data.get("reviewer"),
            reviewed_at=data.get("reviewed_at"),
            rationale=data.get("rationale"),
            source_id=data["source_id"],
            target_id=data["target_id"],
            properties=json.loads(data.get("properties_json") or "{}"),
        )

    @staticmethod
    def _event_from_entity(entity: Any) -> EventLogEntry:
        data = dict(entity)
        return EventLogEntry(
            event_id=data["event_id"],
            operation=data["operation"],
            target=data["target"],
            source_ref=data["source_ref"],
            reviewer=data["reviewer"],
            rationale=data["rationale"],
            created_at=data["created_at"],
            payload=json.loads(data.get("payload_json") or "{}"),
        )

    @staticmethod
    def _validate_node(node: GraphNode) -> None:
        if node.type not in NODE_LABELS:
            raise GraphStoreError("conflict_detected", f"Unsupported node label: {node.type}")
        if not node.source_ref:
            raise GraphStoreError("missing_provenance", "Node source_ref is required")

    @staticmethod
    def _validate_relation(relation: GraphRelationship) -> None:
        if relation.type not in EDGE_LABELS:
            raise GraphStoreError("conflict_detected", f"Unsupported edge label: {relation.type}")
        if not relation.source_ref:
            raise GraphStoreError("missing_provenance", "Relationship source_ref is required")

    @staticmethod
    def _safe_node_label(label: str) -> str:
        if label not in NODE_LABELS:
            raise GraphStoreError("conflict_detected", f"Unsupported node label: {label}")
        return label

    @staticmethod
    def _safe_edge_label(label: str) -> str:
        if label not in EDGE_LABELS:
            raise GraphStoreError("conflict_detected", f"Unsupported edge label: {label}")
        return label

