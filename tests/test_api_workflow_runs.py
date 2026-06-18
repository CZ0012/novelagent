from fastapi.testclient import TestClient

from apps.api.main import create_app
from storygraph.core.config import StoryGraphSettings
from storygraph.demo import PROJECT_ID, SCENE_ID


def test_api_scene_generation_run_is_checkpointed_and_queryable():
    client = TestClient(create_app())

    response = client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/runs/scene-generation")

    assert response.status_code == 200
    payload = response.json()
    run = payload["workflow_run"]
    assert run["contract_version"] == "workflow_run_v1"
    assert run["status"] == "completed"
    assert run["current_step"] == "END"
    assert run["review_payload"]["contract_version"] == "review_payload_v1"

    fetched = client.get(f"/runs/{run['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == run["id"]

    events = client.get(f"/runs/{run['id']}/events")
    assert events.status_code == 200
    assert [event["step"] for event in events.json()["events"]] == [
        "build_context",
        "write_draft",
        "check_continuity",
        "extract_state",
        "human_review",
    ]

    listed = client.get(f"/projects/{PROJECT_ID}/runs", params={"status": "completed"})
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["runs"]] == [run["id"]]


def test_api_workflow_runs_persist_across_app_instances(tmp_path):
    settings = StoryGraphSettings(tmp_path)
    first_client = TestClient(create_app(settings))
    run_response = first_client.post(
        f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/runs/scene-generation"
    )
    run_id = run_response.json()["workflow_run"]["id"]

    second_client = TestClient(create_app(settings))
    fetched = second_client.get(f"/runs/{run_id}")

    assert fetched.status_code == 200
    assert fetched.json()["id"] == run_id


def test_api_missing_workflow_run_returns_404():
    client = TestClient(create_app())

    response = client.get("/runs/missing")

    assert response.status_code == 404
