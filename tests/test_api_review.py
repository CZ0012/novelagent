from fastapi.testclient import TestClient

from apps.api.main import create_app
from storygraph.demo import ITEM_ID, LOCATION_ID, PROJECT_ID, SCENE_ID


def test_api_defer_review_action_blocks_later_accept():
    client = TestClient(create_app())
    fact_id = _create_candidate(client, "fact_api_defer")

    deferred = client.post(
        f"/projects/{PROJECT_ID}/facts/{fact_id}/defer",
        json={"reviewer": "author", "note": "Hold for later."},
    )

    assert deferred.status_code == 200
    assert deferred.json()["status"] == "DEFERRED"
    assert deferred.json()["review"]["status"] == "deferred"
    assert deferred.json()["review"]["note"] == "Hold for later."

    accepted = client.post(
        f"/projects/{PROJECT_ID}/facts/{fact_id}/accept",
        json={"reviewer": "author", "note": "Changed mind."},
    )
    assert accepted.status_code == 409


def test_api_edit_accept_review_action():
    client = TestClient(create_app())
    fact_id = _create_candidate(client, "fact_api_edit")

    edited = client.post(
        f"/projects/{PROJECT_ID}/facts/{fact_id}/edit-accept",
        json={
            "reviewer": "author",
            "note": "Accept with an edited relation property.",
            "patch_properties": {"review_note": "edited before canon commit"},
        },
    )

    assert edited.status_code == 200
    payload = edited.json()
    assert payload["status"] == "ACCEPTED_FOR_CANON"
    assert payload["review"]["status"] == "edited"
    assert payload["proposed_graph_patch"]["properties"]["review_note"] == "edited before canon commit"


def _create_candidate(client: TestClient, fact_id: str) -> str:
    marker = (
        f"[[fact:id={fact_id};fact_type=ItemState;subject={ITEM_ID};"
        f"relation=LOCATED_AT;object={LOCATION_ID};confidence=0.95]]"
    )
    draft_response = client.post(
        f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/draft",
        json={"text": f"Lin Jin finds a clue. {marker}", "summary": "Fact marker draft."},
    )
    assert draft_response.status_code == 200

    extract_response = client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/extract-state")
    assert extract_response.status_code == 200
    candidates = extract_response.json()["candidates"]
    assert len(candidates) == 1
    return candidates[0]["id"]

