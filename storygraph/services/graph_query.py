"""Canon graph query helpers for API and CLI surfaces."""

from __future__ import annotations

from typing import get_args

from storygraph.core.errors import ContractError
from storygraph.models.common import GraphStatus
from storygraph.models.graph import EDGE_LABELS, NODE_LABELS, GraphNode
from storygraph.stores.graph_base import GraphStore
from storygraph.stores.memory_graph import InMemoryGraphStore


class GraphQueryService:
    def __init__(self, graph_store: GraphStore) -> None:
        self.graph_store = graph_store

    def get_node(
        self,
        *,
        project_id: str,
        node_id: str,
        include_non_canon: bool = False,
    ) -> GraphNode:
        self.graph_store.get_node(project_id)
        return self.graph_store.get_node(node_id, include_non_canon=include_non_canon)

    def query_neighbors(
        self,
        *,
        project_id: str,
        source_id: str,
        hop_limit: int = 1,
        edge_labels: list[str] | None = None,
        node_labels: list[str] | None = None,
        statuses: list[GraphStatus] | None = None,
    ) -> dict:
        self.graph_store.get_node(project_id)
        self._validate_hop_limit(hop_limit)
        include_non_canon_source = bool(statuses and statuses != ["CANON"])
        source = self.graph_store.get_node(
            source_id,
            include_non_canon=include_non_canon_source,
        )
        self._validate_filters(
            edge_labels=edge_labels,
            node_labels=node_labels,
            statuses=statuses,
        )
        result = self.graph_store.query_neighbors(
            source_id,
            edge_labels=edge_labels,
            node_labels=node_labels,
            statuses=statuses,
            hop_limit=hop_limit,
        )
        nodes = [
            node
            for node in result["nodes"]
            if self._belongs_to_project(node.properties, project_id=project_id)
        ]
        relationships = [
            relationship
            for relationship in result["relationships"]
            if self._belongs_to_project(relationship.properties, project_id=project_id)
        ]
        return {
            "project_id": project_id,
            "source": source.model_dump(),
            "nodes": [node.model_dump() for node in nodes],
            "relationships": [
                relationship.model_dump()
                for relationship in relationships
            ],
            "filters": {
                "hop_limit": hop_limit,
                "edge_labels": edge_labels or [],
                "node_labels": node_labels or [],
                "statuses": statuses or ["CANON"],
            },
        }

    def list_projects(self) -> list[dict]:
        graph = self._snapshot()
        projects = [
            node
            for node in graph.nodes.values()
            if node.type == "Project" and node.status == "CANON"
        ]
        return [
            self.project_outline(project_id=project.id)
            for project in sorted(projects, key=lambda node: self._display_name(node).lower())
        ]

    def project_outline(self, *, project_id: str) -> dict:
        graph = self._snapshot()
        project = graph.get_node(project_id)
        chapters = [
            graph.nodes[relation.target_id]
            for relation in graph.relationships.values()
            if relation.type == "HAS_CHAPTER"
            and relation.status == "CANON"
            and relation.source_id == project_id
            and relation.target_id in graph.nodes
            and graph.nodes[relation.target_id].status == "CANON"
        ]
        chapter_items = [
            self._chapter_payload(graph, chapter, project_id=project_id)
            for chapter in sorted(chapters, key=self._chapter_sort_key)
        ]
        return {
            "id": project.id,
            "title": project.properties.get("title", project.id),
            "genre": project.properties.get("genre"),
            "language": project.properties.get("language"),
            "status": project.status,
            "properties": project.properties,
            "chapters": chapter_items,
        }

    def scene_node(self, *, project_id: str, scene_id: str) -> dict:
        self.graph_store.get_node(project_id)
        scene = self.graph_store.get_node(scene_id)
        if scene.type != "Scene" or scene.properties.get("project_id") != project_id:
            raise ContractError("Scene does not belong to the requested project.")
        return scene.model_dump()

    def project_graph_preview(self, *, project_id: str, max_relationships: int = 16) -> dict:
        graph = self._snapshot()
        outline = self.project_outline(project_id=project_id)
        relevant_ids = {project_id}
        for chapter in outline["chapters"]:
            relevant_ids.add(chapter["id"])
            for scene in chapter["scenes"]:
                relevant_ids.add(scene["id"])
                scene_node = graph.nodes.get(scene["id"])
                if scene_node:
                    relevant_ids.update(self._scene_references(scene_node.properties))

        for node in graph.nodes.values():
            if node.status != "CANON":
                continue
            if node.properties.get("project_id") == project_id:
                relevant_ids.add(node.id)

        relationships = []
        for relation in sorted(graph.relationships.values(), key=lambda item: item.id):
            if relation.status != "CANON":
                continue
            if relation.source_id in relevant_ids and relation.target_id in relevant_ids:
                relationships.append(relation)
                relevant_ids.add(relation.source_id)
                relevant_ids.add(relation.target_id)

        nodes = [
            graph.nodes[node_id]
            for node_id in sorted(relevant_ids)
            if node_id in graph.nodes and graph.nodes[node_id].status == "CANON"
        ]
        node_payloads = {
            node.id: {
                "id": node.id,
                "type": node.type,
                "label": self._display_name(node),
            }
            for node in nodes
        }
        timeline = []
        for chapter in outline["chapters"]:
            for scene in chapter["scenes"]:
                timeline.append(
                    {
                        "id": scene["id"],
                        "label": scene["title"],
                        "state": scene.get("status") or "planned",
                        "chapter_id": chapter["id"],
                        "scene_index": scene.get("scene_index"),
                    }
                )
        return {
            "project_id": project_id,
            "nodes": list(node_payloads.values()),
            "relationships": [
                {
                    "id": relation.id,
                    "source_id": relation.source_id,
                    "source_label": node_payloads.get(relation.source_id, {}).get(
                        "label", relation.source_id
                    ),
                    "type": relation.type,
                    "target_id": relation.target_id,
                    "target_label": node_payloads.get(relation.target_id, {}).get(
                        "label", relation.target_id
                    ),
                }
                for relation in relationships[:max_relationships]
            ],
            "timeline": timeline,
            "truncated": len(relationships) > max_relationships,
        }

    @staticmethod
    def _validate_hop_limit(hop_limit: int) -> None:
        if hop_limit < 1 or hop_limit > 2:
            raise ContractError("hop_limit must be between 1 and 2 for the MVP")

    @staticmethod
    def _belongs_to_project(properties: dict, *, project_id: str) -> bool:
        return properties.get("project_id", project_id) == project_id

    @staticmethod
    def _validate_filters(
        *,
        edge_labels: list[str] | None,
        node_labels: list[str] | None,
        statuses: list[str] | None,
    ) -> None:
        unsupported_edges = sorted(set(edge_labels or []) - EDGE_LABELS)
        unsupported_nodes = sorted(set(node_labels or []) - NODE_LABELS)
        unsupported_statuses = sorted(set(statuses or []) - set(get_args(GraphStatus)))
        if unsupported_edges:
            raise ContractError(f"Unsupported edge labels: {unsupported_edges}")
        if unsupported_nodes:
            raise ContractError(f"Unsupported node labels: {unsupported_nodes}")
        if unsupported_statuses:
            raise ContractError(f"Unsupported statuses: {unsupported_statuses}")

    def _snapshot(self) -> InMemoryGraphStore:
        if isinstance(self.graph_store, InMemoryGraphStore):
            return self.graph_store
        snapshot = getattr(self.graph_store, "_snapshot", None)
        if callable(snapshot):
            return snapshot()
        raise ContractError("Graph backend does not expose a project structure snapshot.")

    @classmethod
    def _chapter_payload(
        cls,
        graph: InMemoryGraphStore,
        chapter: GraphNode,
        *,
        project_id: str,
    ) -> dict:
        scenes = [
            graph.nodes[relation.target_id]
            for relation in graph.relationships.values()
            if relation.type == "HAS_SCENE"
            and relation.status == "CANON"
            and relation.source_id == chapter.id
            and relation.target_id in graph.nodes
            and graph.nodes[relation.target_id].status == "CANON"
            and cls._belongs_to_project(graph.nodes[relation.target_id].properties, project_id=project_id)
        ]
        return {
            "id": chapter.id,
            "title": chapter.properties.get("title", chapter.id),
            "volume_index": chapter.properties.get("volume_index"),
            "chapter_index": chapter.properties.get("chapter_index"),
            "status": chapter.properties.get("status", "planned"),
            "summary": chapter.properties.get("summary"),
            "purpose": chapter.properties.get("purpose"),
            "properties": chapter.properties,
            "scenes": [
                cls._scene_payload(scene)
                for scene in sorted(scenes, key=cls._scene_sort_key)
            ],
        }

    @staticmethod
    def _scene_payload(scene: GraphNode) -> dict:
        return {
            "id": scene.id,
            "title": scene.properties.get("title", scene.id),
            "scene_index": scene.properties.get("scene_index"),
            "status": scene.properties.get("status", "planned"),
            "pov_character_id": scene.properties.get("pov_character_id"),
            "location_id": scene.properties.get("location_id"),
            "timeline_position": scene.properties.get("timeline_position"),
            "goal": scene.properties.get("goal"),
            "conflict": scene.properties.get("conflict"),
            "properties": scene.properties,
        }

    @staticmethod
    def _display_name(node: GraphNode) -> str:
        for key in ("title", "name", "rule", "content", "clue_text"):
            value = node.properties.get(key)
            if isinstance(value, str) and value:
                return value
        return node.id

    @staticmethod
    def _chapter_sort_key(node: GraphNode) -> tuple[int, int, str]:
        return (
            int(node.properties.get("volume_index") or 0),
            int(node.properties.get("chapter_index") or 0),
            node.id,
        )

    @staticmethod
    def _scene_sort_key(node: GraphNode) -> tuple[int, str]:
        return (int(node.properties.get("scene_index") or 0), node.id)

    @staticmethod
    def _scene_references(props: dict) -> set[str]:
        refs = {
            value
            for value in [
                props.get("chapter_id"),
                props.get("pov_character_id"),
                props.get("location_id"),
                props.get("previous_scene_id"),
            ]
            if isinstance(value, str) and value
        }
        required = props.get("required_characters", [])
        if isinstance(required, list):
            refs.update(item for item in required if isinstance(item, str) and item)
        return refs
