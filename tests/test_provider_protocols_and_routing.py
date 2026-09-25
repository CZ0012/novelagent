"""Protocol wire semantics, rejection boundaries and request-frozen role routing."""
import io
import json
from urllib import error, request

import pytest
from fastapi.testclient import TestClient

from apps.api.main import create_app
from storygraph.core.agent_config import (
    AgentRuntimeConfig, AgentRuntimeConfigUpdate, apply_agent_config, config_response,
    load_agent_config, save_agent_config, settings_for_task, update_agent_config,
)
from storygraph.core.config import StoryGraphSettings
from storygraph.demo import PROJECT_ID, SCENE_ID
from storygraph.services.llm_provider import (
    AnthropicMessagesProvider, LLMMessage, LLMRequest, LLMResponse,
    OpenAICompatibleProvider, ResponsesProvider,
)
from storygraph.services.json_output import unwrap_json_fence
from storygraph.services.scene_writer_factory import create_llm_provider, create_scene_writer


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return None
    def read(self):
        return json.dumps(self.payload).encode()


def provider(cls, **kwargs):
    return cls(base_url="https://gateway.example/v1", api_key="private-secret-key",
               model="claude-opus-4-6", **kwargs)


def llm_request():
    return LLMRequest(model="claude-opus-4-6", max_tokens=512, messages=[
        LLMMessage("system", "contract"), LLMMessage("system", "preferences"),
        LLMMessage("system", "project language"), LLMMessage("user", "JSON please"),
    ])


@pytest.mark.parametrize("cls,endpoint,payload", [
    (ResponsesProvider, "responses", {"status": "completed", "model": "reported-model", "output": [
        {"type": "reasoning", "summary": [{"text": "hidden"}]},
        {"type": "message", "role": "assistant", "status": "completed", "content": [
            {"type": "output_text", "text": '{"ok":'}, {"type": "output_text", "text": 'true}'}]},
    ]}),
    (AnthropicMessagesProvider, "messages", {"type": "message", "role": "assistant",
        "stop_reason": "end_turn", "model": "reported-model", "content": [
            {"type": "thinking", "thinking": "hidden"}, {"type": "text", "text": '{"ok":'},
            {"type": "text", "text": 'true}'}]}),
])
def test_protocol_wire_and_safe_output(monkeypatch, cls, endpoint, payload):
    captured = []
    def fake(req, timeout):
        captured.append((req, timeout))
        return FakeResponse(payload)
    monkeypatch.setattr(request, "urlopen", fake)
    result = provider(cls).generate(llm_request())
    assert result.content == '{"ok":true}'
    assert result.raw == {"model": "reported-model"}
    assert len(captured) == 1
    req, _ = captured[0]
    body = json.loads(req.data)
    assert req.full_url == f"https://gateway.example/v1/{endpoint}"
    assert body["model"] == "claude-opus-4-6"
    assert "response_format" not in body
    if endpoint == "responses":
        assert body["store"] is False
        assert body["max_output_tokens"] == 512
        assert body["instructions"] == "contract\n\npreferences\n\nproject language"
        assert body["input"] == [{"role": "user", "content": "JSON please"}]
        assert body["text"] == {"format": {"type": "json_object"}}
        assert req.get_header("Authorization") == "Bearer private-secret-key"
    else:
        assert body["max_tokens"] == 512
        assert body["system"] == "contract\n\npreferences\n\nproject language"
        assert body["messages"] == [{"role": "user", "content": "JSON please"}]
        assert req.get_header("X-api-key") == "private-secret-key"
        assert req.get_header("Anthropic-version") == "2023-06-01"
        assert req.get_header("Authorization") is None
        assert "text" not in body


@pytest.mark.parametrize("payload", [
    {"status": "incomplete", "incomplete_details": {"reason": "private-secret-key"}},
    {"status": "failed", "error": {"message": "private manuscript"}},
    {"status": "queued", "output": []},
    {"status": "completed", "output": [{"type": "function_call", "arguments": "private manuscript"}]},
    {"status": "completed", "output": [{"type": "message", "role": "assistant", "content": [{"type": "refusal", "refusal": "private manuscript"}]}]},
    {"status": "completed", "output": [{"type": "reasoning"}]},
    {"status": "completed", "output": []},
    [],
])
def test_responses_rejects_partial_refusal_tools_and_empty_once(monkeypatch, payload):
    calls = []
    monkeypatch.setattr(request, "urlopen", lambda req, timeout: calls.append(req) or FakeResponse(payload))
    with pytest.raises(RuntimeError) as caught:
        provider(ResponsesProvider).generate(llm_request())
    assert len(calls) == 1
    assert "private" not in str(caught.value)


@pytest.mark.parametrize("stop_reason", ["max_tokens", "tool_use", "pause_turn", "refusal", None])
def test_anthropic_rejects_nonfinal_stop_reasons(monkeypatch, stop_reason):
    monkeypatch.setattr(request, "urlopen", lambda *_a, **_k: FakeResponse({
        "type": "message", "role": "assistant", "stop_reason": stop_reason,
        "content": [{"type": "text", "text": "private manuscript"}],
    }))
    with pytest.raises(RuntimeError, match="incomplete_response"):
        provider(AnthropicMessagesProvider).generate(llm_request())


@pytest.mark.parametrize("cls", [OpenAICompatibleProvider, ResponsesProvider, AnthropicMessagesProvider])
def test_http_failures_do_not_echo_body_reason_or_key_and_do_not_retry(monkeypatch, cls):
    calls = []
    def fail(req, timeout):
        calls.append(req)
        raise error.HTTPError(req.full_url, 401, "private-secret-key", {}, io.BytesIO(b"private manuscript"))
    monkeypatch.setattr(request, "urlopen", fail)
    with pytest.raises(RuntimeError, match="invalid_credentials") as caught:
        provider(cls).generate(llm_request())
    assert "private" not in str(caught.value)
    assert len(calls) == 1


def test_responses_without_json_mode_does_not_send_text_format(monkeypatch):
    captured = []
    monkeypatch.setattr(request, "urlopen", lambda req, timeout: captured.append(json.loads(req.data)) or FakeResponse({
        "status": "completed", "output": [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "ok"}]}],
    }))
    provider(ResponsesProvider, json_mode=False).generate(llm_request())
    assert "text" not in captured[0]


@pytest.mark.parametrize("bad", ['```json\n{}', '```json\n{}\n``` explanation', '```json\n{}\n```\n```json\n{}\n```'])
def test_json_envelope_rejects_incomplete_or_extra_material(bad):
    with pytest.raises(ValueError):
        unwrap_json_fence(bad)


def test_json_envelope_preserves_valid_json_and_whole_fence():
    assert unwrap_json_fence('```json\n{"text":"夜色"}\n```') == '{"text":"夜色"}'
    assert unwrap_json_fence(' {"text":"night"} ') == '{"text":"night"}'


def routed_config():
    return AgentRuntimeConfig(scene_writer="llm", llm_base_url="https://default.example/v1",
        llm_api_key="default-secret", llm_model="default-model", connection_profiles=[
            {"id": role, "name": role, "protocol": "responses" if role != "extraction" else "anthropic_messages",
             "base_url": f"https://{role}.example/v1", "model": f"{role}-model", "api_key": f"{role}-secret"}
            for role in ("planning", "writing", "revision", "discussion", "extraction")],
        task_assignments={role: role for role in ("planning", "writing", "revision", "discussion", "extraction")})


def test_legacy_load_and_profile_secret_preservation_are_atomic(tmp_path):
    settings = StoryGraphSettings(tmp_path)
    settings.agent_config_path.write_text(json.dumps({"llm_model": "legacy", "llm_api_key": "legacy-secret"}))
    config = load_agent_config(settings)
    assert config.llm_protocol == "chat_completions"
    assert all(item.profile_id == "default" for item in config_response(config).resolved_tasks.values())
    config = routed_config()
    update = AgentRuntimeConfigUpdate(connection_profiles=[{
        **p.model_dump(exclude={"api_key"}), "api_key": "",
    } for p in config.connection_profiles], task_assignments={"discussion": None})
    updated = update_agent_config(config, update)
    assert updated.connection_profiles[0].api_key == "planning-secret"
    assert updated.task_assignments.writing == "writing"
    assert updated.task_assignments.discussion is None
    assert updated.llm_api_key == "default-secret"
    public = config_response(updated).model_dump_json()
    assert all(key not in public for key in ["default-secret", "planning-secret", "writing-secret"])
    save_agent_config(settings, updated)
    assert load_agent_config(settings) == updated
    with pytest.raises(ValueError):
        update_agent_config(updated, AgentRuntimeConfigUpdate(connection_profiles=[]))
    assert load_agent_config(settings) == updated
    with pytest.raises(ValueError):
        AgentRuntimeConfig(connection_profiles=[{"id": "default", "name": "bad"}])


def test_each_role_resolves_a_frozen_configuration_and_cli_loads_saved_routing(tmp_path):
    settings = StoryGraphSettings(tmp_path)
    config = routed_config()
    save_agent_config(settings, config)
    apply_agent_config(settings, config)
    snapshots = {task: settings_for_task(settings, task) for task in config.task_assignments.model_dump()}
    apply_agent_config(settings, AgentRuntimeConfig(llm_model="changed", selected_preset_id="builtin_balanced"))
    for task, snapshot in snapshots.items():
        transport = create_llm_provider(snapshot)
        assert transport.model == f"{task}-model"
        assert transport.api_key == f"{task}-secret"
        assert snapshot.model_execution["task"] == task
        assert snapshot.agent_preset.id == "builtin_zh_concise"
    cli_writer = create_scene_writer(StoryGraphSettings(tmp_path), None)
    assert cli_writer.model == "writing-model"
    assert cli_writer.model_execution["task"] == "writing"
    revision_writer = create_scene_writer(snapshots["revision"], None)
    assert revision_writer.model == "revision-model"


def test_models_listing_uses_selected_profile_and_permissions(tmp_path, monkeypatch):
    client = TestClient(create_app(StoryGraphSettings(tmp_path)))
    assert client.put('/settings/agent', json=routed_config().model_dump(exclude={"custom_presets"})).status_code == 200
    captured = []
    monkeypatch.setattr(request, "urlopen", lambda req, timeout: captured.append(req) or FakeResponse({"data": [{"id": "extraction-model"}]}))
    response = client.get('/settings/agent/models?profile_id=extraction')
    assert response.status_code == 200
    assert response.json()["current_model_available"]
    assert captured[0].full_url == "https://extraction.example/v1/models"
    assert captured[0].get_header('X-api-key') == 'extraction-secret'
    assert client.get('/settings/agent/models?profile_id=unknown').status_code == 404
    client.put('/settings/agent', json={"permission_level": "read_only"})
    assert client.get('/settings/agent/models?profile_id=extraction').status_code == 403
    assert len(captured) == 1


@pytest.mark.parametrize('mode,role', [("discuss", "discussion"), ("revise_scene", "revision"), ("revise_selection", "revision"), ("continue_scene", "writing")])
def test_agent_routes_and_persists_actual_snapshot_during_settings_change(tmp_path, monkeypatch, mode, role):
    client = TestClient(create_app(StoryGraphSettings(tmp_path)))
    client.post('/demo/seed')
    client.put('/settings/agent', json=routed_config().model_dump(exclude={"custom_presets"}))
    baseline = client.post(f'/projects/{PROJECT_ID}/scenes/{SCENE_ID}/draft', json={"text": "门没有打开。"}).json()
    captured = []
    class FakeProvider:
        def generate(self, req):
            captured.append(req.model)
            client.put('/settings/agent', json={"llm_model": "changed", "task_assignments": {role: None}})
            return LLMResponse(content=json.dumps({"reply": "让动作更清楚。", "proposal_title": "新的动作",
                "proposal_body": "门打开了。", "replacement_text": "门打开了。", "continuation_text": "有人走进屋里。"}))
    monkeypatch.setattr('apps.api.main.create_llm_provider', lambda settings: FakeProvider())
    response = client.post(f'/projects/{PROJECT_ID}/scenes/{SCENE_ID}/agent-discussion', json={
        "mode": mode, "instruction": "Improve the action.", "include_context_pack": False,
        "include_latest_draft": True, "included_draft_id": baseline['id'],
        **({"selected_text": "门没有打开。", "selected_start": 0, "selected_end": 6} if mode == 'revise_selection' else {}),
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert captured == [f"{role}-model"]
    assert body['model_execution']['model'] == f"{role}-model"
    assert body['proposal']['provenance']['model_execution'] == body['model_execution']
    proposal = body['proposal']
    submitted = client.post(f"/projects/{PROJECT_ID}/proposals/{proposal['id']}/submit-review", json={"actor": "author", "expected_version": 1})
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()['provenance']['model_execution'] == body['model_execution']

@pytest.mark.parametrize("cls", [OpenAICompatibleProvider, ResponsesProvider, AnthropicMessagesProvider])
def test_invalid_header_diagnostics_never_echo_secrets(monkeypatch, cls):
    def invalid(*args, **kwargs):
        raise ValueError("Invalid header value private-secret-key")
    monkeypatch.setattr(request, "urlopen", invalid)
    with pytest.raises(RuntimeError, match="connection_error") as caught:
        provider(cls).generate(llm_request())
    assert "private-secret-key" not in str(caught.value)


def test_profile_clear_and_referenced_delete_validation_do_not_leak(tmp_path):
    client = TestClient(create_app(StoryGraphSettings(tmp_path)))
    config = routed_config()
    assert client.put('/settings/agent', json=config.model_dump(exclude={"custom_presets"})).status_code == 200
    failure = client.put('/settings/agent', json={"connection_profiles": [], "llm_api_key": "new-private-secret"})
    assert failure.status_code == 422
    assert "new-private-secret" not in failure.text
    unchanged = load_agent_config(StoryGraphSettings(tmp_path))
    assert unchanged.llm_api_key == "default-secret"
    changed = client.put('/settings/agent', json={"connection_profiles": [{
        **p.model_dump(exclude={"api_key"}), "clear_api_key": p.id == "writing",
    } for p in config.connection_profiles], "llm_api_key": ""})
    assert changed.status_code == 200
    saved = load_agent_config(StoryGraphSettings(tmp_path))
    assert saved.llm_api_key == "default-secret"
    assert next(p for p in saved.connection_profiles if p.id == "writing").api_key == ""
    assert next(p for p in saved.connection_profiles if p.id == "extraction").api_key == "extraction-secret"

@pytest.mark.parametrize('cls', [OpenAICompatibleProvider, ResponsesProvider, AnthropicMessagesProvider])
def test_malformed_url_is_sanitized_before_transport(cls):
    with pytest.raises(ValueError) as caught:
        cls(base_url='https://PRIVATE_REVIEW_SENTINEL＠example.test/v1', api_key='secret', model='model')
    assert 'PRIVATE_REVIEW_SENTINEL' not in str(caught.value)


def test_bad_provider_address_settings_validation_is_safe(tmp_path):
    client = TestClient(create_app(StoryGraphSettings(tmp_path)))
    response = client.put('/settings/agent', json={'llm_base_url': 'https://PRIVATE_REVIEW_SENTINEL＠example.test/v1'})
    assert response.status_code == 422
    assert 'PRIVATE_REVIEW_SENTINEL' not in response.text
    assert client.get('/settings/agent').json()['llm_base_url'] == ''


def test_rule_based_revision_clears_model_lineage_but_manual_revision_preserves_it(tmp_path, monkeypatch):
    client = TestClient(create_app(StoryGraphSettings(tmp_path)))
    client.post('/demo/seed')
    client.put('/settings/agent', json=routed_config().model_dump(exclude={'custom_presets'}))
    class FakeProvider:
        def generate(self, req):
            return LLMResponse(content=json.dumps({'reply': '新的动作。', 'proposal_title': '新的草稿', 'proposal_body': '木门打开了。'}))
    monkeypatch.setattr('apps.api.main.create_llm_provider', lambda settings: FakeProvider())
    baseline = client.post(f'/projects/{PROJECT_ID}/scenes/{SCENE_ID}/draft', json={'text': '木门关着。'}).json()
    generated = client.post(f'/projects/{PROJECT_ID}/scenes/{SCENE_ID}/agent-discussion', json={
        'mode': 'revise_scene', 'instruction': '改写。', 'base_text': '木门关着。',
        'include_latest_draft': True, 'included_draft_id': baseline['id'], 'include_context_pack': False,
    })
    assert generated.status_code == 200, generated.text
    proposal = generated.json()['proposal']
    pid = proposal['id']
    manual = client.post(f'/projects/{PROJECT_ID}/proposals/{pid}/revise', json={'body': '木门开了一道缝。', 'expected_version': 1})
    assert manual.status_code == 200, manual.text
    assert manual.json()['provenance']['model_execution'] == proposal['provenance']['model_execution']
    client.put('/settings/agent', json={'scene_writer': 'rule_based'})
    rewritten = client.post(f'/projects/{PROJECT_ID}/proposals/{pid}/revise', json={'expected_version': 2})
    assert rewritten.status_code == 200, rewritten.text
    assert rewritten.json()['provenance']['model_execution'] is None
    assert rewritten.json()['provenance']['model_ref'] is None


def test_invalid_saved_configuration_diagnostic_does_not_echo_credentials(tmp_path):
    settings = StoryGraphSettings(tmp_path)
    settings.agent_config_path.write_text(json.dumps({
        'llm_api_key': 'PRIVATE_REVIEW_SENTINEL',
        'task_assignments': {'writing': 'missing-profile'},
    }))
    with pytest.raises(ValueError) as caught:
        load_agent_config(settings)
    assert 'PRIVATE_REVIEW_SENTINEL' not in str(caught.value)


def test_invalid_model_json_has_stable_category_and_leaves_story_stores_unchanged(tmp_path, monkeypatch):
    client = TestClient(create_app(StoryGraphSettings(tmp_path)))
    client.post('/demo/seed')
    client.put('/settings/agent', json=routed_config().model_dump(exclude={'custom_presets'}))
    before = (tmp_path / 'graph.json').read_bytes()
    class FakeProvider:
        def generate(self, req):
            return LLMResponse(content='{"reply":"quote " unescaped"}')
    monkeypatch.setattr('apps.api.main.create_llm_provider', lambda settings: FakeProvider())
    response = client.post(f'/projects/{PROJECT_ID}/scenes/{SCENE_ID}/agent-discussion', json={
        'mode': 'discuss', 'instruction': '讨论。', 'include_context_pack': False, 'include_latest_draft': False,
    })
    assert response.status_code == 409
    assert response.json()['detail']['category'] == 'model_output_invalid'
    assert 'unescaped' not in response.text
    assert (tmp_path / 'graph.json').read_bytes() == before
    assert client.get(f'/projects/{PROJECT_ID}/scenes/{SCENE_ID}/draft/latest').status_code == 404


def test_explicit_unconfigured_planning_profile_never_silently_uses_rules(tmp_path, monkeypatch):
    client = TestClient(create_app(StoryGraphSettings(tmp_path)))
    project_id = client.post('/projects', json={'title': '结构测试', 'language': 'zh-CN'}).json()['project_id']
    client.put('/settings/agent', json={
        'llm_base_url': '', 'clear_api_key': True,
        'connection_profiles': [{'id': 'planner', 'name': '规划', 'protocol': 'responses',
                                 'base_url': 'https://planning.example/v1', 'model': 'planning-model'}],
        'task_assignments': {'planning': 'planner'},
    })
    calls = []
    monkeypatch.setattr('apps.api.main.create_llm_provider', lambda settings: calls.append(settings))
    payload = {'title': '原稿', 'text': '第一章 开始\n\n门打开了。', 'source_ref': 'import:synthetic',
               'source_language': 'zh-CN', 'max_chapters': 1, 'max_scenes_per_chapter': 1}
    blocked = client.post(f'/projects/{project_id}/imports/structure-draft', json=payload)
    assert blocked.status_code == 409
    assert blocked.json()['detail']['category'] == 'llm_not_configured'
    assert calls == []
    client.put('/settings/agent', json={'task_assignments': {'planning': None}})
    legacy = client.post(f'/projects/{project_id}/imports/structure-draft', json=payload)
    assert legacy.status_code == 200, legacy.text
    assert legacy.json()['model_execution'] is None
    assert calls == []
