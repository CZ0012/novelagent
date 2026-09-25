import json

import pytest
from fastapi.testclient import TestClient

from apps.api.main import create_app
from storygraph.core.config import StoryGraphSettings
from storygraph.services.llm_provider import LLMResponse


@pytest.mark.parametrize("mode", ["discuss", "continue_scene"])
def test_unplanned_scene_can_discuss_and_continue_without_inventing_canon(tmp_path, monkeypatch, mode):
    settings = StoryGraphSettings(tmp_path)
    settings.llm_base_url = "https://example.test/v1"
    settings.llm_api_key = "synthetic-test-key"
    settings.llm_model = "synthetic-model"
    client = TestClient(create_app(settings))
    project_id = client.post("/projects", json={"title": "即兴写作", "language": "zh-CN"}).json()[
        "project_id"
    ]
    provenance = {"reviewer": "author", "rationale": "创建写作位置。", "source_ref": "test:author"}
    assert client.post(f"/projects/{project_id}/chapters", json={
        "id": "chapter_unplanned", "title": "第一章", **provenance,
    }).status_code == 200
    scene = client.post(f"/projects/{project_id}/chapters/chapter_unplanned/scenes", json={
        "id": "scene_unplanned", "title": "开场", **provenance,
    })
    assert scene.status_code == 200
    original = "雨停了。他收起伞，推开那扇门。"
    scene_route = f"/projects/{project_id}/scenes/scene_unplanned"
    saved = client.post(f"{scene_route}/draft", json={"text": original}).json()
    graph_before = settings.graph_path.read_bytes()
    pending_before = client.get(f"/projects/{project_id}/facts/pending").json()
    captured = []

    class FakeProvider:
        def generate(self, request):
            captured.append(json.loads(request.messages[-1].content))
            return LLMResponse(content=json.dumps({
                "reply": "可沿着门后的声音展开，不新增人物或地点设定。",
                "proposal_title": "开场建议",
                "proposal_body": "让脚步声带出眼前的悬念。",
                "continuation_text": "门后响起脚步声。他停住，握紧伞柄。",
            }, ensure_ascii=False))

    monkeypatch.setattr("apps.api.main.create_llm_provider", lambda settings: FakeProvider())
    response = client.post(f"{scene_route}/agent-discussion", json={
        "mode": mode, "instruction": "推进眼前的悬念。", "included_draft_id": saved["id"],
        # Exercise the same default include_context_pack=true path as the workbench.
    })
    assert response.status_code == 200, response.text
    context_pack = captured[0]["context_pack"]
    for field in ("pov_character_id", "location_id", "timeline_position", "scene_goal", "conflict"):
        assert context_pack[field] == ""
    gaps = {gap["ref"]: gap for gap in context_pack["missing_context"]}
    for field in ("pov_character_id", "location_id", "timeline_position", "goal", "conflict"):
        assert gaps[field]["kind"] == "missing_scene_field"
    assert gaps["pov_character_id"]["severity"] == "critical"
    assert gaps["location_id"]["severity"] == "critical"
    assert context_pack["required_characters"] == []
    assert context_pack["knowledge_boundaries"] == []
    if mode == "continue_scene":
        assert response.json()["proposal"]["body"] == (
            original + "\n\n门后响起脚步声。他停住，握紧伞柄。"
        )
    assert response.json()["proposal"]["status"] == "agent_revised"
    assert client.get(f"{scene_route}/draft").json()["draft"]["id"] == saved["id"]
    assert client.get(f"{scene_route}/draft").json()["draft"]["text"] == original
    assert client.get(f"/projects/{project_id}/facts/pending").json() == pending_before
    assert settings.graph_path.read_bytes() == graph_before

    # Full scene generation retains the existing critical-context safety gate.
    blocked = client.post(f"{scene_route}/draft")
    assert blocked.status_code == 409
    assert "critical missing context" in blocked.text
    assert len(captured) == 1
    assert settings.graph_path.read_bytes() == graph_before
