"""Resolve an author's configured prose connections without exposing their secrets."""
from hashlib import sha256
import json

from pydantic import Field

from storygraph.core.agent_config import settings_for_task
from storygraph.core.errors import ContractError
from storygraph.models.common import ContractModel
from storygraph.services.scene_writer_factory import provider_ready


class WriterRouteReference(ContractModel):
    profile_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


def writer_route(runtime):
    execution = runtime.model_execution
    mode = getattr(runtime, "llm_auth_mode", "api_key")
    identity = [execution["profile_id"], execution["model"], execution["protocol"],
                mode, runtime.llm_base_url, getattr(runtime, "llm_chatgpt_account_id", None),
                runtime.llm_thinking_mode, runtime.llm_reasoning_effort, runtime.llm_json_mode]
    fingerprint = sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()
    return {"profile_id": execution["profile_id"], "profile_name": execution["profile_name"],
            "model": execution["model"], "auth_mode": mode, "fingerprint": fingerprint,
            "ready": provider_ready(runtime)}


def available_writers(settings):
    profiles = settings.agent_runtime_config.connection_profiles
    result = []
    for profile_id in ["default", *(profile.id for profile in profiles)]:
        route = writer_route(settings_for_task(settings, "writing", profile_id=profile_id))
        if route["ready"]:
            result.append(route)
    return result


def resolve_prose_connection(settings, task, choice):
    if choice is None:
        return settings_for_task(settings, task)
    if task not in {"writing", "revision"}:
        raise ContractError("writer_choice_prose_only")
    try:
        runtime = settings_for_task(settings, task, profile_id=choice.profile_id)
    except ValueError:
        raise ContractError("writer_choice_unavailable") from None
    current = writer_route(runtime)
    if not current["ready"] or current["fingerprint"] != choice.fingerprint:
        raise ContractError("writer_choice_stale")
    return runtime
