"""Backend-neutral Graph Store interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from storygraph.core.errors import ContractError, GraphStoreError
from storygraph.models.candidate import CandidateFact
from storygraph.models.context import KnowledgeBoundary
from storygraph.models.graph import EventLogEntry, GraphNode, GraphRelationship
from storygraph.models.project import DEFAULT_OUTPUT_LANGUAGE, validate_output_language


class GraphStore(ABC):
    @abstractmethod
    def get_node(self, node_id: str, *, include_non_canon: bool = False) -> GraphNode:
        raise NotImplementedError

    @abstractmethod
    def get_relationship(
        self,
        relation_id: str,
        *,
        include_non_canon: bool = False,
    ) -> GraphRelationship:
        raise NotImplementedError

    def validate_candidate_scope(
        self,
        candidate: CandidateFact,
        *,
        expected_project_id: str | None = None,
    ) -> CandidateFact:
        """Validate and normalize project ownership before a candidate can reach canon."""
        project_id = expected_project_id or candidate.project_id
        if candidate.project_id != project_id:
            self._raise_candidate_scope_error(candidate, "belongs to another project")

        project = self._candidate_node(candidate, project_id, role="project")
        if project.type != "Project":
            self._raise_candidate_scope_error(candidate, f"project does not exist: {project_id}")
        source_scene = self._require_candidate_node_project(
            candidate,
            candidate.source_scene_id,
            project_id=project_id,
            role="source scene",
        )
        if source_scene.type != "Scene":
            self._raise_candidate_scope_error(
                candidate,
                f"source_scene_id is not a Scene: {candidate.source_scene_id}",
            )

        patch = candidate.proposed_graph_patch
        if patch.source_ref != candidate.source_draft_id:
            self._raise_candidate_scope_error(
                candidate,
                "graph patch source_ref does not match source_draft_id",
            )
        properties = dict(patch.properties)
        supplied_project_id = properties.get("project_id")
        if supplied_project_id is not None and supplied_project_id != project_id:
            self._raise_candidate_scope_error(
                candidate,
                "graph patch properties belong to another project",
            )

        if patch.operation == "create_node":
            self._validate_create_node_scope(candidate)
            properties["project_id"] = project_id
        elif patch.operation == "update_node":
            subject = self._require_candidate_node_project(
                candidate,
                candidate.subject_id,
                project_id=project_id,
                role="subject",
            )
            if subject.type == "Project":
                self._raise_candidate_scope_error(
                    candidate,
                    "fact review cannot update Project configuration",
                )
            if subject.type == "Scene":
                self._validate_scene_patch_references(
                    candidate,
                    properties=properties,
                    project_id=project_id,
                )
            self._validate_subject_patch_target(candidate)
        elif patch.operation == "create_relation":
            self._validate_create_relation_scope(candidate, project_id=project_id)
            properties["project_id"] = project_id
        elif patch.operation == "update_relation":
            self._validate_update_relation_scope(candidate, project_id=project_id)
        elif patch.operation == "none":
            self._require_candidate_node_project(
                candidate,
                candidate.subject_id,
                project_id=project_id,
                role="subject",
            )
            self._validate_subject_patch_target(candidate)

        if properties == patch.properties:
            return candidate
        return candidate.model_copy(
            update={
                "proposed_graph_patch": patch.model_copy(
                    update={"properties": properties}
                )
            }
        )

    def _validate_create_node_scope(self, candidate: CandidateFact) -> None:
        patch = candidate.proposed_graph_patch
        if patch.target != candidate.subject_id:
            self._raise_candidate_scope_error(
                candidate,
                "create_node target does not match subject",
            )
        node_type = patch.properties.get("node_type") or patch.properties.get("type")
        if node_type in {"Project", "Chapter", "Scene"}:
            self._raise_candidate_scope_error(
                candidate,
                f"fact review cannot create a {node_type} node",
            )
        try:
            self.get_node(candidate.subject_id, include_non_canon=True)
        except GraphStoreError as exc:
            if exc.category == "not_found":
                return
            raise
        self._raise_candidate_scope_error(
            candidate,
            f"create_node subject already exists: {candidate.subject_id}",
        )

    def _validate_create_relation_scope(
        self,
        candidate: CandidateFact,
        *,
        project_id: str,
    ) -> None:
        if not candidate.object_id:
            self._raise_candidate_scope_error(candidate, "create_relation requires object_id")
        expected_target = self._candidate_subject_target(candidate)
        if candidate.proposed_graph_patch.target != expected_target:
            self._raise_candidate_scope_error(
                candidate,
                "create_relation target does not match its subject, relation, and object",
            )
        self._require_candidate_node_project(
            candidate,
            candidate.subject_id,
            project_id=project_id,
            role="subject",
        )
        self._require_candidate_node_project(
            candidate,
            candidate.object_id,
            project_id=project_id,
            role="object",
        )

        relation_id = f"rel_{candidate.id}"
        try:
            relation = self.get_relationship(relation_id, include_non_canon=True)
        except GraphStoreError as exc:
            if exc.category == "not_found":
                return
            raise
        self._raise_candidate_scope_error(
            candidate,
            f"create_relation relationship id already exists: {relation.id}",
        )

    def _validate_update_relation_scope(
        self,
        candidate: CandidateFact,
        *,
        project_id: str,
    ) -> None:
        self._require_candidate_node_project(
            candidate,
            candidate.subject_id,
            project_id=project_id,
            role="subject",
        )
        relation = self._candidate_relationship(
            candidate,
            candidate.proposed_graph_patch.target,
        )
        if candidate.subject_id != relation.source_id:
            self._raise_candidate_scope_error(
                candidate,
                "update_relation subject does not match relationship source endpoint",
            )
        if candidate.object_id != relation.target_id:
            self._raise_candidate_scope_error(
                candidate,
                "update_relation object does not match relationship target endpoint",
            )
        if candidate.relation != relation.type:
            self._raise_candidate_scope_error(
                candidate,
                "update_relation type does not match relationship type",
            )
        self._require_candidate_relationship_project(
            candidate,
            relation,
            project_id=project_id,
        )
        self._require_candidate_node_project(
            candidate,
            relation.source_id,
            project_id=project_id,
            role="relationship source",
        )
        self._require_candidate_node_project(
            candidate,
            relation.target_id,
            project_id=project_id,
            role="relationship target",
        )

    def _validate_scene_patch_references(
        self,
        candidate: CandidateFact,
        *,
        properties: dict,
        project_id: str,
    ) -> None:
        singular_refs = {
            "chapter_id": "Chapter",
            "pov_character_id": "Character",
            "location_id": "Location",
            "previous_scene_id": "Scene",
        }
        for field_name, expected_type in singular_refs.items():
            value = properties.get(field_name)
            if value is None:
                continue
            if not isinstance(value, str) or not value:
                self._raise_candidate_scope_error(
                    candidate,
                    f"Scene {field_name} must be a stable node id",
                )
            node = self._require_candidate_node_project(
                candidate,
                value,
                project_id=project_id,
                role=f"Scene {field_name}",
            )
            if node.type != expected_type:
                self._raise_candidate_scope_error(
                    candidate,
                    f"Scene {field_name} must reference a {expected_type}",
                )
        required_characters = properties.get("required_characters")
        if required_characters is None:
            return
        if not isinstance(required_characters, list) or not all(
            isinstance(item, str) and item for item in required_characters
        ):
            self._raise_candidate_scope_error(
                candidate,
                "Scene required_characters must contain stable Character ids",
            )
        for character_id in required_characters:
            character = self._require_candidate_node_project(
                candidate,
                character_id,
                project_id=project_id,
                role="Scene required character",
            )
            if character.type != "Character":
                self._raise_candidate_scope_error(
                    candidate,
                    "Scene required_characters must reference Character nodes",
                )

    def _validate_subject_patch_target(self, candidate: CandidateFact) -> None:
        target = candidate.proposed_graph_patch.target
        allowed_targets = {candidate.subject_id, self._candidate_subject_target(candidate)}
        if target not in allowed_targets:
            self._raise_candidate_scope_error(
                candidate,
                "graph patch target does not match subject",
            )

    @staticmethod
    def _candidate_subject_target(candidate: CandidateFact) -> str:
        if candidate.object_id:
            return f"{candidate.subject_id} -> {candidate.relation} -> {candidate.object_id}"
        return candidate.subject_id

    def _candidate_node(
        self,
        candidate: CandidateFact,
        node_id: str,
        *,
        role: str,
    ) -> GraphNode:
        try:
            return self.get_node(node_id)
        except GraphStoreError as exc:
            if exc.category != "not_found":
                raise
            self._raise_candidate_scope_error(
                candidate,
                f"{role} node does not exist in canon: {node_id}",
            )

    def _candidate_relationship(
        self,
        candidate: CandidateFact,
        relation_id: str,
    ) -> GraphRelationship:
        try:
            return self.get_relationship(relation_id)
        except GraphStoreError as exc:
            if exc.category != "not_found":
                raise
            self._raise_candidate_scope_error(
                candidate,
                f"relationship does not exist in canon: {relation_id}",
            )

    def _require_candidate_node_project(
        self,
        candidate: CandidateFact,
        node_id: str,
        *,
        project_id: str,
        role: str,
    ) -> GraphNode:
        node = self._candidate_node(candidate, node_id, role=role)
        belongs = (
            node.id == project_id
            if node.type == "Project"
            else node.properties.get("project_id") == project_id
        )
        if not belongs:
            self._raise_candidate_scope_error(
                candidate,
                f"{role} node belongs to another project or has no project ownership: {node_id}",
            )
        return node

    def _require_candidate_relationship_project(
        self,
        candidate: CandidateFact,
        relation: GraphRelationship,
        *,
        project_id: str,
    ) -> None:
        if relation.properties.get("project_id") != project_id:
            self._raise_candidate_scope_error(
                candidate,
                "relationship belongs to another project or has no project ownership: "
                f"{relation.id}",
            )

    @staticmethod
    def _raise_candidate_scope_error(candidate: CandidateFact, message: str) -> None:
        raise GraphStoreError(
            "conflict_detected",
            f"CandidateFact {candidate.id} project scope violation: {message}.",
        )

    @staticmethod
    def _validate_project_language_properties(node_type: str, properties: dict) -> None:
        if node_type != "Project" or "language" not in properties:
            return
        try:
            validate_output_language(properties["language"])
        except (ContractError, TypeError) as exc:
            raise GraphStoreError(
                "conflict_detected",
                "Project language must be one of: zh-CN, en-US.",
            ) from exc

    @staticmethod
    def _effective_project_language(properties: dict) -> object:
        return properties.get("language", DEFAULT_OUTPUT_LANGUAGE)

    @abstractmethod
    def create_node(self, node: GraphNode, *, allow_canon: bool = False) -> GraphNode:
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
    def update_project_language(
        self,
        project_id: str,
        *,
        expected_language: str,
        language: str,
        properties: dict,
        reviewer: str,
        rationale: str,
        source_ref: str,
    ) -> GraphNode:
        """Atomically compare and update the authoritative Project language."""

        raise NotImplementedError

    @abstractmethod
    def create_relation(
        self, relation: GraphRelationship, *, allow_canon: bool = False
    ) -> GraphRelationship:
        raise NotImplementedError

    @abstractmethod
    def seed_canon_node(
        self,
        *,
        node_id: str,
        node_type: str,
        properties: dict,
        source_ref: str,
        reviewer: str,
        rationale: str,
    ) -> GraphNode:
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
    def query_neighbors(
        self,
        source_id: str,
        *,
        edge_labels: Iterable[str] | None = None,
        node_labels: Iterable[str] | None = None,
        statuses: Iterable[str] | None = None,
        hop_limit: int,
    ) -> dict[str, list]:
        raise NotImplementedError

    @abstractmethod
    def query_scene_context(self, scene_id: str) -> dict:
        raise NotImplementedError

    @abstractmethod
    def get_character_knowledge(
        self, character_id: str, *, scene_id: str | None = None, timeline_position: str | None = None
    ) -> KnowledgeBoundary:
        raise NotImplementedError

    @abstractmethod
    def get_unresolved_foreshadowing(self, **filters: str) -> list[GraphNode]:
        raise NotImplementedError

    @abstractmethod
    def commit_candidate_fact(
        self, candidate: CandidateFact, *, reviewer: str, rationale: str
    ) -> EventLogEntry:
        raise NotImplementedError
