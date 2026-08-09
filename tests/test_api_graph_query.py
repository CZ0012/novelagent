from fastapi.testclient import TestClient

from apps.api.main import create_app
from storygraph.demo import PROJECT_ID, POV_CHARACTER_ID


def test_api_get_project_and_query_character_neighbors():
    client = TestClient(create_app())

    project = client.get(f"/projects/{PROJECT_ID}")
    query = client.get(
        f"/projects/{PROJECT_ID}/graph/query",
        params={"source_id": POV_CHARACTER_ID, "edge_labels": "KNOWS", "hop_limit": 1},
    )

    assert project.status_code == 200
    assert project.json()["id"] == PROJECT_ID
    assert query.status_code == 200
    payload = query.json()
    assert payload["source"]["id"] == POV_CHARACTER_ID
    assert payload["filters"]["statuses"] == ["CANON"]
    assert [node["id"] for node in payload["nodes"]] == ["character_helianya"]
    assert [relation["id"] for relation in payload["relationships"]] == [
        "rel_linj_knows_helianya"
    ]


def test_api_graph_query_rejects_invalid_filters():
    client = TestClient(create_app())

    bad_label = client.get(
        f"/projects/{PROJECT_ID}/graph/query",
        params={"source_id": POV_CHARACTER_ID, "edge_labels": "FRIENDS"},
    )
    bad_hop = client.get(
        f"/projects/{PROJECT_ID}/graph/query",
        params={"source_id": POV_CHARACTER_ID, "hop_limit": 0},
    )

    assert bad_label.status_code == 409
    assert bad_label.json()["detail"]["category"] == "contract_error"
    assert "Unsupported edge labels" in bad_label.json()["detail"]["message"]
    assert bad_hop.status_code == 409
    assert bad_hop.json()["detail"]["category"] == "contract_error"
    assert "hop_limit" in bad_hop.json()["detail"]["message"]


def test_api_graph_query_is_read_only_for_pending_facts():
    client = TestClient(create_app())

    query = client.get(
        f"/projects/{PROJECT_ID}/graph/query",
        params={"source_id": POV_CHARACTER_ID},
    )
    pending = client.get(f"/projects/{PROJECT_ID}/facts/pending")

    assert query.status_code == 200
    assert pending.status_code == 200
    assert pending.json()["facts"] == []


def test_api_graph_query_rejects_cross_project_source_without_leaking_properties():
    client = TestClient(create_app())
    project_id = client.post(
        "/projects",
        json={"title": "Private Graph Project", "language": "zh-CN"},
    ).json()["project_id"]
    chapter_id = "chapter_private_graph_scope"
    chapter = client.post(
        f"/projects/{project_id}/chapters",
        json={
            "id": chapter_id,
            "title": "Private Chapter",
            "chapter_index": 1,
            "summary": "B_PRIVATE_GRAPH_SENTINEL",
            "reviewer": "author",
            "rationale": "Synthetic graph-scope regression fixture.",
            "source_ref": "test:graph_scope",
        },
    )
    assert chapter.status_code == 200

    response = client.get(
        f"/projects/{PROJECT_ID}/graph/query",
        params={"source_id": chapter_id},
    )

    assert response.status_code == 409
    assert "B_PRIVATE_GRAPH_SENTINEL" not in response.text
