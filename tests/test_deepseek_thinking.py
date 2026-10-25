"""Explicit official-provider thinking control, with no actual network access."""

import json
from urllib import request

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from apps.api.main import create_app
from storygraph.core.agent_config import (
    AgentRuntimeConfig, AgentRuntimeConfigUpdate, ModelExecution, apply_agent_config,
    config_response, load_agent_config, save_agent_config, settings_for_task, update_agent_config,
)
from storygraph.core.config import StoryGraphSettings
from storygraph.services.llm_provider import (
    AnthropicMessagesProvider, LLMMessage, LLMRequest, OpenAICompatibleProvider, ResponsesProvider,
)
from storygraph.services.scene_writer_factory import create_llm_provider


class Reply:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self):
        return json.dumps({"choices": [{"finish_reason": "stop", "message": {
            "content": '{"facts":[]}', "reasoning_content": "PRIVATE_THINKING",
        }}]}).encode()


@pytest.mark.parametrize("mode", ["provider_default", "enabled", "disabled"])
def test_official_chat_sends_only_explicit_thinking_mode(monkeypatch, mode):
    calls = []
    monkeypatch.setattr(request, "urlopen", lambda req, timeout: calls.append(req) or Reply())
    provider = OpenAICompatibleProvider(base_url="https://api.deepseek.com/v1", api_key="synthetic-key",
                                        model="deepseek-flash", thinking_mode=mode)
    result = provider.generate(LLMRequest(model="deepseek-flash", max_tokens=1234,
                                         messages=[LLMMessage("user", "JSON")]))
    body = json.loads(calls[0].data)
    assert len(calls) == 1 and body["model"] == "deepseek-flash" and body["max_tokens"] == 1234
    if mode == "provider_default":
        assert "thinking" not in body
    else:
        assert body["thinking"] == {"type": mode}
    assert "PRIVATE_THINKING" not in result.content and result.raw == {}


@pytest.mark.parametrize("url", [
    "https://api.deepseek.com", "https://api.deepseek.com/v1",
    "https://api.deepseek.com/chat/completions", "https://api.deepseek.com:443/v1",
])
def test_official_https_forms_accept_override_without_model_name_guessing(url):
    provider = OpenAICompatibleProvider(base_url=url, api_key="synthetic", model="exact-custom-model",
                                        thinking_mode="disabled")
    assert provider.model == "exact-custom-model"


@pytest.mark.parametrize("url", [
    "https://gateway.example/v1", "https://api.deepseek.com.evil.invalid",
    "http://api.deepseek.com", "https://api.deepseek.com:444/v1",
    "https://localhost", "https://api.deepseek.com@evil.invalid",
])
@pytest.mark.parametrize("mode", ["enabled", "disabled"])
def test_incompatible_hosts_reject_before_any_request(monkeypatch, url, mode):
    monkeypatch.setattr(request, "urlopen", lambda *_a, **_k: pytest.fail("network forbidden"))
    with pytest.raises(ValueError):
        OpenAICompatibleProvider(base_url=url, api_key="synthetic", model="deepseek-flash",
                                 thinking_mode=mode)


@pytest.mark.parametrize("cls", [ResponsesProvider, AnthropicMessagesProvider])
def test_explicit_mode_rejects_other_protocols_even_on_official_host(monkeypatch, cls):
    monkeypatch.setattr(request, "urlopen", lambda *_a, **_k: pytest.fail("network forbidden"))
    with pytest.raises(ValueError, match="official DeepSeek"):
        cls(base_url="https://api.deepseek.com", api_key="synthetic", model="deepseek-flash",
            thinking_mode="disabled")


def test_legacy_config_and_third_party_gateway_keep_provider_default(tmp_path):
    settings = StoryGraphSettings(tmp_path)
    legacy = {"llm_base_url": "https://gateway.example/v1", "llm_model": "legacy-model",
              "llm_api_key": "synthetic"}
    settings.agent_config_path.write_text(json.dumps(legacy), encoding="utf-8")
    config = load_agent_config(settings)
    assert config.llm_thinking_mode == "provider_default"
    apply_agent_config(settings, config)
    provider = create_llm_provider(settings_for_task(settings, "planning"))
    assert provider.thinking_mode == "provider_default"


def test_task_resolution_freezes_default_and_named_modes_and_preserves_keys(tmp_path):
    settings = StoryGraphSettings(tmp_path)
    config = AgentRuntimeConfig.model_validate({
        "llm_base_url": "https://api.deepseek.com", "llm_model": "default-exact",
        "llm_api_key": "default-synthetic", "llm_thinking_mode": "disabled",
        "connection_profiles": [{"id": "deep", "name": "思考连接",
            "base_url": "https://api.deepseek.com/v1", "model": "profile-exact",
            "api_key": "profile-synthetic", "thinking_mode": "enabled"}],
        "task_assignments": {"continuity": "deep"},
    })
    apply_agent_config(settings, config)
    planning = settings_for_task(settings, "planning")
    continuity = settings_for_task(settings, "continuity")
    assert planning.llm_thinking_mode == "disabled" and continuity.llm_thinking_mode == "enabled"
    assert planning.model_execution["thinking_mode"] == "disabled"
    assert continuity.model_execution["thinking_mode"] == "enabled"
    assert create_llm_provider(continuity).thinking_mode == "enabled"
    updated = update_agent_config(config, AgentRuntimeConfigUpdate(llm_thinking_mode="enabled"))
    assert updated.llm_api_key == "default-synthetic"
    apply_agent_config(settings, updated)
    assert planning.llm_thinking_mode == "disabled"
    save_agent_config(settings, updated)
    assert load_agent_config(settings).llm_thinking_mode == "enabled"
    response = config_response(updated).model_dump()
    assert response["llm_thinking_mode"] == "enabled"
    assert response["connection_profiles"][0]["thinking_mode"] == "enabled"
    assert "api_key" not in response["connection_profiles"][0]
    profile_update = AgentRuntimeConfigUpdate.model_validate({"connection_profiles": [{
        "id": "deep", "name": "思考连接改名", "base_url": "https://api.deepseek.com/v1",
        "model": "profile-exact",
    }]})
    retained = update_agent_config(updated, profile_update)
    assert retained.connection_profiles[0].thinking_mode == "enabled"
    assert retained.connection_profiles[0].api_key == "profile-synthetic"


@pytest.mark.parametrize("payload", [
    {"llm_thinking_mode": "unsupported"},
    {"llm_thinking_mode": "disabled", "llm_base_url": "https://gateway.example"},
    {"llm_thinking_mode": "disabled", "llm_base_url": "https://api.deepseek.com", "llm_protocol": "responses"},
    {"connection_profiles": [{"id": "bad", "name": "Bad", "base_url": "https://gateway.example",
                               "thinking_mode": "disabled"}]},
])
def test_saved_config_rejects_incompatible_explicit_options(payload):
    with pytest.raises(ValidationError):
        AgentRuntimeConfig.model_validate(payload)


def test_api_config_roundtrip_and_failed_protocol_change_keep_prior_config(tmp_path):
    client = TestClient(create_app(StoryGraphSettings(tmp_path)))
    result = client.put("/settings/agent", json={
        "llm_base_url": "https://api.deepseek.com", "llm_model": "deepseek-flash",
        "llm_api_key": "synthetic-test-key", "llm_thinking_mode": "disabled",
    })
    assert result.status_code == 200, result.text
    assert result.json()["llm_thinking_mode"] == "disabled"
    assert "synthetic-test-key" not in result.text
    invalid = client.put("/settings/agent", json={"llm_protocol": "responses"})
    assert invalid.status_code == 422
    assert client.get("/settings/agent").json()["llm_protocol"] == "chat_completions"


def test_old_model_history_does_not_invent_thinking_choice():
    historical = ModelExecution(profile_id="default", profile_name="old", protocol="chat_completions",
                                model="old", task="writing")
    assert historical.thinking_mode is None
