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


def test_author_can_update_project_metadata(tmp_path):
    client = TestClient(create_app(_json_settings(tmp_path)))
    project_id = client.post("/projects", json={"title": "旧标题"}).json()["project_id"]

    response = client.patch(
        f"/projects/{project_id}",
        json={
            "title": "新标题",
            "genre": "science-fantasy",
            "language": "zh-CN",
            "target_length": "80万字",
            "narrative_pov": "多视角",
        },
    )
    project = client.get(f"/projects/{project_id}")

    assert response.status_code == 200
    assert project.json()["properties"]["title"] == "新标题"
    assert project.json()["properties"]["genre"] == "science-fantasy"
    assert project.json()["properties"]["target_length"] == "80万字"
    assert project.json()["properties"]["narrative_pov"] == "多视角"


def test_imported_document_structure_draft_requires_accept_before_project_tree_write(tmp_path):
    client = TestClient(create_app(_json_settings(tmp_path)))
    project_id = client.post("/projects", json={"title": "导入项目"}).json()["project_id"]
    graph_before = client.get(f"/projects/{project_id}/graph/preview").json()

    created = client.post(
        f"/projects/{project_id}/imports/structure-draft",
        json={
            "title": "已有小说.docx",
            "text": (
                "第一章 星门开启\n\n"
                "林瑾在旧港醒来，发现天空挂着陌生星图。\n\n"
                "她跟随钟声进入地下车站，遇见追索旧史的人。\n\n"
                "第二章 失落年表\n\n"
                "众人争夺繁星编年史的残页，城市开始停电。"
            ),
            "source_ref": "import:local-doc",
            "max_chapters": 4,
            "max_scenes_per_chapter": 3,
        },
    )
    outline_after_create = client.get(f"/projects/{project_id}/outline")
    pending_after_create = client.get(f"/projects/{project_id}/facts/pending")

    assert created.status_code == 200
    payload = created.json()
    assert payload["proposal"]["artifact_type"] == "project_structure_draft"
    assert payload["proposal"]["body_format"] == "structured_json"
    assert payload["proposal"]["status"] == "agent_revised"
    assert payload["outline"]["chapters"][0]["scenes"]
    assert outline_after_create.json()["chapters"] == []
    assert pending_after_create.json()["facts"] == []
    assert client.get(f"/projects/{project_id}/graph/preview").json() == graph_before

    accepted = client.post(
        f"/projects/{project_id}/proposals/{payload['proposal']['id']}/accept",
        json={"reviewer": "author", "expected_version": 1},
    )
    applied = client.post(
        f"/projects/{project_id}/proposals/{payload['proposal']['id']}/apply/project-structure",
        json={
            "reviewer": "author",
            "rationale": "作者确认导入生成的章节场景结构。",
            "expected_version": 2,
        },
    )
    outline_after_apply = client.get(f"/projects/{project_id}/outline")
    pending_after_apply = client.get(f"/projects/{project_id}/facts/pending")

    assert accepted.status_code == 200
    assert applied.status_code == 200
    assert len(applied.json()["chapters"]) == 2
    assert len(applied.json()["scenes"]) >= 2
    assert applied.json()["proposal"]["derived_refs"][-1]["kind"] == "graph_node"
    assert outline_after_apply.json()["chapters"][0]["title"].startswith("第一章")
    assert outline_after_apply.json()["chapters"][0]["scenes"][0]["status"] == "planned"
    assert pending_after_apply.json()["facts"] == []


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
