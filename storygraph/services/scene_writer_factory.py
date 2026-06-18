"""Scene writer construction from local settings."""

from __future__ import annotations

from storygraph.core.config import StoryGraphSettings
from storygraph.services.llm_provider import OpenAICompatibleProvider
from storygraph.services.scene_writer import LLMSceneWriter, RuleBasedSceneWriter
from storygraph.stores.draft_store import SQLiteDraftStore


def create_scene_writer(settings: StoryGraphSettings, draft_store: SQLiteDraftStore):
    if settings.scene_writer == "rule_based":
        return RuleBasedSceneWriter(draft_store)
    if settings.scene_writer == "llm":
        provider = OpenAICompatibleProvider(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
            json_mode=settings.llm_json_mode,
        )
        return LLMSceneWriter(
            draft_store=draft_store,
            provider=provider,
            model=settings.llm_model,
        )
    raise ValueError(f"Unknown scene writer: {settings.scene_writer}")
