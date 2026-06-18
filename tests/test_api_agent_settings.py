from fastapi.testclient import TestClient

from apps.api.main import create_app
from storygraph.core.config import StoryGraphSettings
from storygraph.demo import PROJECT_ID, SCENE_ID


def test_agent_settings_persist_and_do_not_echo_api_key(tmp_path):
    settings = StoryGraphSettings(tmp_path)
    client = TestClient(create_app(settings))

    response = client.put(
        "/settings/agent",
        json={
            "scene_writer": "llm",
            "provider_label": "Local OpenAI compatible",
            "llm_base_url": "http://127.0.0.1:11434/v1",
            "llm_model": "story-model",
            "llm_api_key": "sk-local-secret",
            "llm_json_mode": True,
            "permission_level": "read_generate",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scene_writer"] == "llm"
    assert payload["api_key_configured"] is True
    assert payload["api_key_preview"] == "sk-l...cret"
    assert "sk-local-secret" not in response.text

    second_client = TestClient(create_app(settings))
    persisted = second_client.get("/settings/agent")

    assert persisted.status_code == 200
    assert persisted.json()["llm_model"] == "story-model"
    assert persisted.json()["permission_level"] == "read_generate"


def test_read_only_permission_blocks_draft_generation(tmp_path):
    client = TestClient(create_app(StoryGraphSettings(tmp_path)))
    client.put(
        "/settings/agent",
        json={
            "scene_writer": "rule_based",
            "permission_level": "read_only",
        },
    )

    response = client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/draft")

    assert response.status_code == 403
    assert response.json()["detail"]["category"] == "permission_denied"


def test_permission_level_cannot_self_elevate_through_settings_api(tmp_path):
    client = TestClient(create_app(StoryGraphSettings(tmp_path)))
    lowered = client.put(
        "/settings/agent",
        json={
            "scene_writer": "rule_based",
            "permission_level": "read_only",
        },
    )
    assert lowered.status_code == 200

    elevated = client.put(
        "/settings/agent",
        json={
            "scene_writer": "rule_based",
            "permission_level": "full",
        },
    )

    assert elevated.status_code == 403
    assert elevated.json()["detail"]["category"] == "permission_denied"
    assert client.get("/settings/agent").json()["permission_level"] == "read_only"


def test_read_generate_permission_blocks_canon_review_decision(tmp_path):
    client = TestClient(create_app(StoryGraphSettings(tmp_path)))
    client.put(
        "/settings/agent",
        json={
            "scene_writer": "rule_based",
            "permission_level": "read_generate",
        },
    )
    run_response = client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/runs/scene-generation")
    assert run_response.status_code == 200

    response = client.post(
        f"/projects/{PROJECT_ID}/facts/fact_missing/accept",
        json={"reviewer": "author"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["category"] == "permission_denied"
