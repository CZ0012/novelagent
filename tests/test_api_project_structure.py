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


def test_project_structure_apply_is_idempotent_for_same_proposal(tmp_path):
    client = TestClient(create_app(_json_settings(tmp_path)))
    project_id = client.post("/projects", json={"title": "重复应用项目"}).json()["project_id"]

    created = client.post(
        f"/projects/{project_id}/imports/structure-draft",
        json={
            "title": "重复应用.txt",
            "text": "第一章 起点\n\n林瑾推开门。\n\n第二章 回声\n\n门后的钟声回应她。",
            "source_ref": "import:repeat-apply",
            "max_chapters": 4,
            "max_scenes_per_chapter": 2,
        },
    ).json()
    accepted = client.post(
        f"/projects/{project_id}/proposals/{created['proposal']['id']}/accept",
        json={"reviewer": "author", "expected_version": 1},
    ).json()
    first_apply = client.post(
        f"/projects/{project_id}/proposals/{created['proposal']['id']}/apply/project-structure",
        json={
            "reviewer": "author",
            "rationale": "作者确认导入生成的章节场景结构。",
            "expected_version": accepted["version"],
        },
    )
    second_apply = client.post(
        f"/projects/{project_id}/proposals/{created['proposal']['id']}/apply/project-structure",
        json={
            "reviewer": "author",
            "rationale": "作者重复点击应用按钮。",
            "expected_version": first_apply.json()["proposal"]["version"],
        },
    )
    outline = client.get(f"/projects/{project_id}/outline").json()
    pending = client.get(f"/projects/{project_id}/facts/pending").json()

    assert first_apply.status_code == 200
    assert second_apply.status_code == 200
    assert first_apply.json()["already_applied"] is False
    assert second_apply.json()["already_applied"] is True
    assert [chapter["id"] for chapter in second_apply.json()["chapters"]] == [
        chapter["id"] for chapter in first_apply.json()["chapters"]
    ]
    assert [scene["id"] for scene in second_apply.json()["scenes"]] == [
        scene["id"] for scene in first_apply.json()["scenes"]
    ]
    assert len(outline["chapters"]) == len(first_apply.json()["chapters"])
    assert sum(len(chapter["scenes"]) for chapter in outline["chapters"]) == len(
        first_apply.json()["scenes"]
    )
    assert pending["facts"] == []


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


def test_author_can_update_existing_scene_metadata_without_candidate_writes(tmp_path):
    client = TestClient(create_app(_json_settings(tmp_path)))
    project_id = client.post("/projects", json={"title": "场景整理项目"}).json()["project_id"]
    client.post(
        f"/projects/{project_id}/chapters",
        json={
            "id": "chapter_edit",
            "title": "待整理章",
            "reviewer": "author",
            "rationale": "作者创建章节。",
            "source_ref": "author_seed:outline",
        },
    )
    client.post(
        f"/projects/{project_id}/chapters/chapter_edit/scenes",
        json={
            "id": "scene_previous",
            "title": "前一场景",
            "scene_index": 1,
            "reviewer": "author",
            "rationale": "作者创建前置场景。",
            "source_ref": "author_seed:outline",
        },
    )
    client.post(
        f"/projects/{project_id}/chapters/chapter_edit/scenes",
        json={
            "id": "scene_edit",
            "title": "待整理场景",
            "scene_index": 2,
            "reviewer": "author",
            "rationale": "作者创建场景。",
            "source_ref": "author_seed:outline",
        },
    )
    client.post(
        f"/projects/{project_id}/characters",
        json={
            "id": "character_editor",
            "name": "整理者",
            "reviewer": "author",
            "rationale": "作者创建 POV 人物。",
            "source_ref": "author_seed:story_bible",
        },
    )
    client.post(
        f"/projects/{project_id}/locations",
        json={
            "id": "location_archive",
            "name": "档案室",
            "reviewer": "author",
            "rationale": "作者创建地点。",
            "source_ref": "author_seed:story_bible",
        },
    )
    previous_draft = client.post(
        f"/projects/{project_id}/scenes/scene_previous/draft",
        json={"text": "前一场正文。", "summary": "前一场摘要。"},
    )

    updated = client.patch(
        f"/projects/{project_id}/scenes/scene_edit",
        json={
            "title": "整理后的场景",
            "scene_index": 3,
            "pov_character_id": "character_editor",
            "location_id": "location_archive",
            "timeline_position": "第一天夜晚",
            "goal": "整理导入结构中的关键线索",
            "conflict": "档案被人为打乱",
            "outcome": "确认旧档案缺页来自内部调换",
            "emotional_turn": "从怀疑转为警觉",
            "previous_scene_id": "scene_previous",
            "style_constraints": {
                "pov": "third-person limited",
                "tense": "past",
                "tone": "冷静克制",
                "sentence_rhythm": "短句推进",
                "diction": "避免华丽比喻",
                "dialogue_style": "含蓄短句",
                "banned_patterns": ["突然意识到"],
            },
            "required_characters": ["character_editor"],
            "must_include": ["旧档案编号"],
            "must_not_violate": ["不要自动提交 canon 事实"],
            "status": "drafting",
            "reviewer": "author",
            "rationale": "作者整理导入后的场景元数据。",
            "source_ref": "author_seed:scene_metadata",
        },
    )
    scene = client.get(f"/projects/{project_id}/scenes/scene_edit")
    context = client.post(f"/projects/{project_id}/scenes/scene_edit/context-pack")
    pending = client.get(f"/projects/{project_id}/facts/pending")

    assert previous_draft.status_code == 200
    assert updated.status_code == 200
    assert scene.json()["properties"]["title"] == "整理后的场景"
    assert scene.json()["properties"]["pov_character_id"] == "character_editor"
    assert scene.json()["properties"]["location_id"] == "location_archive"
    assert scene.json()["properties"]["outcome"] == "确认旧档案缺页来自内部调换"
    assert scene.json()["properties"]["emotional_turn"] == "从怀疑转为警觉"
    assert scene.json()["properties"]["previous_scene_id"] == "scene_previous"
    assert scene.json()["properties"]["style_constraints"]["tone"] == "冷静克制"
    assert scene.json()["properties"]["style_constraints"]["banned_patterns"] == ["突然意识到"]
    assert scene.json()["properties"]["status"] == "drafting"
    assert scene.json()["properties"]["must_include"] == ["旧档案编号"]
    assert context.status_code == 200
    assert context.json()["pov_character_id"] == "character_editor"
    assert context.json()["location_id"] == "location_archive"
    assert context.json()["previous_scene_summary"] == "前一场摘要。"
    assert context.json()["style_constraints"]["tone"] == "冷静克制"
    assert context.json()["style_constraints"]["dialogue_style"] == "含蓄短句"
    assert context.json()["style_constraints"]["banned_patterns"] == ["突然意识到"]
    assert not context.json()["missing_context"]
    assert pending.json()["facts"] == []


def test_author_can_update_existing_chapter_metadata_without_side_effects(tmp_path):
    client = TestClient(create_app(_json_settings(tmp_path)))
    project_id = client.post("/projects", json={"title": "章节整理项目"}).json()["project_id"]
    client.post(
        f"/projects/{project_id}/chapters",
        json={
            "id": "chapter_cleanup",
            "title": "导入章",
            "chapter_index": 1,
            "summary": "旧摘要。",
            "reviewer": "author",
            "rationale": "作者创建章节。",
            "source_ref": "author_seed:outline",
        },
    )
    client.post(
        f"/projects/{project_id}/chapters/chapter_cleanup/scenes",
        json={
            "id": "scene_stays_attached",
            "title": "章节下场景",
            "reviewer": "author",
            "rationale": "作者创建场景。",
            "source_ref": "author_seed:outline",
        },
    )
    proposals_before = client.get(f"/projects/{project_id}/proposals").json()
    graph_before = client.get(f"/projects/{project_id}/graph/preview").json()

    updated = client.patch(
        f"/projects/{project_id}/chapters/chapter_cleanup",
        json={
            "title": "整理后的章节",
            "volume_index": 2,
            "chapter_index": 4,
            "summary": "作者整理后的章节摘要。",
            "purpose": "承接导入结构并准备写作。",
            "status": "planned",
            "reviewer": "author",
            "rationale": "作者整理导入后的章节元数据。",
            "source_ref": "author_seed:chapter_metadata",
        },
    )
    outline = client.get(f"/projects/{project_id}/outline").json()
    pending = client.get(f"/projects/{project_id}/facts/pending").json()
    proposals_after = client.get(f"/projects/{project_id}/proposals").json()
    graph_after = client.get(f"/projects/{project_id}/graph/preview").json()

    assert updated.status_code == 200
    assert updated.json()["id"] == "chapter_cleanup"
    assert updated.json()["properties"]["title"] == "整理后的章节"
    assert updated.json()["properties"]["chapter_index"] == 4
    assert outline["chapters"][0]["id"] == "chapter_cleanup"
    assert outline["chapters"][0]["title"] == "整理后的章节"
    assert outline["chapters"][0]["summary"] == "作者整理后的章节摘要。"
    assert outline["chapters"][0]["purpose"] == "承接导入结构并准备写作。"
    assert outline["chapters"][0]["scenes"][0]["id"] == "scene_stays_attached"
    assert pending["facts"] == []
    assert proposals_after == proposals_before
    assert len(graph_after["nodes"]) == len(graph_before["nodes"])
    assert len(graph_after["relationships"]) == len(graph_before["relationships"])


def test_project_story_bible_lists_are_project_scoped_and_read_only(tmp_path):
    client = TestClient(create_app(_json_settings(tmp_path)))
    project_id = client.post("/projects", json={"title": "选项项目"}).json()["project_id"]
    other_project_id = client.post("/projects", json={"title": "其他项目"}).json()["project_id"]
    client.post(
        f"/projects/{project_id}/characters",
        json={
            "id": "character_option",
            "name": "选项人物",
            "reviewer": "author",
            "rationale": "作者创建人物。",
            "source_ref": "author_seed:characters",
        },
    )
    client.post(
        f"/projects/{project_id}/locations",
        json={
            "id": "location_option",
            "name": "选项地点",
            "reviewer": "author",
            "rationale": "作者创建地点。",
            "source_ref": "author_seed:locations",
        },
    )
    client.post(
        f"/projects/{other_project_id}/characters",
        json={
            "id": "character_other",
            "name": "其他人物",
            "reviewer": "author",
            "rationale": "作者创建其他项目人物。",
            "source_ref": "author_seed:characters",
        },
    )
    client.post(
        f"/projects/{other_project_id}/locations",
        json={
            "id": "location_other",
            "name": "其他地点",
            "reviewer": "author",
            "rationale": "作者创建其他项目地点。",
            "source_ref": "author_seed:locations",
        },
    )

    graph_before = client.get(f"/projects/{project_id}/graph/preview").json()
    characters = client.get(f"/projects/{project_id}/characters")
    locations = client.get(f"/projects/{project_id}/locations")
    graph_after = client.get(f"/projects/{project_id}/graph/preview").json()
    pending = client.get(f"/projects/{project_id}/facts/pending").json()

    assert characters.status_code == 200
    assert locations.status_code == 200
    assert [item["id"] for item in characters.json()["characters"]] == ["character_option"]
    assert [item["id"] for item in locations.json()["locations"]] == ["location_option"]
    assert characters.json()["characters"][0]["properties"]["name"] == "选项人物"
    assert locations.json()["locations"][0]["properties"]["name"] == "选项地点"
    assert graph_after == graph_before
    assert pending["facts"] == []


def _json_settings(tmp_path) -> StoryGraphSettings:
    settings = StoryGraphSettings(tmp_path)
    settings.graph_backend = "json"
    settings.graph_backend_explicit = True
    settings.ensure_workspace()
    return settings
