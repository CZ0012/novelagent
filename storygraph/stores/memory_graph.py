"""Canon-safe in-memory Graph Store implementation for local MVP and tests."""

from __future__ import annotations

from collections import deque
from typing import Iterable

from storygraph.core.errors import GraphStoreError
from storygraph.core.ids import new_id
from storygraph.core.time import utc_now
from storygraph.models.candidate import CandidateFact
from storygraph.models.context import KnowledgeBoundary
from storygraph.models.graph import EDGE_LABELS, NODE_LABELS, EventLogEntry, GraphNode, GraphRelationship
from storygraph.stores.event_log import InMemoryEventLog
from storygraph.stores.graph_base import GraphStore


class InMemoryGraphStore(GraphStore):
    def __init__(self, event_log: InMemoryEventLog | None = None) -> None:
        self.nodes: dict[str, GraphNode] = {}
        self.relationships: dict[str, GraphRelationship] = {}
        self.event_log = event_log or InMemoryEventLog()

    def get_node(self, node_id: str, *, include_non_canon: bool = False) -> GraphNode:
        node = self.nodes.get(node_id)
        if node is None:
            raise GraphStoreError("not_found", f"Node not found: {node_id}")
        if node.status != "CANON" and not include_non_canon:
            raise GraphStoreError("not_found", f"Node is not canon: {node_id}")
        return node

    def create_node(self, node: GraphNode, *, allow_canon: bool = False) -> GraphNode:
        self._validate_node(node)
        if node.id in self.nodes:
            raise GraphStoreError("duplicate_id", f"Duplicate node id: {node.id}")
        if node.status == "CANON" and not allow_canon:
            raise GraphStoreError("canon_write_forbidden", "Automated create_node cannot write CANON")
        self.nodes[node.id] = node
        return node

    def seed_canon_node(
        self,
        *,
        node_id: str,
        node_type: str,
        properties: dict,
        source_ref: str = "manual_seed",
        reviewer: str = "author",
        rationale: str = "Manual project seed.",
    ) -> GraphNode:
        now = utc_now()
        node = GraphNode(
            id=node_id,
            type=node_type,
            status="CANON",
            created_at=now,
            updated_at=now,
            source_ref=source_ref,
            event_id=new_id("evt"),
            reviewer=reviewer,
            reviewed_at=now,
            rationale=rationale,
            properties=properties,
        )
        self.create_node(node, allow_canon=True)
        self._record_event(
            operation="create_node",
            target=node.id,
            source_ref=source_ref,
            reviewer=reviewer,
            rationale=rationale,
            payload=node.model_dump(),
            event_id=node.event_id,
        )
        return node

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
        now = utc_now()
        updated = node.model_copy(
            update={
                "properties": {**node.properties, **properties},
                "updated_at": now,
                "event_id": event_id or new_id("evt"),
                "reviewer": reviewer,
                "reviewed_at": now,
                "rationale": rationale,
                "source_ref": source_ref,
            }
        )
        self.nodes[node_id] = updated
        self._record_event(
            operation="update_node",
            target=node_id,
            source_ref=source_ref,
            reviewer=reviewer,
            rationale=rationale,
            payload=properties,
            event_id=updated.event_id,
        )
        return updated

    def create_relation(
        self, relation: GraphRelationship, *, allow_canon: bool = False
    ) -> GraphRelationship:
        self._validate_relation(relation)
        if relation.id in self.relationships:
            raise GraphStoreError("duplicate_id", f"Duplicate relationship id: {relation.id}")
        if relation.status == "CANON" and not allow_canon:
            raise GraphStoreError("canon_write_forbidden", "Automated create_relation cannot write CANON")
        if relation.source_id not in self.nodes or relation.target_id not in self.nodes:
            raise GraphStoreError("not_found", "Relationship endpoints must exist")
        self.relationships[relation.id] = relation
        return relation

    def seed_canon_relation(
        self,
        *,
        relation_id: str,
        relation_type: str,
        source_id: str,
        target_id: str,
        properties: dict | None = None,
        source_ref: str = "manual_seed",
        reviewer: str = "author",
        rationale: str = "Manual project seed.",
    ) -> GraphRelationship:
        now = utc_now()
        relation = GraphRelationship(
            id=relation_id,
            type=relation_type,
            status="CANON",
            created_at=now,
            updated_at=now,
            source_ref=source_ref,
            event_id=new_id("evt"),
            reviewer=reviewer,
            reviewed_at=now,
            rationale=rationale,
            source_id=source_id,
            target_id=target_id,
            properties=properties or {},
        )
        self.create_relation(relation, allow_canon=True)
        self._record_event(
            operation="create_relation",
            target=relation.id,
            source_ref=source_ref,
            reviewer=reviewer,
            rationale=rationale,
            payload=relation.model_dump(),
            event_id=relation.event_id,
        )
        return relation

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
        relation = self.relationships.get(relation_id)
        if relation is None:
            raise GraphStoreError("not_found", f"Relationship not found: {relation_id}")
        now = utc_now()
        updated = relation.model_copy(
            update={
                "properties": {**relation.properties, **properties},
                "updated_at": now,
                "event_id": event_id or new_id("evt"),
                "reviewer": reviewer,
                "reviewed_at": now,
                "rationale": rationale,
                "source_ref": source_ref,
            }
        )
        self.relationships[relation_id] = updated
        self._record_event(
            operation="update_relation",
            target=relation_id,
            source_ref=source_ref,
            reviewer=reviewer,
            rationale=rationale,
            payload=properties,
            event_id=updated.event_id,
        )
        return updated

    def query_neighbors(
        self,
        source_id: str,
        *,
        edge_labels: Iterable[str] | None = None,
        node_labels: Iterable[str] | None = None,
        statuses: Iterable[str] | None = None,
        hop_limit: int,
    ) -> dict[str, list]:
        if hop_limit < 1:
            raise GraphStoreError("conflict_detected", "hop_limit must be explicit and >= 1")
        self.get_node(source_id, include_non_canon=True)
        allowed_edges = set(edge_labels) if edge_labels else None
        allowed_nodes = set(node_labels) if node_labels else None
        allowed_statuses = set(statuses) if statuses else {"CANON"}

        found_node_ids: set[str] = set()
        found_relation_ids: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(source_id, 0)])
        visited: set[tuple[str, int]] = set()
        while queue:
            current_id, depth = queue.popleft()
            if (current_id, depth) in visited or depth >= hop_limit:
                continue
            visited.add((current_id, depth))
            for relation in sorted(self.relationships.values(), key=lambda item: item.id):
                if relation.status not in allowed_statuses:
                    continue
                if allowed_edges and relation.type not in allowed_edges:
                    continue
                if relation.source_id == current_id:
                    neighbor_id = relation.target_id
                elif relation.target_id == current_id:
                    neighbor_id = relation.source_id
                else:
                    continue
                neighbor = self.nodes[neighbor_id]
                if neighbor.status not in allowed_statuses:
                    continue
                if allowed_nodes and neighbor.type not in allowed_nodes:
                    continue
                found_node_ids.add(neighbor_id)
                found_relation_ids.add(relation.id)
                queue.append((neighbor_id, depth + 1))
        return {
            "nodes": [self.nodes[node_id] for node_id in sorted(found_node_ids)],
            "relationships": [self.relationships[rel_id] for rel_id in sorted(found_relation_ids)],
        }

    def query_scene_context(self, scene_id: str) -> dict:
        scene = self.get_node(scene_id)
        props = scene.properties
        required = list(dict.fromkeys([props.get("pov_character_id"), *props.get("required_characters", [])]))
        required = [item for item in required if item]
        characters = [self.get_node(character_id) for character_id in required]
        location = self.get_node(props["location_id"]) if props.get("location_id") else None
        active_relationships: list[GraphRelationship] = []
        for character_id in required:
            neighbors = self.query_neighbors(
                character_id,
                edge_labels=[
                    "KNOWS",
                    "LOVES",
                    "HATES",
                    "LOYAL_TO",
                    "BETRAYED",
                    "FAMILY_OF",
                    "MENTOR_OF",
                    "RIVAL_OF",
                    "SUSPECTS",
                ],
                hop_limit=1,
            )
            active_relationships.extend(neighbors["relationships"])
        return {
            "scene": scene,
            "characters": characters,
            "location": location,
            "active_relationships": sorted(
                {relation.id: relation for relation in active_relationships}.values(),
                key=lambda relation: relation.id,
            ),
            "world_rules": [
                node
                for node in self.nodes.values()
                if node.type == "WorldRule" and node.status == "CANON"
            ],
            "unresolved_foreshadowing": self.get_unresolved_foreshadowing(),
        }

    def get_character_knowledge(
        self,
        character_id: str,
        *,
        scene_id: str | None = None,
        timeline_position: str | None = None,
    ) -> KnowledgeBoundary:
        self.get_node(character_id)
        knows: list[str] = []
        falsely_believes: list[str] = []
        suspects: list[str] = []
        hides: list[str] = []
        refs: list[str] = []
        for relation in sorted(self.relationships.values(), key=lambda item: item.id):
            if relation.status != "CANON" or relation.source_id != character_id:
                continue
            if relation.type == "KNOWS_SECRET":
                knows.append(relation.target_id)
            elif relation.type == "BELIEVES_FALSELY":
                falsely_believes.append(relation.target_id)
            elif relation.type == "SUSPECTS":
                suspects.append(relation.target_id)
            elif relation.type == "HIDES_FROM":
                hides.append(relation.target_id)
            if relation.type in {"KNOWS_SECRET", "BELIEVES_FALSELY", "SUSPECTS", "HIDES_FROM"}:
                refs.append(relation.id)

        knownish = set(knows) | set(falsely_believes) | set(suspects)
        does_not_know = [
            node.id
            for node in sorted(self.nodes.values(), key=lambda item: item.id)
            if node.type == "Secret" and node.status == "CANON" and node.id not in knownish
        ]
        return KnowledgeBoundary(
            character_id=character_id,
            knows=knows,
            does_not_know=does_not_know,
            falsely_believes=falsely_believes,
            suspects=suspects,
            hides=hides,
            source_refs=refs,
        )

    def get_unresolved_foreshadowing(self, **filters: str) -> list[GraphNode]:
        items = []
        for node in sorted(self.nodes.values(), key=lambda item: item.id):
            if node.type != "Foreshadowing" or node.status != "CANON":
                continue
            if node.properties.get("status") == "paid_off":
                continue
            if any(node.properties.get(key) != value for key, value in filters.items()):
                continue
            items.append(node)
        return items

    def commit_candidate_fact(
        self, candidate: CandidateFact, *, reviewer: str, rationale: str
    ) -> EventLogEntry:
        if candidate.review.status not in {"accepted", "edited"}:
            raise GraphStoreError("invalid_status_transition", "Candidate is not accepted for canon")
        if candidate.status != "ACCEPTED_FOR_CANON":
            raise GraphStoreError("invalid_status_transition", "Candidate status is not ACCEPTED_FOR_CANON")
        patch = candidate.proposed_graph_patch
        if patch.operation == "none":
            return self._record_event(
                operation="commit_candidate_fact",
                target=candidate.id,
                source_ref=candidate.source_draft_id,
                reviewer=reviewer,
                rationale=rationale,
                payload={"candidate_id": candidate.id, "operation": "none"},
            )
        if patch.operation == "create_relation":
            if not candidate.object_id:
                raise GraphStoreError("missing_provenance", "Relation candidate requires object_id")
            relation_id = f"rel_{candidate.id}"
            now = utc_now()
            relation = GraphRelationship(
                id=relation_id,
                type=candidate.relation,
                status="CANON",
                created_at=now,
                updated_at=now,
                source_ref=candidate.source_draft_id,
                event_id=new_id("evt"),
                reviewer=reviewer,
                reviewed_at=now,
                rationale=rationale,
                source_id=candidate.subject_id,
                target_id=candidate.object_id,
                properties={**patch.properties, "candidate_fact_id": candidate.id},
            )
            if relation_id not in self.relationships:
                self.create_relation(relation, allow_canon=True)
            event = self._record_event(
                operation="commit_candidate_fact",
                target=relation_id,
                source_ref=candidate.source_draft_id,
                reviewer=reviewer,
                rationale=rationale,
                payload={"candidate": candidate.model_dump(), "relationship": relation.model_dump()},
                event_id=relation.event_id,
            )
            return event
        if patch.operation == "update_node":
            self.update_node(
                candidate.subject_id,
                patch.properties,
                reviewer=reviewer,
                rationale=rationale,
                source_ref=candidate.source_draft_id,
            )
        elif patch.operation == "update_relation":
            self.update_relation(
                patch.target,
                patch.properties,
                reviewer=reviewer,
                rationale=rationale,
                source_ref=candidate.source_draft_id,
            )
        elif patch.operation == "create_node":
            now = utc_now()
            node = GraphNode(
                id=candidate.subject_id,
                type=candidate.fact_type,
                status="CANON",
                created_at=now,
                updated_at=now,
                source_ref=candidate.source_draft_id,
                event_id=new_id("evt"),
                reviewer=reviewer,
                reviewed_at=now,
                rationale=rationale,
                properties=patch.properties,
            )
            self.create_node(node, allow_canon=True)
        return self._record_event(
            operation="commit_candidate_fact",
            target=patch.target,
            source_ref=candidate.source_draft_id,
            reviewer=reviewer,
            rationale=rationale,
            payload={"candidate": candidate.model_dump()},
        )

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
        return self.event_log.append(event)

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

