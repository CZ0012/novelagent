"""Backend-neutral Graph Store interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from storygraph.models.candidate import CandidateFact
from storygraph.models.context import KnowledgeBoundary
from storygraph.models.graph import EventLogEntry, GraphNode, GraphRelationship


class GraphStore(ABC):
    @abstractmethod
    def get_node(self, node_id: str, *, include_non_canon: bool = False) -> GraphNode:
        raise NotImplementedError

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
    def create_relation(
        self, relation: GraphRelationship, *, allow_canon: bool = False
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

