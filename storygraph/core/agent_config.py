"""Persisted local agent runtime configuration."""

from __future__ import annotations

from enum import StrEnum
import json

from pydantic import BaseModel, Field

from storygraph.core.config import StoryGraphSettings


class AgentPermissionLevel(StrEnum):
    READ_ONLY = "read_only"
    READ_GENERATE = "read_generate"
    FULL = "full"


class AgentRuntimeConfig(BaseModel):
    scene_writer: str = "rule_based"
    provider_label: str = "OpenAI-compatible"
    llm_base_url: str = ""
    llm_model: str = "deepseek-chat"
    llm_api_key: str = ""
    llm_json_mode: bool = True
    permission_level: AgentPermissionLevel = AgentPermissionLevel.FULL


class AgentRuntimeConfigUpdate(BaseModel):
    scene_writer: str = Field(default="rule_based", pattern="^(rule_based|llm)$")
    provider_label: str = "OpenAI-compatible"
    llm_base_url: str = ""
    llm_model: str = "deepseek-chat"
    llm_api_key: str | None = None
    clear_api_key: bool = False
    llm_json_mode: bool = True
    permission_level: AgentPermissionLevel = AgentPermissionLevel.FULL


class AgentRuntimeConfigResponse(BaseModel):
    scene_writer: str
    provider_label: str
    llm_base_url: str
    llm_model: str
    api_key_configured: bool
    api_key_preview: str | None
    llm_json_mode: bool
    permission_level: AgentPermissionLevel


PERMISSION_ORDER = {
    AgentPermissionLevel.READ_ONLY: 0,
    AgentPermissionLevel.READ_GENERATE: 1,
    AgentPermissionLevel.FULL: 2,
}


def load_agent_config(settings: StoryGraphSettings) -> AgentRuntimeConfig:
    config = AgentRuntimeConfig(
        scene_writer=settings.scene_writer,
        llm_base_url=settings.llm_base_url,
        llm_model=settings.llm_model,
        llm_api_key=settings.llm_api_key,
        llm_json_mode=settings.llm_json_mode,
    )
    if not settings.agent_config_path.exists():
        return config
    payload = json.loads(settings.agent_config_path.read_text(encoding="utf-8"))
    stored = AgentRuntimeConfig.model_validate(payload)
    if not stored.llm_api_key and settings.llm_api_key:
        stored.llm_api_key = settings.llm_api_key
    return stored


def save_agent_config(settings: StoryGraphSettings, config: AgentRuntimeConfig) -> None:
    settings.agent_config_path.parent.mkdir(parents=True, exist_ok=True)
    settings.agent_config_path.write_text(
        json.dumps(config.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def update_agent_config(
    current: AgentRuntimeConfig,
    update: AgentRuntimeConfigUpdate,
) -> AgentRuntimeConfig:
    api_key = current.llm_api_key
    if update.clear_api_key:
        api_key = ""
    elif update.llm_api_key is not None:
        api_key = update.llm_api_key
    return AgentRuntimeConfig(
        scene_writer=update.scene_writer,
        provider_label=update.provider_label,
        llm_base_url=update.llm_base_url,
        llm_model=update.llm_model,
        llm_api_key=api_key,
        llm_json_mode=update.llm_json_mode,
        permission_level=update.permission_level,
    )


def apply_agent_config(settings: StoryGraphSettings, config: AgentRuntimeConfig) -> None:
    settings.scene_writer = config.scene_writer
    settings.llm_base_url = config.llm_base_url
    settings.llm_api_key = config.llm_api_key
    settings.llm_model = config.llm_model
    settings.llm_json_mode = config.llm_json_mode


def config_response(config: AgentRuntimeConfig) -> AgentRuntimeConfigResponse:
    return AgentRuntimeConfigResponse(
        scene_writer=config.scene_writer,
        provider_label=config.provider_label,
        llm_base_url=config.llm_base_url,
        llm_model=config.llm_model,
        api_key_configured=bool(config.llm_api_key),
        api_key_preview=_preview_secret(config.llm_api_key),
        llm_json_mode=config.llm_json_mode,
        permission_level=config.permission_level,
    )


def has_permission(current: AgentPermissionLevel, required: AgentPermissionLevel) -> bool:
    return PERMISSION_ORDER[current] >= PERMISSION_ORDER[required]


def _preview_secret(secret: str) -> str | None:
    if not secret:
        return None
    if len(secret) <= 8:
        return "configured"
    return f"{secret[:4]}...{secret[-4:]}"
