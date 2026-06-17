"""Graph Store contract models."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from storygraph.models.common import ContractModel, GraphStatus, JsonDict


NODE_LABELS = {
    "Project",
    "Character",
    "Organization",
    "Location",
    "Item",
    "Event",
    "Scene",
    "Chapter",
    "Secret",
    "Foreshadowing",
    "WorldRule",
    "StyleProfile",
}

EDGE_LABELS = {
    "KNOWS",
    "LOVES",
    "HATES",
    "LOYAL_TO",
    "BETRAYED",
    "FAMILY_OF",
    "MENTOR_OF",
    "RIVAL_OF",
    "KNOWS_SECRET",
    "BELIEVES_FALSELY",
    "SUSPECTS",
    "HIDES_FROM",
    "LOCATED_AT",
    "CONTROLS",
    "OWNED_BY",
    "PART_OF",
    "CAUSES",
    "CONSEQUENCE_OF",
    "PARTICIPATED_IN",
    "OCCURRED_AT",
    "OCCURRED_IN_SCENE",
    "SEEDED_IN",
    "POINTS_TO",
    "PAID_OFF_IN",
    "HAS_CHAPTER",
    "HAS_SCENE",
    "NEXT_SCENE",
}


class GraphMetadata(ContractModel):
    id: str
    type: str
    status: GraphStatus = "DRAFT_FACT"
    created_at: str
    updated_at: str
    source_ref: str
    event_id: str | None = None
    reviewer: str | None = None
    reviewed_at: str | None = None
    rationale: str | None = None


class GraphNode(GraphMetadata):
    properties: JsonDict = Field(default_factory=dict)


class GraphRelationship(GraphMetadata):
    source_id: str
    target_id: str
    properties: JsonDict = Field(default_factory=dict)


class EventLogEntry(ContractModel):
    event_id: str
    operation: Literal[
        "create_node",
        "update_node",
        "create_relation",
        "update_relation",
        "commit_candidate_fact",
    ]
    target: str
    source_ref: str
    reviewer: str
    rationale: str
    created_at: str
    payload: JsonDict = Field(default_factory=dict)

