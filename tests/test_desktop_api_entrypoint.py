from fastapi.testclient import TestClient

from apps.api.main import create_app
from apps.api import desktop
from storygraph.core.config import StoryGraphSettings
from storygraph.demo import PROJECT_ID


def test_desktop_settings_uses_local_appdata_workspace_without_seeding_canon(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("STORYGRAPH_HOME", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    settings = desktop.desktop_settings()

    assert settings.workspace_dir == tmp_path / "StoryGraph Agent" / "workspace"
    assert settings.workspace_dir.exists()
    assert not settings.graph_path.exists()
    assert settings.graph_backend == "json"


def test_desktop_json_runtime_seeds_demo_only_by_explicit_full_permission_request(tmp_path):
    settings = _json_settings(tmp_path)
    client = TestClient(create_app(settings))

    missing = client.get(f"/projects/{PROJECT_ID}")
    assert missing.status_code == 404
    assert not settings.graph_path.exists()

    seeded = client.post("/demo/seed")

    assert seeded.status_code == 200
    payload = seeded.json()
    assert payload["project_id"] == PROJECT_ID
    assert payload["nodes_created"] == 11
    assert payload["relationships_created"] == 5
    assert settings.graph_path.exists()

    project = client.get(f"/projects/{PROJECT_ID}")
    assert project.status_code == 200
    assert project.json()["source_ref"] == "demo:fantasy_project_v1"

    repeated = client.post("/demo/seed")
    assert repeated.status_code == 200
    assert repeated.json()["nodes_created"] == 0
    assert len(repeated.json()["nodes_skipped"]) == 11


def test_read_generate_permission_blocks_demo_seed(tmp_path):
    settings = _json_settings(tmp_path)
    client = TestClient(create_app(settings))
    lowered = client.put(
        "/settings/agent",
        json={
            "scene_writer": "rule_based",
            "permission_level": "read_generate",
        },
    )
    assert lowered.status_code == 200

    response = client.post("/demo/seed")

    assert response.status_code == 403
    assert response.json()["detail"]["category"] == "permission_denied"
    assert not settings.graph_path.exists()


def _json_settings(tmp_path) -> StoryGraphSettings:
    settings = StoryGraphSettings(tmp_path)
    settings.graph_backend = "json"
    settings.graph_backend_explicit = True
    settings.ensure_workspace()
    return settings
