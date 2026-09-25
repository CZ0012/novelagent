import json

import pytest
from fastapi.testclient import TestClient

from apps.api.main import create_app
from storygraph.core.config import StoryGraphSettings
from storygraph.core.errors import ContractError
from storygraph.services.llm_provider import LLMResponse
from storygraph.services.project_structure_analyzer import (
    LLMProjectStructureAnalyzer,
    RuleBasedProjectStructureAnalyzer,
    validate_project_structure_output_language,
)


def chinese_outline():
    return {
        "summary": "主角发现旧城的秘密。",
        "chapters": [{
            "title": "序章", "summary": "一次突如其来的告别。", "purpose": "建立冲突。",
            "scenes": [{
                "title": "出发前夜", "summary": "主角决定离开旧城。",
                "goal": "找到失踪的朋友。", "conflict": "城门已经关闭。",
                "pov_label": "Alice", "location_label": "Mars",
            }],
        }],
    }


class CapturingProvider:
    def __init__(self, payload):
        self.payload = payload
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return LLMResponse(content=json.dumps(self.payload, ensure_ascii=False))


@pytest.mark.parametrize("field,value", [
    ("chapter_title", "Prologue"),
    ("chapter_title", "The Hero's Sacrifice"),
    ("chapter_title", "第1章 The Hero's Sacrifice"),
    ("chapter_title", "第 1 章 The Hero's Sacrifice"),
    ("chapter_title", "第一章The Hero's Sacrifice"),
    ("chapter_title", "Chapter 1 Arrival"),
    ("scene_title", "The Last Gift"),
    ("scene_title", "The Awakening of 林谨"),
    ("chapter_title", "第一章 The Return of 林谨"),
    ("scene_title", "Scene 1"),
    ("summary", "He returns."),
    ("purpose", "Reveal the secret"),
    ("goal", "Find the key"),
    ("conflict", "The gate is shut"),
])
def test_chinese_structure_rejects_short_english_narrative_without_retry_or_text_leak(field, value):
    outline = chinese_outline()
    chapter = outline["chapters"][0]
    scene = chapter["scenes"][0]
    if field == "chapter_title":
        chapter["title"] = value
    elif field == "scene_title":
        scene["title"] = value
    elif field == "purpose":
        chapter[field] = value
    else:
        scene[field] = value
    provider = CapturingProvider(outline)
    analyzer = LLMProjectStructureAnalyzer(
        provider=provider, model="synthetic-model", output_language="zh-CN",
    )
    with pytest.raises(ContractError, match="output_language zh-CN") as exc:
        analyzer.analyze(
            project_id="project_test", title="测试资料", source_text="主角离开旧城。",
            source_language="zh-CN",
        )
    assert value not in str(exc.value)
    assert len(provider.requests) == 1
    sent = json.loads(provider.requests[0].messages[-1].content)
    assert sent["output_language"] == "zh-CN"
    assert sent["output_example"]["chapters"][0]["title"] == "序章"


@pytest.mark.parametrize("name", [
    "AI", "NASA", "GPT", "X", "Alice", "Mars", "New York",
    "The Who", "King's Landing", "Alice's Restaurant", "House of Black",
])
def test_structure_preserves_acronyms_and_declared_proper_names(name):
    outline = chinese_outline()
    chapter = outline["chapters"][0]
    chapter["title"] = name
    chapter["scenes"][0]["title"] = name
    chapter["scenes"][0]["location_label"] = name
    outline["source_title"] = "Original English source title"
    chapter["scenes"][0]["timeline_position"] = "Before the old calendar began"
    validate_project_structure_output_language(outline=outline, output_language="zh-CN")
    assert chapter["title"] == name


@pytest.mark.parametrize("name", [
    "AI", "Mars", "Alice", "NASA", "New York", "林谨与 AI", "AI 的觉醒", "The Who 的演出",
])
def test_short_ambiguous_name_titles_do_not_need_declared_labels(name):
    outline = {"chapters": [{"title": name, "scenes": [{"title": name}]}]}
    validate_project_structure_output_language(outline=outline, output_language="zh-CN")


def test_english_structure_uses_english_example_and_rejects_generic_chinese_heading():
    provider = CapturingProvider({"chapters": [{"title": "Prologue", "scenes": []}]})
    analyzer = LLMProjectStructureAnalyzer(
        provider=provider, model="synthetic-model", output_language="en-US",
    )
    result = analyzer.analyze(
        project_id="project_test", title="Source", source_text="The story begins.",
        source_language="en-US",
    )
    assert result.outline["chapters"][0]["title"] == "Prologue"
    assert json.loads(provider.requests[0].messages[-1].content)["output_example"]["summary"] == (
        "Project summary"
    )
    with pytest.raises(ContractError, match="output_language en-US"):
        validate_project_structure_output_language(
            outline={"chapters": [{"title": "序章", "scenes": []}]}, output_language="en-US",
        )


def test_rule_structure_cannot_label_english_excerpts_as_chinese():
    with pytest.raises(ContractError, match="output_language zh-CN"):
        RuleBasedProjectStructureAnalyzer(output_language="zh-CN").analyze(
            project_id="project_test", title="资料", source_language="zh-CN",
            source_text="Chapter 1 The Hero's Sacrifice\n\n主角在出发前把信交给朋友。",
        )


@pytest.mark.parametrize("title", ["第1章", "第 1 章", "场景 1", "序章"])
def test_english_structure_rejects_chinese_numbered_headings(title):
    with pytest.raises(ContractError, match="output_language en-US"):
        validate_project_structure_output_language(
            outline={"chapters": [{"title": title, "scenes": []}]}, output_language="en-US",
        )


def test_edited_structure_non_text_summary_fails_as_contract_error():
    with pytest.raises(ContractError, match="must be text"):
        validate_project_structure_output_language(
            outline={"summary": 123, "chapters": []}, output_language="zh-CN",
        )


def _client(tmp_path):
    settings = StoryGraphSettings(tmp_path)
    settings.llm_api_key = ""
    settings.llm_base_url = ""
    client = TestClient(create_app(settings))
    project_id = client.post("/projects", json={"title": "测试小说", "language": "zh-CN"}).json()[
        "project_id"
    ]
    return client, settings, project_id


def _accepted_english_structure(client, project_id):
    outline = chinese_outline()
    outline["chapters"][0]["title"] = "Prologue"
    outline["chapters"][0]["scenes"][0]["title"] = "The Hero's Sacrifice"
    created = client.post(f"/projects/{project_id}/proposals", json={
        "artifact_type": "project_structure_draft", "title": "旧结构提案",
        "body_format": "structured_json", "body": json.dumps(outline, ensure_ascii=False),
    })
    assert created.status_code == 200
    proposal = created.json()
    accepted = client.post(f"/projects/{project_id}/proposals/{proposal['id']}/accept", json={
        "reviewer": "author", "expected_version": proposal["version"],
    })
    assert accepted.status_code == 200
    return accepted.json()


def test_first_apply_rechecks_body_language_without_changing_existing_project(tmp_path):
    client, settings, project_id = _client(tmp_path)
    proposal = _accepted_english_structure(client, project_id)
    graph_before = settings.graph_path.read_bytes()
    response = client.post(
        f"/projects/{project_id}/proposals/{proposal['id']}/apply/project-structure",
        json={"reviewer": "author", "expected_version": proposal["version"]},
    )
    assert response.status_code == 409
    assert "Prologue" not in response.text
    assert "The Hero's Sacrifice" not in response.text
    assert settings.graph_path.read_bytes() == graph_before
    assert client.get(f"/projects/{project_id}/outline").json()["chapters"] == []
    assert client.get(f"/projects/{project_id}/proposals/{proposal['id']}").json() == proposal


def test_first_apply_non_text_summary_returns_conflict_before_graph_writes(tmp_path):
    client, settings, project_id = _client(tmp_path)
    outline = chinese_outline()
    outline["summary"] = 123
    created = client.post(f"/projects/{project_id}/proposals", json={
        "artifact_type": "project_structure_draft", "title": "编辑过的结构",
        "body_format": "structured_json", "body": json.dumps(outline, ensure_ascii=False),
    })
    assert created.status_code == 200
    proposal = created.json()
    accepted = client.post(f"/projects/{project_id}/proposals/{proposal['id']}/accept", json={
        "reviewer": "author", "expected_version": proposal["version"],
    })
    assert accepted.status_code == 200
    graph_before = settings.graph_path.read_bytes()
    response = client.post(
        f"/projects/{project_id}/proposals/{proposal['id']}/apply/project-structure",
        json={"reviewer": "author", "expected_version": accepted.json()["version"]},
    )
    assert response.status_code == 409
    assert settings.graph_path.read_bytes() == graph_before


def test_already_applied_english_structure_remains_readable_and_retry_safe(tmp_path, monkeypatch):
    client, settings, project_id = _client(tmp_path)
    proposal = _accepted_english_structure(client, project_id)
    route = f"/projects/{project_id}/proposals/{proposal['id']}/apply/project-structure"
    request_body = {"reviewer": "author", "expected_version": proposal["version"]}
    # Construct a historical applied record as produced before this guard existed.
    with monkeypatch.context() as legacy:
        legacy.setattr("apps.api.main.validate_project_structure_output_language", lambda **kw: None)
        first = client.post(route, json=request_body)
    assert first.status_code == 200, first.text
    graph_before = settings.graph_path.read_bytes()
    second = client.post(route, json=request_body)
    assert second.status_code == 200, second.text
    assert second.json()["already_applied"] is True
    assert second.json()["proposal"]["version"] == first.json()["proposal"]["version"]
    assert second.json()["chapters"][0]["properties"]["title"] == "Prologue"
    assert settings.graph_path.read_bytes() == graph_before


def test_failed_generated_structure_never_saves_a_proposal(tmp_path, monkeypatch):
    client, settings, project_id = _client(tmp_path)
    client.put("/settings/agent", json={
        "llm_base_url": "https://example.test/v1", "llm_api_key": "synthetic-key",
        "llm_model": "synthetic-model",
    })
    outline = chinese_outline()
    outline["chapters"][0]["title"] = "Prologue"
    provider = CapturingProvider(outline)
    monkeypatch.setattr("apps.api.main.create_llm_provider", lambda settings: provider)
    graph_before = settings.graph_path.read_bytes()
    proposals_before = client.get(f"/projects/{project_id}/proposals").json()
    response = client.post(f"/projects/{project_id}/imports/structure-draft", json={
        "title": "测试资料", "text": "主角在出发前把信交给朋友。", "source_ref": "test:synthetic",
        "source_language": "zh-CN",
    })
    assert response.status_code == 409, response.text
    assert "Prologue" not in response.text
    assert len(provider.requests) == 1
    assert client.get(f"/projects/{project_id}/proposals").json() == proposals_before
    assert settings.graph_path.read_bytes() == graph_before
