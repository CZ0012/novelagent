"""Human-authored canon seed operations.

These helpers are for explicit author/editor actions, not automated extraction.
Generated drafts still produce CandidateFact records and must go through review.
"""

from __future__ import annotations

from storygraph.core.errors import ContractError
from storygraph.core.ids import slug_id
from storygraph.models.graph import GraphNode, GraphRelationship
from storygraph.stores.graph_base import GraphStore


class AuthorCanonSeedService:
    def __init__(self, graph_store: GraphStore) -> None:
        self.graph_store = graph_store

    def add_character(
        self,
        *,
        project_id: str,
        name: str,
        node_id: str | None = None,
        properties: dict | None = None,
        reviewer: str,
        rationale: str,
        source_ref: str,
    ) -> GraphNode:
        self._require_provenance(reviewer=reviewer, rationale=rationale, source_ref=source_ref)
        self.graph_store.get_node(project_id)
        node_properties = {"project_id": project_id, "name": name, **(properties or {})}
        return self.graph_store.seed_canon_node(
            node_id=node_id or slug_id("character", name),
            node_type="Character",
            properties=node_properties,
            source_ref=source_ref,
            reviewer=reviewer,
            rationale=rationale,
        )

    def add_location(
        self,
        *,
        project_id: str,
        name: str,
        node_id: str | None = None,
        properties: dict | None = None,
        reviewer: str,
        rationale: str,
        source_ref: str,
    ) -> GraphNode:
        self._require_provenance(reviewer=reviewer, rationale=rationale, source_ref=source_ref)
        self.graph_store.get_node(project_id)
        node_properties = {"project_id": project_id, "name": name, **(properties or {})}
        return self.graph_store.seed_canon_node(
            node_id=node_id or slug_id("location", name),
            node_type="Location",
            properties=node_properties,
            source_ref=source_ref,
            reviewer=reviewer,
            rationale=rationale,
        )

    def add_relation(
        self,
        *,
        project_id: str,
        relation_type: str,
        source_id: str,
        target_id: str,
        relation_id: str | None = None,
        properties: dict | None = None,
        reviewer: str,
        rationale: str,
        source_ref: str,
    ) -> GraphRelationship:
        self._require_provenance(reviewer=reviewer, rationale=rationale, source_ref=source_ref)
        self.graph_store.get_node(project_id)
        self.graph_store.get_node(source_id)
        self.graph_store.get_node(target_id)
        relation_properties = {"project_id": project_id, **(properties or {})}
        return self.graph_store.seed_canon_relation(
            relation_id=relation_id or slug_id("rel", f"{source_id}_{relation_type}_{target_id}"),
            relation_type=relation_type,
            source_id=source_id,
            target_id=target_id,
            properties=relation_properties,
            source_ref=source_ref,
            reviewer=reviewer,
            rationale=rationale,
        )

    @staticmethod
    def _require_provenance(*, reviewer: str, rationale: str, source_ref: str) -> None:
        missing = [
            field
            for field, value in {
                "reviewer": reviewer,
                "rationale": rationale,
                "source_ref": source_ref,
            }.items()
            if not value.strip()
        ]
        if missing:
            raise ContractError(f"Author canon seed missing provenance: {', '.join(missing)}")
