from fastapi.testclient import TestClient

from apps.api.main import create_app
from storygraph.core.config import StoryGraphSettings
from storygraph.services.llm_provider import LLMResponse


def test_api_proposal_lifecycle_is_versioned_and_non_canon(tmp_path):
    client = TestClient(create_app(_json_settings(tmp_path)))
    project_id = _create_project_with_scene(client)

    graph_before = client.get(f"/projects/{project_id}/graph/preview").json()
    draft_before = client.get(f"/projects/{project_id}/scenes/scene_opening/draft").json()
    facts_before = client.get(f"/projects/{project_id}/facts/pending").json()

    created = client.post(
        f"/projects/{project_id}/proposals",
        json={
            "id": "proposal_scene_opening",
            "artifact_type": "scene_draft",
            "title": "开场协作草稿",
            "body": "还没有进入 Draft Store 的场景提案。",
            "target_refs": [{"kind": "scene", "ref": "scene_opening"}],
            "source_refs": [{"kind": "author_instruction", "ref": "prompt:opening"}],
            "created_by": "agent",
            "created_via": "llm",
            "model_ref": "KouriChat/deepseek-v4-flash",
        },
    )
    updated = client.patch(
        f"/projects/{project_id}/proposals/proposal_scene_opening",
        json={
            "body": "作者修改后的协作草稿。",
            "expected_version": 1,
        },
    )
    agent_revised = client.post(
        f"/projects/{project_id}/proposals/proposal_scene_opening/revise",
        json={
            "body": "Agent 按作者要求修订后的协作草稿。",
            "expected_version": 2,
        },
    )
    ready = client.post(
        f"/projects/{project_id}/proposals/proposal_scene_opening/submit-review",
        json={"expected_version": 3},
    )
    accepted = client.post(
        f"/projects/{project_id}/proposals/proposal_scene_opening/review",
        json={
            "decision": "accepted",
            "reviewer": "author",
            "note": "接受为非正典协作提案。",
            "expected_version": 4,
        },
    )
    history = client.get(f"/projects/{project_id}/proposals/proposal_scene_opening/versions")

    assert created.status_code == 200
    assert created.json()["contract_version"] == "proposal_artifact_v1"
    assert created.json()["status"] == "drafting"
    assert updated.status_code == 200
    assert updated.json()["status"] == "author_revised"
    assert agent_revised.status_code == 200
    assert agent_revised.json()["status"] == "agent_revised"
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready_for_review"
    assert accepted.status_code == 200
    assert accepted.json()["version"] == 5
    assert accepted.json()["status"] == "accepted"
    assert accepted.json()["review_decision"]["status"] == "accepted"
    assert history.status_code == 200
    assert [proposal["version"] for proposal in history.json()["versions"]] == [1, 2, 3, 4, 5]

    assert client.get(f"/projects/{project_id}/graph/preview").json() == graph_before
    assert client.get(f"/projects/{project_id}/scenes/scene_opening/draft").json() == draft_before
    assert client.get(f"/projects/{project_id}/facts/pending").json() == facts_before

    promoted = client.post(
        f"/projects/{project_id}/proposals/proposal_scene_opening/promote/draft",
        json={"scene_id": "scene_opening", "expected_version": 5},
    )
    latest_draft = client.get(f"/projects/{project_id}/scenes/scene_opening/draft")

    assert promoted.status_code == 200
    assert promoted.json()["draft"]["text"] == "Agent 按作者要求修订后的协作草稿。"
    assert promoted.json()["proposal"]["derived_refs"][-1]["kind"] == "draft"
    assert latest_draft.json()["draft"]["id"] == promoted.json()["draft"]["id"]


def test_api_proposals_are_project_scoped_and_stale_safe(tmp_path):
    client = TestClient(create_app(_json_settings(tmp_path)))
    first_project = _create_project_with_scene(client, title="第一项目")
    second_project = _create_project_with_scene(
        client,
        title="第二项目",
        chapter_id="chapter_second",
        scene_id="scene_second",
    )

    created = client.post(
        f"/projects/{first_project}/proposals",
        json={
            "id": "proposal_project_scoped",
            "artifact_type": "outline_draft",
            "title": "项目内提案",
            "body": "只属于第一个项目。",
        },
    )
    updated = client.patch(
        f"/projects/{first_project}/proposals/proposal_project_scoped",
        json={"body": "第一个更新。", "expected_version": 1},
    )
    stale = client.patch(
        f"/projects/{first_project}/proposals/proposal_project_scoped",
        json={"body": "过期写入。", "expected_version": 1},
    )
    wrong_project = client.get(f"/projects/{second_project}/proposals/proposal_project_scoped")
    proposals = client.get(f"/projects/{first_project}/proposals")

    assert created.status_code == 200
    assert updated.status_code == 200
    assert stale.status_code == 409
    assert wrong_project.status_code == 404
    assert proposals.status_code == 200
    assert [proposal["id"] for proposal in proposals.json()["proposals"]] == [
        "proposal_project_scoped"
    ]


def test_api_agent_revise_can_create_new_proposal_version_without_draft_write(tmp_path):
    client = TestClient(create_app(_json_settings(tmp_path)))
    project_id = _create_project_with_scene(client)
    created = client.post(
        f"/projects/{project_id}/proposals",
        json={
            "id": "proposal_agent_revise",
            "artifact_type": "scene_draft",
            "title": "Agent 修订目标",
            "body": "v1",
            "target_refs": [{"kind": "scene", "ref": "scene_opening"}],
        },
    )

    revised = client.post(
        f"/projects/{project_id}/proposals/proposal_agent_revise/revise",
        json={"expected_version": 1, "actor": "agent", "created_via": "workflow"},
    )
    latest_draft = client.get(f"/projects/{project_id}/scenes/scene_opening/draft")

    assert created.status_code == 200
    assert revised.status_code == 200
    assert revised.json()["version"] == 2
    assert revised.json()["status"] == "agent_revised"
    assert revised.json()["body"] != "v1"
    assert latest_draft.json()["draft"] is None


def test_api_proposal_accept_reject_require_current_version(tmp_path):
    client = TestClient(create_app(_json_settings(tmp_path)))
    project_id = _create_project_with_scene(client)
    created = client.post(
        f"/projects/{project_id}/proposals",
        json={
            "id": "proposal_stale_decision",
            "artifact_type": "scene_draft",
            "title": "版本防陈旧",
            "body": "v1",
        },
    )
    revised = client.patch(
        f"/projects/{project_id}/proposals/proposal_stale_decision",
        json={"body": "v2", "expected_version": 1},
    )

    stale_accept = client.post(
        f"/projects/{project_id}/proposals/proposal_stale_decision/accept",
        json={"reviewer": "author", "expected_version": 1},
    )
    current_reject = client.post(
        f"/projects/{project_id}/proposals/proposal_stale_decision/reject",
        json={"reviewer": "author", "expected_version": 2},
    )

    assert created.status_code == 200
    assert revised.status_code == 200
    assert stale_accept.status_code == 409
    assert current_reject.status_code == 200
    assert current_reject.json()["status"] == "rejected"


def test_api_proposal_permissions_follow_generation_and_full_review(tmp_path):
    client = TestClient(create_app(_json_settings(tmp_path)))
    project_id = _create_project_with_scene(client)

    lowered = client.put(
        "/settings/agent",
        json={
            "scene_writer": "rule_based",
            "permission_level": "read_only",
        },
    )
    blocked_create = client.post(
        f"/projects/{project_id}/proposals",
        json={
            "artifact_type": "scene_draft",
            "title": "被阻止的提案",
            "body": "read_only 不应能创建。",
        },
    )
    readable = client.get(f"/projects/{project_id}/proposals")

    raised_to_generate = client.put(
        "/settings/agent",
        json={
            "scene_writer": "rule_based",
            "permission_level": "read_generate",
        },
    )
    created = client.post(
        f"/projects/{project_id}/proposals",
        json={
            "id": "proposal_permission",
            "artifact_type": "scene_draft",
            "title": "权限提案",
            "body": "read_generate 可以创建。",
        },
    )
    blocked_accept = client.post(
        f"/projects/{project_id}/proposals/proposal_permission/accept",
        json={"reviewer": "author", "expected_version": 1},
    )

    raised_to_full = client.put(
        "/settings/agent",
        json={
            "scene_writer": "rule_based",
            "permission_level": "full",
        },
    )
    accepted = client.post(
        f"/projects/{project_id}/proposals/proposal_permission/accept",
        json={"reviewer": "author", "expected_version": 1},
    )

    assert lowered.status_code == 200
    assert blocked_create.status_code == 403
    assert readable.status_code == 200
    assert raised_to_generate.status_code == 200
    assert created.status_code == 200
    assert blocked_accept.status_code == 403
    assert raised_to_full.status_code == 200
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"


def test_api_fact_draft_promotion_uses_real_source_draft(tmp_path):
    client = TestClient(create_app(_json_settings(tmp_path)))
    project_id = _create_project_with_scene(client)
    marker = (
        "[[fact:id=fact_from_proposal;fact_type=SceneState;"
        "subject=scene_opening;relation=HAS_SECRET;value=true;confidence=0.91]]"
    )
    draft = client.post(
        f"/projects/{project_id}/scenes/scene_opening/draft",
        json={"text": f"正文里有明确事实标记。{marker}", "summary": "事实来源草稿。"},
    ).json()
    created = client.post(
        f"/projects/{project_id}/proposals",
        json={
            "id": "proposal_fact_draft",
            "artifact_type": "fact_draft",
            "title": "候选事实协作稿",
            "body": marker,
            "target_refs": [{"kind": "draft", "ref": draft["id"]}],
        },
    )
    accepted = client.post(
        f"/projects/{project_id}/proposals/proposal_fact_draft/accept",
        json={"reviewer": "author", "expected_version": 1},
    )
    graph_before = client.get(f"/projects/{project_id}/graph/preview").json()

    promoted = client.post(
        f"/projects/{project_id}/proposals/proposal_fact_draft/promote/candidate-facts",
        json={"source_draft_id": draft["id"], "expected_version": 2},
    )
    pending = client.get(f"/projects/{project_id}/facts/pending")

    assert created.status_code == 200
    assert accepted.status_code == 200
    assert promoted.status_code == 200
    assert promoted.json()["source_draft"]["id"] == draft["id"]
    assert promoted.json()["candidates"][0]["source_draft_id"] == draft["id"]
    assert promoted.json()["candidates"][0]["evidence"][-1]["kind"] == "proposal_artifact"
    assert promoted.json()["proposal"]["derived_refs"][-1]["kind"] == "candidate_fact"
    assert pending.json()["facts"][0]["id"] == "fact_from_proposal"
    assert client.get(f"/projects/{project_id}/graph/preview").json() == graph_before


def test_api_document_fact_extraction_creates_editable_fact_draft(tmp_path, monkeypatch):
    class FakeProvider:
        def generate(self, request):
            return LLMResponse(
                content=(
                    '{"facts":[{"id":"fact_linjin_status",'
                    '"fact_type":"CharacterState",'
                    '"subject":"character_linj",'
                    '"relation":"HAS_STATE",'
                    '"object":null,'
                    '"operation":"update_node",'
                    '"confidence":0.87,'
                    '"rationale":"资料说明林瑾正在寻找遗失信件。",'
                    '"quote":"林瑾正在寻找遗失信件",'
                    '"properties":{"current_status":"寻找遗失信件"}}]}'
                )
            )

    monkeypatch.setattr("apps.api.main.create_llm_provider", lambda settings: FakeProvider())
    settings = _json_settings(tmp_path)
    settings.llm_base_url = "https://api.example.test/v1"
    settings.llm_api_key = "test-key"
    settings.llm_model = "test-model"
    client = TestClient(create_app(settings))
    project_id = _create_project_with_scene(client)
    graph_before = client.get(f"/projects/{project_id}/graph/preview").json()

    response = client.post(
        f"/projects/{project_id}/scenes/scene_opening/extract-document-facts",
        json={
            "title": "设定资料.docx",
            "text": "林瑾正在寻找遗失信件。其他段落。",
            "source_ref": "import:local-doc",
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["proposal"]["artifact_type"] == "fact_draft"
    assert "[[fact:id=fact_linjin_status" in payload["proposal"]["body"]
    assert payload["source_draft"]["summary"] == "导入资料源：设定资料.docx"
    assert payload["candidate_previews"][0]["source_draft_id"] == payload["source_draft"]["id"]
    assert payload["candidate_previews"][0]["source_span"]["quote"] == "林瑾正在寻找遗失信件"
    assert payload["candidate_previews"][0]["evidence"][-1]["kind"] == "proposal_artifact"
    assert client.get(f"/projects/{project_id}/facts/pending").json()["facts"] == []
    assert client.get(f"/projects/{project_id}/graph/preview").json() == graph_before


def test_api_extract_state_can_create_fact_draft_proposal_without_candidate_store(tmp_path):
    client = TestClient(create_app(_json_settings(tmp_path)))
    project_id = _create_project_with_scene(client)
    marker = (
        "[[fact:id=fact_preview_only;fact_type=SceneState;"
        "subject=scene_opening;relation=HAS_CLUE;value=true;confidence=0.9]]"
    )
    draft = client.post(
        f"/projects/{project_id}/scenes/scene_opening/draft",
        json={"text": f"先生成协作事实提案。{marker}", "summary": "事实预览来源草稿。"},
    ).json()
    graph_before = client.get(f"/projects/{project_id}/graph/preview").json()

    response = client.post(
        f"/projects/{project_id}/scenes/scene_opening/extract-state",
        json={"output_target": "proposal_workspace"},
    )
    pending = client.get(f"/projects/{project_id}/facts/pending")
    proposals = client.get(f"/projects/{project_id}/proposals")

    assert response.status_code == 200
    assert response.json()["candidates"] == []
    assert response.json()["candidate_previews"][0]["id"] == "fact_preview_only"
    assert response.json()["proposal"]["artifact_type"] == "fact_draft"
    assert response.json()["proposal"]["body_format"] == "structured_json"
    assert response.json()["proposal"]["target_refs"][1]["ref"] == draft["id"]
    assert pending.json()["facts"] == []
    assert proposals.json()["proposals"][0]["id"] == response.json()["proposal"]["id"]
    assert client.get(f"/projects/{project_id}/graph/preview").json() == graph_before


def test_api_promotion_rejects_wrong_status_type_and_permission(tmp_path):
    client = TestClient(create_app(_json_settings(tmp_path)))
    project_id = _create_project_with_scene(client)
    draft = client.post(
        f"/projects/{project_id}/scenes/scene_opening/draft",
        json={"text": "没有事实标记。", "summary": "普通草稿。"},
    ).json()
    scene_proposal = client.post(
        f"/projects/{project_id}/proposals",
        json={
            "id": "proposal_unaccepted_scene",
            "artifact_type": "scene_draft",
            "title": "未接受场景提案",
            "body": "不能直接提升。",
        },
    )
    blocked_status = client.post(
        f"/projects/{project_id}/proposals/proposal_unaccepted_scene/promote/draft",
        json={"scene_id": "scene_opening", "expected_version": 1},
    )
    accepted_scene = client.post(
        f"/projects/{project_id}/proposals/proposal_unaccepted_scene/accept",
        json={"reviewer": "author", "expected_version": 1},
    )

    client.put(
        "/settings/agent",
        json={"scene_writer": "rule_based", "permission_level": "read_generate"},
    )
    blocked_permission = client.post(
        f"/projects/{project_id}/proposals/proposal_unaccepted_scene/promote/draft",
        json={"scene_id": "scene_opening", "expected_version": 2},
    )
    client.put(
        "/settings/agent",
        json={"scene_writer": "rule_based", "permission_level": "full"},
    )
    wrong_type = client.post(
        f"/projects/{project_id}/proposals/proposal_unaccepted_scene/promote/candidate-facts",
        json={"source_draft_id": draft["id"], "expected_version": 2},
    )

    assert scene_proposal.status_code == 200
    assert blocked_status.status_code == 409
    assert accepted_scene.status_code == 200
    assert blocked_permission.status_code == 403
    assert wrong_type.status_code == 409


def _create_project_with_scene(
    client: TestClient,
    *,
    title: str = "提案项目",
    chapter_id: str = "chapter_opening",
    scene_id: str = "scene_opening",
) -> str:
    project_id = client.post("/projects", json={"title": title}).json()["project_id"]
    character_id = f"{project_id}_character_placeholder"
    location_id = f"{project_id}_location_placeholder"
    character = client.post(
        f"/projects/{project_id}/characters",
        json={
            "id": character_id,
            "name": "主角",
            "reviewer": "author",
            "rationale": "作者创建视角人物。",
            "source_ref": "author_seed:characters",
        },
    )
    location = client.post(
        f"/projects/{project_id}/locations",
        json={
            "id": location_id,
            "name": "开场地点",
            "reviewer": "author",
            "rationale": "作者创建开场地点。",
            "source_ref": "author_seed:locations",
        },
    )
    chapter = client.post(
        f"/projects/{project_id}/chapters",
        json={
            "id": chapter_id,
            "title": "第一章",
            "reviewer": "author",
            "rationale": "作者创建章节。",
            "source_ref": "author_seed:outline",
        },
    )
    scene = client.post(
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
    )
    assert character.status_code == 200
    assert location.status_code == 200
    assert chapter.status_code == 200
    assert scene.status_code == 200
    return project_id


def _json_settings(tmp_path) -> StoryGraphSettings:
    settings = StoryGraphSettings(tmp_path)
    settings.graph_backend = "json"
    settings.graph_backend_explicit = True
    settings.ensure_workspace()
    return settings
