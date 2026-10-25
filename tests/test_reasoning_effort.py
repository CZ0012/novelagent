"""Explicit reasoning controls and visible, bounded request budgets; no paid calls."""

import json
from types import SimpleNamespace
from urllib import request

import pytest
from pydantic import ValidationError

from storygraph.core.agent_config import (
    AgentRuntimeConfig, AgentRuntimeConfigUpdate, ModelExecution, apply_agent_config,
    config_response, load_agent_config, save_agent_config, settings_for_task, update_agent_config,
)
from storygraph.core.config import StoryGraphSettings
from storygraph.models.proposal import ProposalProvenance
from storygraph.services.generation_budget import completion_budget
from storygraph.services.llm_provider import (
    AnthropicMessagesProvider, LLMMessage, LLMRequest, OpenAICompatibleProvider, ResponsesProvider,
)
from storygraph.services.scene_writer_factory import create_llm_provider
from test_deepseek_thinking import Reply
from test_generation_budget import pack
from test_planning_run import setup as setup
from test_planning_run import create


@pytest.mark.parametrize("mode,effort,base,expected", [
    ("provider_default", None, 20000, 20000), ("disabled", None, 20000, 20000),
    ("provider_default", "low", 20000, 52768), ("enabled", "low", 8000, 40768),
    ("enabled", None, 20000, 52768), ("enabled", "high", 16000, 48768),
    ("provider_default", "max", 8000, 65536), ("enabled", "low", 64000, 65536),
])
def test_completion_budget_is_explicit_bounded_and_preserves_unspecified_behavior(mode, effort, base, expected):
    assert completion_budget(SimpleNamespace(thinking_mode=mode, reasoning_effort=effort), base) == expected
    assert completion_budget(object(), 4096) == 4096


@pytest.mark.parametrize("mode,effort", [("disabled", "low"), ("enabled", "none"), ("unknown", None)])
def test_invalid_budget_controls_fail_before_request(mode, effort):
    with pytest.raises(ValueError):
        completion_budget(SimpleNamespace(thinking_mode=mode, reasoning_effort=effort), 8000)


@pytest.mark.parametrize("mode,effort", [("provider_default", None), ("provider_default", "low"),
                                        ("enabled", "high"), ("enabled", "max")])
def test_wire_effort_is_optional_and_provider_never_inflates_callers_maximum(monkeypatch, mode, effort):
    calls = []
    monkeypatch.setattr(request, "urlopen", lambda req, timeout: calls.append(json.loads(req.data)) or Reply())
    provider = OpenAICompatibleProvider(base_url="https://api.deepseek.com/v1", api_key="synthetic",
        model="exact-model", thinking_mode=mode, reasoning_effort=effort)
    provider.generate(LLMRequest(model="exact-model", max_tokens=123, messages=[LLMMessage("user", "JSON")]))
    assert len(calls) == 1 and calls[0]["max_tokens"] == 123
    if effort is None:
        assert "reasoning_effort" not in calls[0]
    else:
        assert calls[0]["reasoning_effort"] == effort
    if mode == "provider_default":
        assert "thinking" not in calls[0]


@pytest.mark.parametrize("url,cls,mode", [
    ("https://gateway.example", OpenAICompatibleProvider, "provider_default"),
    ("https://api.deepseek.com.evil.invalid", OpenAICompatibleProvider, "enabled"),
    ("http://api.deepseek.com", OpenAICompatibleProvider, "provider_default"),
    ("https://api.deepseek.com", ResponsesProvider, "provider_default"),
    ("https://api.deepseek.com", AnthropicMessagesProvider, "enabled"),
    ("https://api.deepseek.com", OpenAICompatibleProvider, "disabled"),
])
def test_explicit_effort_rejects_host_protocol_or_disabled_conflicts_without_io(monkeypatch, url, cls, mode):
    monkeypatch.setattr(request, "urlopen", lambda *_a, **_k: pytest.fail("network forbidden"))
    with pytest.raises(ValueError):
        cls(base_url=url, api_key="synthetic", model="exact-model", thinking_mode=mode, reasoning_effort="low")


def test_default_and_named_effort_freeze_and_missing_updates_preserve(tmp_path):
    settings = StoryGraphSettings(tmp_path)
    current = AgentRuntimeConfig.model_validate({"llm_base_url": "https://api.deepseek.com", "llm_api_key": "default-synthetic",
        "llm_thinking_mode": "enabled", "llm_reasoning_effort": "low",
        "connection_profiles": [{"id": "review", "name": "审阅", "base_url": "https://api.deepseek.com",
            "api_key": "profile-synthetic", "model": "fixture-review-model", "thinking_mode": "enabled", "reasoning_effort": "high"}],
        "task_assignments": {"continuity": "review"}})
    apply_agent_config(settings, current)
    save_agent_config(settings, current)
    restored = load_agent_config(settings)
    assert restored.llm_reasoning_effort == "low" and restored.connection_profiles[0].reasoning_effort == "high"
    planning, continuity = settings_for_task(settings, "planning"), settings_for_task(settings, "continuity")
    assert planning.llm_reasoning_effort == "low" and continuity.llm_reasoning_effort == "high"
    assert planning.model_execution["reasoning_effort"] == "low"
    assert create_llm_provider(continuity).reasoning_effort == "high"
    updated = update_agent_config(current, AgentRuntimeConfigUpdate.model_validate({"llm_model": "new-model",
        "connection_profiles": [{"id": "review", "name": "新审阅名", "base_url": "https://api.deepseek.com"}]}))
    assert updated.llm_reasoning_effort == "low" and updated.connection_profiles[0].reasoning_effort == "high"
    assert updated.connection_profiles[0].api_key == "profile-synthetic"
    cleared = update_agent_config(updated, AgentRuntimeConfigUpdate.model_validate({"llm_reasoning_effort": None,
        "connection_profiles": [{"id": "review", "name": "新审阅名", "base_url": "https://api.deepseek.com", "reasoning_effort": None}]}))
    assert cleared.llm_reasoning_effort is None and cleared.connection_profiles[0].reasoning_effort is None
    assert planning.llm_reasoning_effort == "low" and continuity.llm_reasoning_effort == "high"


def test_unset_effort_is_omitted_from_historical_nested_execution_and_old_fingerprint():
    old = {"profile_id": "default", "profile_name": "old", "protocol": "chat_completions",
           "model": "old-model", "task": "planning", "thinking_mode": "provider_default"}
    model = ModelExecution.model_validate(old)
    assert model.model_dump() == old and json.loads(model.model_dump_json()) == old
    nested = ProposalProvenance(created_by="fixture", model_execution=model).model_dump(mode="json")
    assert nested["model_execution"] == old
    explicit_null = ModelExecution.model_validate({**old, "reasoning_effort": None})
    assert explicit_null.model_dump() == old
    config = AgentRuntimeConfig()
    response = config_response(config).model_dump(mode="json")
    assert response["llm_reasoning_effort"] is None
    assert all("reasoning_effort" not in item for item in response["resolved_tasks"].values())


@pytest.mark.parametrize("data", [
    {"llm_reasoning_effort": "none"},
    {"llm_base_url": "https://api.deepseek.com", "llm_thinking_mode": "disabled", "llm_reasoning_effort": "low"},
    {"llm_base_url": "https://gateway.example", "llm_reasoning_effort": "high"},
])
def test_configuration_rejects_conflicting_or_unsupported_effort(data):
    with pytest.raises(ValidationError):
        AgentRuntimeConfig.model_validate(data)


def test_autonomous_planner_and_critic_requests_expose_actual_low_effort_envelopes(setup):
    _, _, _, writer, reviewer, service, _ = setup
    for provider in (writer, reviewer):
        provider.thinking_mode, provider.reasoning_effort = "enabled", "low"
    result = service.execute(create(setup).id)
    assert result.status == "awaiting_review"
    assert len(writer.calls) == 5 and len(reviewer.requests) == 6
    assert all(call.max_tokens == 52768 for call in writer.calls)
    assert all(call.max_tokens == 65536 for call in reviewer.requests)


def test_planned_writer_budget_is_visible_to_guard_before_provider_execution():
    from storygraph.services.scene_writer import LLMSceneWriter
    requests = []
    class Guard:
        thinking_mode, reasoning_effort = "enabled", "low"
        def generate(self, request):
            requests.append(request)
            assert request.max_tokens == 6024 + 32768
            raise RuntimeError("synthetic stop at financial guard")
    with pytest.raises(RuntimeError, match="financial guard"):
        LLMSceneWriter(provider=Guard(), model="fixture").draft(pack(2500))
    assert len(requests) == 1
