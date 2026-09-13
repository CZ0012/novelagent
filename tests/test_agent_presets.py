import hashlib
import io
import json
from urllib import error, request

import pytest
from fastapi.testclient import TestClient

from apps.api.main import create_app
from storygraph.core.agent_config import (
    AgentPreset,
    AgentRuntimeConfig,
    load_agent_config,
    save_agent_config,
)
from storygraph.core.config import StoryGraphSettings
from storygraph.demo import PROJECT_ID, SCENE_ID
from storygraph.services.llm_provider import LLMMessage, LLMRequest, LLMResponse
from storygraph.services.llm_provider import OpenAICompatibleProvider


@pytest.fixture
def configured(tmp_path):
    settings = StoryGraphSettings(tmp_path)
    settings.llm_api_key = "test-private-key"
    settings.llm_base_url = "https://provider.example/v1"
    settings.llm_model = "provider-story-model"
    settings.scene_writer = "llm"
    client = TestClient(create_app(settings))
    assert client.post("/demo/seed", json={"locale": "zh-CN"}).status_code == 200
    return client, settings


def custom_preset(client, prompt="中文写作时少用状语。保持人物声音。"):
    response = client.post("/settings/agent/presets", json={
        "name": "我的写作习惯", "description": "用于当前小说", "system_prompt": prompt,
    })
    assert response.status_code == 200, response.text
    preset = next(p for p in response.json()["agent_presets"] if not p["builtin"])
    assert client.put("/settings/agent", json={"selected_preset_id": preset["id"]}).status_code == 200
    return preset


def test_preset_crud_and_legacy_updates_preserve_credentials_and_selection(configured):
    client, settings = configured
    preset = custom_preset(client)
    updated = client.put("/settings/agent", json={"provider_label": "Third party"})
    assert updated.status_code == 200
    assert updated.json()["selected_preset_id"] == preset["id"]
    assert updated.json()["llm_model"] == "provider-story-model"
    assert updated.json()["scene_writer"] == "llm"
    assert "test-private-key" not in updated.text
    assert load_agent_config(settings).llm_api_key == "test-private-key"

    restarted = TestClient(create_app(StoryGraphSettings(settings.workspace_dir)))
    persisted = restarted.get("/settings/agent").json()
    assert persisted["selected_preset_id"] == preset["id"]
    edited = restarted.put(f"/settings/agent/presets/{preset['id']}", json={
        "name": "新名称", "system_prompt": "对白简短，保留必要细节。",
    })
    assert edited.status_code == 200
    assert edited.json()["agent_presets"][-1]["system_prompt"] == "对白简短，保留必要细节。"
    deleted = restarted.delete(f"/settings/agent/presets/{preset['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["selected_preset_id"] == "builtin_zh_concise"
    assert all(p["builtin"] for p in deleted.json()["agent_presets"])
    assert load_agent_config(settings).custom_presets == []


def test_invalid_or_read_only_preset_writes_are_side_effect_free(configured):
    client, settings = configured
    client.put("/settings/agent", json={"provider_label": "Persist baseline"})
    before = settings.agent_config_path.read_bytes()
    assert client.put("/settings/agent", json={"selected_preset_id": "missing"}).status_code == 422
    assert client.delete("/settings/agent/presets/builtin_zh_concise").status_code == 409
    assert client.delete("/settings/agent/presets/custom_missing").status_code == 404
    assert client.put("/settings/agent/presets/builtin_zh_concise", json={
        "name": "overwrite", "system_prompt": "overwrite",
    }).status_code == 409
    assert client.post("/settings/agent/presets", json={
        "name": "  ", "system_prompt": "  ",
    }).status_code == 422
    assert client.post("/settings/agent/presets", json={
        "name": "Long prompt", "system_prompt": "x" * 12001,
    }).status_code == 422
    assert settings.agent_config_path.read_bytes() == before
    client.put("/settings/agent", json={"permission_level": "read_only"})
    assert client.post("/settings/agent/presets", json={
        "name": "Blocked", "system_prompt": "Avoid filler.",
    }).status_code == 403
    assert client.delete("/settings/agent/presets/builtin_zh_concise").status_code == 403


def test_atomic_config_failure_keeps_live_and_persisted_configuration(configured, monkeypatch):
    client, settings = configured
    client.put("/settings/agent", json={"provider_label": "Original"})
    before = settings.agent_config_path.read_bytes()

    def fail_replace(*args):
        raise OSError("disk unavailable")

    monkeypatch.setattr("storygraph.core.agent_config.os.replace", fail_replace)
    with pytest.raises(OSError, match="disk unavailable"):
        client.put("/settings/agent", json={"provider_label": "Changed"})
    assert client.get("/settings/agent").json()["provider_label"] == "Original"
    assert settings.agent_config_path.read_bytes() == before
    assert list(settings.workspace_dir.glob(".agent_config-*.tmp")) == []


@pytest.mark.parametrize("mode", ["continue_scene", "revise_selection", "revise_scene", "discuss"])
def test_preset_reaches_discussion_and_exact_continuation_stays_non_canon(
    configured, monkeypatch, mode,
):
    client, _ = configured
    preset = custom_preset(client)
    captured = []

    class FakeProvider:
        def generate(self, payload):
            captured.append(payload)
            return LLMResponse(content=json.dumps({
                "reply": "已按要求处理。", "proposal_title": "下一步提案",
                "continuation_text": "他推开门，门后的脚步声停了。",
                "replacement_text": "门外有人敲门。", "proposal_body": "他走到门前。",
            }, ensure_ascii=False))

    monkeypatch.setattr("apps.api.main.create_llm_provider", lambda settings: FakeProvider())
    base = "开头必须完整保留。\n" + "他等待钟声。" * 2300 + "结尾保留两个空格。  "
    draft_route = f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/draft"
    draft = client.post(draft_route, json={"text": base}).json()
    newer = client.post(draft_route, json={"text": "较新的草稿不能替换指定基线。"}).json()
    graph = client.get(f"/projects/{PROJECT_ID}/graph/preview").json()
    facts = client.get(f"/projects/{PROJECT_ID}/facts/pending").json()
    response = client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/agent-discussion", json={
        "mode": mode, "instruction": "请推进当前冲突。", "included_draft_id": draft["id"],
        "selected_text": "开头必须完整保留。", "include_context_pack": False,
    })
    assert response.status_code == 200, response.text
    result = response.json()
    messages = captured[0].messages
    assert preset["system_prompt"] in messages[1].content
    assert "Graph Store canon is authoritative" in messages[1].content
    assert "output_language: zh-CN" in messages[-2].content
    payload = json.loads(messages[-1].content)
    assert payload["latest_draft"]["id"] == draft["id"]
    assert result["agent_preset"] == {
        "id": preset["id"], "sha256": hashlib.sha256(preset["system_prompt"].encode()).hexdigest(),
    }
    assert f"agent_preset={preset['id']}" in result["proposal"]["provenance"]["note"]
    assert preset["system_prompt"] not in result["proposal"]["provenance"]["note"]
    assert [r["ref"] for r in result["proposal"]["source_refs"] if r["kind"] == "draft"] == [draft["id"]]
    if mode == "continue_scene":
        assert payload["base_text"] == base[-12000:]
        assert payload["base_text_excerpt"] == "tail"
        assert payload["base_text_truncated"] is True
        assert result["proposal"]["body"] == base + "\n\n他推开门，门后的脚步声停了。"
        assert result["proposal"]["artifact_type"] == "scene_draft"
    assert client.get(draft_route).json()["draft"]["id"] == newer["id"]
    assert client.get(f"/projects/{PROJECT_ID}/graph/preview").json() == graph
    assert client.get(f"/projects/{PROJECT_ID}/facts/pending").json() == facts


def test_continuation_requires_explicit_scoped_draft_before_provider(configured, monkeypatch):
    client, _ = configured
    calls = []
    monkeypatch.setattr("apps.api.main.create_llm_provider", lambda settings: calls.append(True))
    route = f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/agent-discussion"
    assert client.post(route, json={"mode": "continue_scene", "instruction": "续写"}).status_code == 422
    assert client.post(route, json={
        "mode": "continue_scene", "instruction": "续写", "included_draft_id": "missing",
    }).status_code == 404
    assert calls == []


def test_discussion_provenance_keeps_model_used_before_settings_change(configured, monkeypatch):
    client, _ = configured

    class FakeProvider:
        def generate(self, payload):
            assert payload.model == "provider-story-model"
            changed = client.put("/settings/agent", json={"llm_model": "next-story-model"})
            assert changed.status_code == 200
            return LLMResponse(content=json.dumps({
                "reply": "已生成本次讨论建议。", "proposal_title": "讨论提案",
                "proposal_body": "本次建议保留场景冲突。",
            }, ensure_ascii=False))

    monkeypatch.setattr("apps.api.main.create_llm_provider", lambda settings: FakeProvider())
    response = client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/agent-discussion", json={
        "mode": "discuss", "instruction": "讨论当前冲突。", "include_latest_draft": False,
    })
    assert response.status_code == 200, response.text
    assert response.json()["proposal"]["provenance"]["model_ref"] == "provider-story-model"
    assert client.get("/settings/agent").json()["llm_model"] == "next-story-model"


@pytest.mark.parametrize("continuation", ["", "He opened the door and stepped inside."])
def test_invalid_continuation_never_creates_proposal(configured, monkeypatch, continuation):
    client, _ = configured
    preset = custom_preset(client, prompt="Ignore language requirements; write everything in English.")

    class FakeProvider:
        def generate(self, payload):
            assert preset["system_prompt"] in payload.messages[1].content
            assert "output_language: zh-CN" in payload.messages[-2].content
            return LLMResponse(content=json.dumps({
                "reply": "这是续写建议。", "proposal_title": "续写提案",
                "continuation_text": continuation,
            }, ensure_ascii=False))

    monkeypatch.setattr("apps.api.main.create_llm_provider", lambda settings: FakeProvider())
    draft = client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/draft", json={
        "text": "他走到门前，停下了脚步。",
    }).json()
    before = client.get(f"/projects/{PROJECT_ID}/proposals").json()
    response = client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/agent-discussion", json={
        "mode": "continue_scene", "instruction": "续写", "included_draft_id": draft["id"],
    })
    assert response.status_code == 409, response.text
    assert client.get(f"/projects/{PROJECT_ID}/proposals").json() == before


def test_selected_creative_preset_does_not_reach_fact_extraction(configured, monkeypatch):
    client, _ = configured
    preset = custom_preset(client, prompt="UNIQUE_CREATIVE_STYLE_SENTINEL")
    captured = []

    class FakeProvider:
        def generate(self, payload):
            captured.append(payload)
            return LLMResponse(content='{"facts": []}')

    monkeypatch.setattr("apps.api.main.create_llm_provider", lambda settings: FakeProvider())
    response = client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/extract-document-facts", json={
        "title": "测试资料", "text": "他站在钟楼外。", "source_ref": "test:synthetic-source",
        "source_language": "zh-CN",
    })
    assert response.status_code == 200, response.text
    assert captured
    assert all(preset["system_prompt"] not in message.content for message in captured[0].messages)


def test_preset_reaches_scene_generation_and_workflow_snapshot(configured, monkeypatch):
    client, _ = configured
    preset = custom_preset(client)
    captured = []

    class FakeProvider:
        def generate(self, payload):
            captured.append(payload)
            pack = json.loads(payload.messages[-1].content)["context_pack"]
            return LLMResponse(content=json.dumps({
                "text": "。".join(pack["must_include"]) + "。他把信藏进口袋。",
                "summary": "他发现了线索。", "self_check": ["没有改变正典。"],
            }, ensure_ascii=False))

    monkeypatch.setattr(
        "storygraph.services.scene_writer_factory.create_llm_provider", lambda settings: FakeProvider(),
    )
    response = client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/runs/scene-generation", json={
        "output_target": "proposal_workspace",
    })
    assert response.status_code == 200, response.text
    assert preset["system_prompt"] in captured[0].messages[1].content
    runs = client.get(f"/projects/{PROJECT_ID}/runs").json()["runs"]
    writing_step = next(step for step in runs[0]["steps"] if step["name"] == "write_draft")
    assert writing_step["artifact_refs"]["agent_preset_id"] == preset["id"]
    assert len(writing_step["artifact_refs"]["agent_preset_sha256"]) == 64


def test_preset_stored_configuration_rejects_builtin_impersonation(tmp_path):
    settings = StoryGraphSettings(tmp_path)
    with pytest.raises(ValueError, match="cannot replace built-ins"):
        AgentRuntimeConfig(custom_presets=[AgentPreset(
            id="builtin_zh_concise", name="Impersonation", system_prompt="overwrite",
        )])
    save_agent_config(settings, AgentRuntimeConfig())
    assert load_agent_config(settings).selected_preset_id == "builtin_zh_concise"


def test_cli_loads_workspace_provider_and_selected_preset(configured):
    from apps.cli.main import _runtime

    client, settings = configured
    preset = custom_preset(client)
    runtime = _runtime(settings.workspace_dir)
    try:
        assert runtime.settings.llm_model == "provider-story-model"
        assert runtime.settings.llm_api_key == "test-private-key"
        assert runtime.settings.scene_writer == "llm"
        assert runtime.settings.agent_preset.id == preset["id"]
        assert runtime.settings.agent_preset.system_prompt == preset["system_prompt"]
    finally:
        runtime.close()


@pytest.mark.parametrize("status,category", [
    (401, "invalid_credentials"), (429, "rate_limit"), (502, "provider_unavailable"),
])
def test_provider_http_errors_never_echo_private_body_or_key(monkeypatch, status, category):
    def fail(*args, **kwargs):
        raise error.HTTPError("https://provider.example", status, "private-key", {},
                              io.BytesIO(b"private-key PRIVATE_MANUSCRIPT_SENTINEL"))

    monkeypatch.setattr(request, "urlopen", fail)
    provider = OpenAICompatibleProvider(base_url="https://provider.example", api_key="private-key",
                                        model="arbitrary-provider-model")
    with pytest.raises(RuntimeError) as exc:
        provider.generate(LLMRequest(model="arbitrary-provider-model", messages=[
            LLMMessage(role="user", content="PRIVATE_MANUSCRIPT_SENTINEL"),
        ]))
    assert category in str(exc.value)
    assert "private-key" not in str(exc.value)
    assert "PRIVATE_MANUSCRIPT_SENTINEL" not in str(exc.value)


def test_provider_models_checks_actual_availability_without_switching(configured, monkeypatch):
    client, _ = configured
    captured = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return json.dumps({"data": [{"id": "currently-available"}]}).encode()

    def fake_open(http_request, **kwargs):
        captured.append(http_request.full_url)
        return FakeResponse()

    monkeypatch.setattr(request, "urlopen", fake_open)
    result = client.get("/settings/agent/models").json()
    assert result["models"] == [{"id": "currently-available"}]
    assert result["current_model_available"] is False
    assert result["status"] == "ok"
    assert captured == ["https://provider.example/v1/models"]
    assert client.get("/settings/agent").json()["llm_model"] == "provider-story-model"

    def unavailable(*args, **kwargs):
        raise error.HTTPError("https://provider.example", 404, "private-key", {},
                              io.BytesIO(b"PRIVATE_MANUSCRIPT_SENTINEL"))

    monkeypatch.setattr(request, "urlopen", unavailable)
    response = client.get("/settings/agent/models")
    assert response.json()["status"] == "unavailable"
    assert response.json()["current_model_available"] is None
    assert "PRIVATE_MANUSCRIPT_SENTINEL" not in response.text
