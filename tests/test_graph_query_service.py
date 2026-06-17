import pytest

from storygraph.core.errors import ContractError
from storygraph.core.time import utc_now
from storygraph.demo import PROJECT_ID, POV_CHARACTER_ID, build_fantasy_demo_graph
from storygraph.models.graph import GraphNode, GraphRelationship
from storygraph.services.graph_query import GraphQueryService


def test_graph_query_defaults_to_canon_and_can_explicitly_include_draft_facts():
    graph = build_fantasy_demo_graph()
    now = utc_now()
    graph.create_node(
        GraphNode(
            id="character_draft_neighbor",
            type="Character",
            status="DRAFT_FACT",
            created_at=now,
            updated_at=now,
            source_ref="test",
            properties={"project_id": PROJECT_ID, "name": "Draft Neighbor"},
        )
    )
    graph.create_relation(
        GraphRelationship(
            id="rel_linj_knows_draft_neighbor",
            type="KNOWS",
            status="DRAFT_FACT",
            created_at=now,
            updated_at=now,
            source_ref="test",
            source_id=POV_CHARACTER_ID,
            target_id="character_draft_neighbor",
            properties={"project_id": PROJECT_ID},
        )
    )
    before_events = graph.event_log.list()
    service = GraphQueryService(graph)

    canon = service.query_neighbors(project_id=PROJECT_ID, source_id=POV_CHARACTER_ID)
    draft = service.query_neighbors(
        project_id=PROJECT_ID,
        source_id=POV_CHARACTER_ID,
        statuses=["DRAFT_FACT"],
    )

    assert "character_draft_neighbor" not in [node["id"] for node in canon["nodes"]]
    assert [node["id"] for node in draft["nodes"]] == ["character_draft_neighbor"]
    assert [relation["id"] for relation in draft["relationships"]] == [
        "rel_linj_knows_draft_neighbor"
    ]
    assert graph.event_log.list() == before_events


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"edge_labels": ["FRIENDS"]}, "Unsupported edge labels"),
        ({"node_labels": ["Monster"]}, "Unsupported node labels"),
        ({"statuses": ["MAYBE"]}, "Unsupported statuses"),
        ({"hop_limit": 0}, "hop_limit"),
        ({"hop_limit": 3}, "hop_limit"),
    ],
)
def test_graph_query_rejects_invalid_filters(kwargs, message):
    service = GraphQueryService(build_fantasy_demo_graph())

    with pytest.raises(ContractError, match=message):
        service.query_neighbors(
            project_id=PROJECT_ID,
            source_id=POV_CHARACTER_ID,
            **kwargs,
        )

