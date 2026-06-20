from fastapi.testclient import TestClient

from apps.api.main import create_app
from storygraph.core.config import StoryGraphSettings


def test_persistent_api_lists_empty_workspace_without_demo_seed(tmp_path):
    client = TestClient(create_app(_json_settings(tmp_path)))

    response = client.get("/projects")

    assert response.status_code == 200
    assert response.json()["projects"] == []


def test_author_can_seed_project_outline_scene_and_world_rule(tmp_path):
    client = TestClient(create_app(_json_settings(tmp_path)))

    project = client.post(
        "/projects",
        json={
            "title": "我的长篇",
            "genre": "fantasy",
            "language": "zh-CN",
            "target_length": "30万字",
            "narrative_pov": "第三人称有限视角",
        },
    )
    project_id = project.json()["project_id"]
    chapter = client.post(
        f"/projects/{project_id}/chapters",
        json={
            "id": "chapter_opening",
            "title": "第一章",
            "chapter_index": 1,
            "summary": "开端。",
            "reviewer": "author",
            "rationale": "作者创建章节。",
            "source_ref": "author_seed:outline",
        },
    )
    scene = client.post(
        f"/projects/{project_id}/chapters/chapter_opening/scenes",
        json={
            "id": "scene_opening",
            "title": "开场",
            "scene_index": 1,
            "goal": "建立主角处境",
            "conflict": "旧秘密开始浮现",
            "timeline_position": "第一天清晨",
            "status": "drafting",
            "reviewer": "author",
            "rationale": "作者创建场景。",
            "source_ref": "author_seed:outline",
        },
    )
    rule = client.post(
        f"/projects/{project_id}/world-rules",
        json={
            "id": "worldrule_secret_cost",
            "domain": "秘密",
            "rule": "重大秘密必须经由明确场景揭示。",
            "severity": "high",
            "reviewer": "author",
            "rationale": "作者创建世界规则。",
            "source_ref": "author_seed:rules",
        },
    )

    assert project.status_code == 200
    assert chapter.status_code == 200
    assert scene.status_code == 200
    assert rule.status_code == 200

    projects = client.get("/projects")
    assert projects.status_code == 200
    assert projects.json()["projects"][0]["id"] == project_id
    assert projects.json()["projects"][0]["chapters"][0]["id"] == "chapter_opening"
    assert projects.json()["projects"][0]["chapters"][0]["scenes"][0]["id"] == "scene_opening"

    outline = client.get(f"/projects/{project_id}/outline")
    assert outline.status_code == 200
    assert outline.json()["chapters"][0]["scenes"][0]["goal"] == "建立主角处境"

    scene_detail = client.get(f"/projects/{project_id}/scenes/scene_opening")
    assert scene_detail.status_code == 200
    assert scene_detail.json()["properties"]["conflict"] == "旧秘密开始浮现"

    preview = client.get(f"/projects/{project_id}/graph/preview")
    assert preview.status_code == 200
    assert [item["id"] for item in preview.json()["timeline"]] == ["scene_opening"]
    assert any(
        relation["type"] == "HAS_SCENE"
        for relation in preview.json()["relationships"]
    )

    pending = client.get(f"/projects/{project_id}/facts/pending")
    assert pending.status_code == 200
    assert pending.json()["facts"] == []


def test_latest_draft_endpoint_returns_imported_scene_draft(tmp_path):
    client = TestClient(create_app(_json_settings(tmp_path)))
    project_id = client.post("/projects", json={"title": "草稿项目"}).json()["project_id"]
    client.post(
        f"/projects/{project_id}/chapters",
        json={
            "id": "chapter_draft",
            "title": "草稿章",
            "reviewer": "author",
            "rationale": "作者创建章节。",
            "source_ref": "author_seed:outline",
        },
    )
    client.post(
        f"/projects/{project_id}/chapters/chapter_draft/scenes",
        json={
            "id": "scene_draft",
            "title": "导入场景",
            "reviewer": "author",
            "rationale": "作者创建场景。",
            "source_ref": "author_seed:outline",
        },
    )

    before = client.get(f"/projects/{project_id}/scenes/scene_draft/draft")
    saved = client.post(
        f"/projects/{project_id}/scenes/scene_draft/draft",
        json={"text": "导入正文", "summary": "导入文档设为草稿。"},
    )
    after = client.get(f"/projects/{project_id}/scenes/scene_draft/draft")

    assert before.status_code == 200
    assert before.json()["draft"] is None
    assert saved.status_code == 200
    assert after.status_code == 200
    assert after.json()["draft"]["text"] == "导入正文"


def _json_settings(tmp_path) -> StoryGraphSettings:
    settings = StoryGraphSettings(tmp_path)
    settings.graph_backend = "json"
    settings.graph_backend_explicit = True
    settings.ensure_workspace()
    return settings
