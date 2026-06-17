"""Canon graph query helpers for API and CLI surfaces."""

from __future__ import annotations

from typing import get_args

from storygraph.core.errors import ContractError
from storygraph.models.common import GraphStatus
from storygraph.models.graph import EDGE_LABELS, NODE_LABELS, GraphNode
from storygraph.stores.graph_base import GraphStore


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
