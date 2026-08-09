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
        self._require_project(project_id)
        node_properties = {**(properties or {}), "project_id": project_id, "name": name}
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
        self._require_project(project_id)
        node_properties = {**(properties or {}), "project_id": project_id, "name": name}
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
        self._require_project(project_id)
        node_properties = {**(properties or {}), "project_id": project_id, "title": title}
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
        self._require_project(project_id)
        self._require_owned_node(project_id, chapter_id, expected_type="Chapter")
        raw_properties = dict(properties or {})
        property_previous_scene_id = raw_properties.get("previous_scene_id")
        if (
            previous_scene_id is not None
            and property_previous_scene_id is not None
            and property_previous_scene_id != previous_scene_id
        ):
            raise ContractError("Scene previous_scene_id values do not match.")
        effective_previous_scene_id = previous_scene_id or property_previous_scene_id
        node_properties = {
            **raw_properties,
            "project_id": project_id,
            "chapter_id": chapter_id,
            "title": title,
            "previous_scene_id": effective_previous_scene_id,
        }
        self.validate_scene_references(project_id=project_id, properties=node_properties)
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
        if effective_previous_scene_id:
            self.graph_store.seed_canon_relation(
                relation_id=slug_id(
                    "rel", f"{effective_previous_scene_id}_NEXT_SCENE_{scene.id}"
                ),
                relation_type="NEXT_SCENE",
                source_id=effective_previous_scene_id,
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
        self._require_project(project_id)
        node_properties = {
            **(properties or {}),
            "project_id": project_id,
            "domain": domain,
            "rule": rule,
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
        self._require_project(project_id)
        self._require_owned_node(project_id, source_id)
        self._require_owned_node(project_id, target_id)
        relation_properties = {**(properties or {}), "project_id": project_id}
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

    def validate_scene_references(self, *, project_id: str, properties: dict) -> None:
        reference_types = {
            "pov_character_id": "Character",
            "location_id": "Location",
            "previous_scene_id": "Scene",
        }
        for field_name, expected_type in reference_types.items():
            node_id = properties.get(field_name)
            if node_id:
                self._require_owned_node(
                    project_id,
                    str(node_id),
                    expected_type=expected_type,
                )
        required_characters = properties.get("required_characters", [])
        if not isinstance(required_characters, list):
            raise ContractError("Scene required_characters must be a list.")
        for character_id in required_characters:
            if not isinstance(character_id, str) or not character_id:
                raise ContractError("Scene required_characters must contain stable IDs.")
            self._require_owned_node(
                project_id,
                character_id,
                expected_type="Character",
            )

    def _require_project(self, project_id: str) -> GraphNode:
        project = self.graph_store.get_node(project_id)
        if project.type != "Project":
            raise ContractError(f"Node {project_id} is not a Project.")
        return project

    def _require_owned_node(
        self,
        project_id: str,
        node_id: str,
        *,
        expected_type: str | None = None,
    ) -> GraphNode:
        node = self.graph_store.get_node(node_id)
        belongs = (
            node.id == project_id
            if node.type == "Project"
            else node.properties.get("project_id") == project_id
        )
        if not belongs:
            raise ContractError("Referenced node does not belong to the requested project.")
        if expected_type is not None and node.type != expected_type:
            raise ContractError(f"Referenced node must be a {expected_type}.")
        return node

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
