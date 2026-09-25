"""Scene writer construction from local settings."""

from __future__ import annotations

from storygraph.core.config import StoryGraphSettings
from storygraph.core.agent_config import load_agent_config, selected_agent_preset, settings_for_task
from storygraph.services.llm_provider import OpenAICompatibleProvider, ResponsesProvider, AnthropicMessagesProvider
from storygraph.services.scene_writer import LLMSceneWriter, RuleBasedSceneWriter
from storygraph.stores.draft_store import SQLiteDraftStore


def create_llm_provider(settings: StoryGraphSettings) -> OpenAICompatibleProvider:
    provider_class = {"chat_completions": OpenAICompatibleProvider,
                      "responses": ResponsesProvider,
                      "anthropic_messages": AnthropicMessagesProvider}.get(settings.llm_protocol)
    if provider_class is None:
        raise ValueError("Unsupported provider protocol")
    provider = provider_class(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        json_mode=settings.llm_json_mode,
    )
    provider.model_execution = getattr(settings, "model_execution", None)
    return provider


def create_scene_writer(settings: StoryGraphSettings, draft_store: SQLiteDraftStore):
    if getattr(settings, "resolved_task", None) is None:
        settings = settings_for_task(settings, "writing")
    if settings.scene_writer == "rule_based":
        return RuleBasedSceneWriter(draft_store)
    if settings.scene_writer == "llm":
        provider = create_llm_provider(settings)
        return LLMSceneWriter(
            draft_store=draft_store,
            provider=provider,
            model=settings.llm_model,
            agent_preset=getattr(settings, "agent_preset", None) or selected_agent_preset(
                load_agent_config(settings)
            ),
        )
    raise ValueError(f"Unknown scene writer: {settings.scene_writer}")
