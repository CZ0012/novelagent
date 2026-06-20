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

    def add_chapter(
        self,
        *,
        project_id: str,
        title: str,
        node_id: str | None = None,
        properties: dict | None = None,
        reviewer: str,
        rationale: str,
        source_ref: str,
    ) -> GraphNode:
        self._require_provenance(reviewer=reviewer, rationale=rationale, source_ref=source_ref)
        self.graph_store.get_node(project_id)
        node_properties = {"project_id": project_id, "title": title, **(properties or {})}
        chapter = self.graph_store.seed_canon_node(
            node_id=node_id or slug_id("chapter", title),
            node_type="Chapter",
            properties=node_properties,
            source_ref=source_ref,
            reviewer=reviewer,
            rationale=rationale,
        )
        self.graph_store.seed_canon_relation(
            relation_id=slug_id("rel", f"{project_id}_HAS_CHAPTER_{chapter.id}"),
            relation_type="HAS_CHAPTER",
            source_id=project_id,
            target_id=chapter.id,
            properties={"project_id": project_id},
            source_ref=source_ref,
            reviewer=reviewer,
            rationale=rationale,
        )
        return chapter

    def add_scene(
        self,
        *,
        project_id: str,
        chapter_id: str,
        title: str,
        node_id: str | None = None,
        properties: dict | None = None,
        previous_scene_id: str | None = None,
        reviewer: str,
        rationale: str,
        source_ref: str,
    ) -> GraphNode:
        self._require_provenance(reviewer=reviewer, rationale=rationale, source_ref=source_ref)
        self.graph_store.get_node(project_id)
        chapter = self.graph_store.get_node(chapter_id)
        if chapter.type != "Chapter" or chapter.properties.get("project_id") != project_id:
            raise ContractError("Chapter does not belong to the requested project.")
        node_properties = {
            "project_id": project_id,
            "chapter_id": chapter_id,
            "title": title,
            **(properties or {}),
        }
        scene = self.graph_store.seed_canon_node(
            node_id=node_id or slug_id("scene", title),
            node_type="Scene",
            properties=node_properties,
            source_ref=source_ref,
            reviewer=reviewer,
            rationale=rationale,
        )
        self.graph_store.seed_canon_relation(
            relation_id=slug_id("rel", f"{chapter_id}_HAS_SCENE_{scene.id}"),
            relation_type="HAS_SCENE",
            source_id=chapter_id,
            target_id=scene.id,
            properties={"project_id": project_id},
            source_ref=source_ref,
            reviewer=reviewer,
            rationale=rationale,
        )
        if previous_scene_id:
            self.graph_store.get_node(previous_scene_id)
            self.graph_store.seed_canon_relation(
                relation_id=slug_id("rel", f"{previous_scene_id}_NEXT_SCENE_{scene.id}"),
                relation_type="NEXT_SCENE",
                source_id=previous_scene_id,
                target_id=scene.id,
                properties={"project_id": project_id},
                source_ref=source_ref,
                reviewer=reviewer,
                rationale=rationale,
            )
        return scene

    def add_world_rule(
        self,
        *,
        project_id: str,
        domain: str,
        rule: str,
        node_id: str | None = None,
        properties: dict | None = None,
        reviewer: str,
        rationale: str,
        source_ref: str,
    ) -> GraphNode:
        self._require_provenance(reviewer=reviewer, rationale=rationale, source_ref=source_ref)
        self.graph_store.get_node(project_id)
        node_properties = {
            "project_id": project_id,
            "domain": domain,
            "rule": rule,
            **(properties or {}),
        }
        return self.graph_store.seed_canon_node(
            node_id=node_id or slug_id("worldrule", f"{domain}_{rule[:40]}"),
            node_type="WorldRule",
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
