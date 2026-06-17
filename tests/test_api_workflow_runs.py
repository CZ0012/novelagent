from fastapi.testclient import TestClient

from apps.api.main import create_app
from storygraph.demo import PROJECT_ID, SCENE_ID


def test_api_scene_generation_run_is_checkpointed_and_queryable():
    client = TestClient(create_app())

    response = client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/runs/scene-generation")

    assert response.status_code == 200
    payload = response.json()
    run = payload["workflow_run"]
    assert run["status"] == "completed"
    assert run["current_step"] == "END"

    fetched = client.get(f"/runs/{run['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == run["id"]

    listed = client.get(f"/projects/{PROJECT_ID}/runs", params={"status": "completed"})
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["runs"]] == [run["id"]]


def test_api_missing_workflow_run_returns_404():
    client = TestClient(create_app())

    response = client.get("/runs/missing")

    assert response.status_code == 404
