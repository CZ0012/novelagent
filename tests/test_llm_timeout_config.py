"""Normal product settings accommodate measured slow thinking/review responses."""

import pytest

from storygraph.core.config import StoryGraphSettings
from storygraph.core.agent_config import settings_for_task
from storygraph.services import scene_writer_factory


def test_llm_transport_timeout_defaults_to_300_seconds(tmp_path, monkeypatch):
    monkeypatch.delenv("STORYGRAPH_LLM_TIMEOUT_SECONDS", raising=False)
    assert StoryGraphSettings(tmp_path).llm_timeout_seconds == 300.0


@pytest.mark.parametrize("value", ["60", "12.5", "450"])
def test_explicit_timeout_override_is_preserved_across_task_resolution(tmp_path, monkeypatch, value):
    monkeypatch.setenv("STORYGRAPH_LLM_TIMEOUT_SECONDS", value)
    settings = StoryGraphSettings(tmp_path)
    assert settings.llm_timeout_seconds == float(value)
    assert settings_for_task(settings, "planning").llm_timeout_seconds == float(value)
    assert settings_for_task(settings, "continuity").llm_timeout_seconds == float(value)


def test_default_timeout_reaches_provider_constructor_without_any_network_call(tmp_path, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.delenv("STORYGRAPH_LLM_TIMEOUT_SECONDS", raising=False)
    captured = []
    def provider(**kwargs):
        captured.append(kwargs)
        return SimpleNamespace()
    monkeypatch.setattr(scene_writer_factory, "OpenAICompatibleProvider", provider)
    settings = StoryGraphSettings(tmp_path)
    settings.llm_protocol = "chat_completions"
    settings.llm_base_url, settings.llm_api_key = "https://fixture.invalid", "synthetic-test-key"
    scene_writer_factory.create_llm_provider(settings_for_task(settings, "continuity"))
    assert captured[0]["timeout_seconds"] == 300.0 and len(captured) == 1
