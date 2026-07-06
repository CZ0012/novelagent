import json

from fastapi.testclient import TestClient

from apps.api.main import create_app
from storygraph.core.config import StoryGraphSettings
from storygraph.services.agent_discussion import WebSearchResult
from storygraph.services.llm_provider import LLMResponse


def test_api_agent_discussion_revises_selection_as_non_canon_proposal(
    tmp_path,
    monkeypatch,
):
    class FakeProvider:
        def generate(self, request):
            assert "这段不好。" in request.messages[-1].content
            assert "本地资料片段" in request.messages[-1].content
            return LLMResponse(
                content=json.dumps(
                    {
                        "reply": "已保留视角限制，只改写选中段落。",
                        "proposal_title": "选区改写提案",
                        "replacement_text": "这段更克制，也更贴近当前冲突。",
                        "self_check": ["只生成协作提案", "未提交 canon"],
                    },
                    ensure_ascii=False,
                )
            )

    monkeypatch.setattr("apps.api.main.create_llm_provider", lambda settings: FakeProvider())
    client = TestClient(create_app(_llm_settings(tmp_path)))
    project_id = _create_project_with_scene(client)
    original_text = "第一段。\n这段不好。\n第三段。"
    draft = client.post(
        f"/projects/{project_id}/scenes/scene_opening/draft",
        json={"text": original_text, "summary": "待修改草稿。"},
    ).json()
    graph_before = client.get(f"/projects/{project_id}/graph/preview").json()
    facts_before = client.get(f"/projects/{project_id}/facts/pending").json()

    response = client.post(
        f"/projects/{project_id}/scenes/scene_opening/agent-discussion",
        json={
            "mode": "revise_selection",
            "instruction": "这段还不好，请改得更克制。",
            "selected_text": "这段不好。",
            "base_text": original_text,
            "include_context_pack": True,
            "include_latest_draft": True,
            "local_sources": [
                {
                    "kind": "imported_document",
                    "ref": "local:note",
                    "title": "资料.md",
                    "text": "本地资料片段：主角此时不能知道秘密。",
                }
            ],
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["replacement_applied"] is True
    assert payload["reply"] == "已保留视角限制，只改写选中段落。"
    assert payload["proposal"]["artifact_type"] == "scene_draft"
    assert payload["proposal"]["status"] == "agent_revised"
    assert "这段更克制" in payload["proposal"]["body"]
    assert "这段不好" not in payload["proposal"]["body"]
    assert payload["proposal"]["source_refs"][1]["ref"] == draft["id"]

    latest_draft = client.get(f"/projects/{project_id}/scenes/scene_opening/draft").json()
    assert latest_draft["draft"]["text"] == original_text
    assert client.get(f"/projects/{project_id}/facts/pending").json() == facts_before
    assert client.get(f"/projects/{project_id}/graph/preview").json() == graph_before


def test_api_agent_discussion_can_include_explicit_web_search_context(
    tmp_path,
    monkeypatch,
):
    captured_user_payload = {}

    class FakeProvider:
        def generate(self, request):
            captured_user_payload.update(json.loads(request.messages[-1].content))
            return LLMResponse(
                content=json.dumps(
                    {
                        "reply": "已参考搜索结果，但只作为资料背景。",
                        "proposal_title": "联网讨论记录",
                        "proposal_body": "# 讨论\n搜索资料仅作参考。",
                        "self_check": ["未写 canon"],
                    },
                    ensure_ascii=False,
                )
            )

    def fake_search(self, query, *, max_results=5):
        assert "钟楼" in query
        return [
            WebSearchResult(
                title="Clock tower reference",
                url="https://example.test/clock",
                snippet="Clock towers can mark civic time.",
            )
        ]

    monkeypatch.setattr("apps.api.main.create_llm_provider", lambda settings: FakeProvider())
    monkeypatch.setattr(
        "storygraph.services.agent_discussion.SimpleWebSearchClient.search",
        fake_search,
    )
    client = TestClient(create_app(_llm_settings(tmp_path)))
    project_id = _create_project_with_scene(client)

    response = client.post(
        f"/projects/{project_id}/scenes/scene_opening/agent-discussion",
        json={
            "mode": "discuss",
            "instruction": "钟楼意象还能怎么写？",
            "include_context_pack": False,
            "include_latest_draft": False,
            "allow_web_search": True,
            "web_search_query": "钟楼 civic time",
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert captured_user_payload["web_search_results"][0]["url"] == "https://example.test/clock"
    assert payload["proposal"]["artifact_type"] == "scene_rebuild"
    assert payload["web_results"][0]["snippet"] == "Clock towers can mark civic time."
    assert payload["proposal"]["source_refs"][-1]["kind"] == "web_search"


def _create_project_with_scene(
    client: TestClient,
    *,
    title: str = "Agent 对话项目",
    chapter_id: str = "chapter_opening",
    scene_id: str = "scene_opening",
) -> str:
    project_id = client.post("/projects", json={"title": title}).json()["project_id"]
    character_id = f"{project_id}_character_placeholder"
    location_id = f"{project_id}_location_placeholder"
    assert client.post(
        f"/projects/{project_id}/characters",
        json={
            "id": character_id,
            "name": "主角",
            "reviewer": "author",
            "rationale": "作者创建视角人物。",
            "source_ref": "author_seed:characters",
        },
    ).status_code == 200
    assert client.post(
        f"/projects/{project_id}/locations",
        json={
            "id": location_id,
            "name": "开场地点",
            "reviewer": "author",
            "rationale": "作者创建开场地点。",
            "source_ref": "author_seed:locations",
        },
    ).status_code == 200
    assert client.post(
        f"/projects/{project_id}/chapters",
        json={
            "id": chapter_id,
            "title": "第一章",
            "reviewer": "author",
            "rationale": "作者创建章节。",
            "source_ref": "author_seed:outline",
        },
    ).status_code == 200
    assert client.post(
        f"/projects/{project_id}/chapters/{chapter_id}/scenes",
        json={
            "id": scene_id,
            "title": "开场",
            "goal": "建立主角处境",
            "conflict": "旧秘密浮现",
            "pov_character_id": character_id,
            "location_id": location_id,
            "timeline_position": "第一天清晨",
            "reviewer": "author",
            "rationale": "作者创建场景。",
            "source_ref": "author_seed:outline",
        },
    ).status_code == 200
    return project_id


def _llm_settings(tmp_path) -> StoryGraphSettings:
    settings = StoryGraphSettings(tmp_path)
    settings.graph_backend = "json"
    settings.graph_backend_explicit = True
    settings.llm_base_url = "https://api.example.test/v1"
    settings.llm_api_key = "test-key"
    settings.llm_model = "test-model"
    settings.ensure_workspace()
    return settings
