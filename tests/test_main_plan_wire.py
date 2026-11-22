"""Main Agent's actual plan wire against a strict, entirely offline admission stub."""
import io
import json
from urllib.error import HTTPError

import pytest

from storygraph.core.agent_config import AgentRuntimeConfig, apply_agent_config, settings_for_task
from storygraph.core.config import StoryGraphSettings
from storygraph.services.llm_provider import LLMMessage, LLMRequest, ProviderError
from storygraph.services.scene_writer_factory import create_llm_provider
from tests.test_authoring_service import finish, make_service
from tests.test_chatgpt_plan_provider import completed

TOKEN = "synthetic-plan-oauth-secret"
LEGACY_KEY = "synthetic-legacy-api-secret"


class SyntheticLogin:
    def access_token(self, account_id):
        assert account_id == "synthetic-account"
        return TOKEN

    def account_ready(self, account_id):
        return account_id == "synthetic-account"


class StrictPlanServer:
    """Reject json_object unless input, independently of instructions, says JSON."""
    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.requests = []
        self.bodies = []

    def open(self, request, **kwargs):
        self.requests.append(request)
        body = json.loads(request.data)
        self.bodies.append(body)
        assert request.full_url == "https://api.openai.com/v1/responses"
        assert request.get_header("Authorization") == "Bearer " + TOKEN
        assert TOKEN not in request.data.decode() and LEGACY_KEY not in request.data.decode()
        assert body["store"] is False and body["stream"] is True
        assert "temperature" not in body and "max_output_tokens" not in body
        if body.get("text", {}).get("format", {}).get("type") == "json_object":
            if not any("json" in item["content"].lower() for item in body["input"]):
                raise HTTPError(request.full_url, 400, "synthetic rejection", {},
                    io.BytesIO(b'{"error":{"code":"missing_json_input","message":"input must mention JSON"}}'))
        assert self.outputs, "Unexpected retry or extra model call"
        output = self.outputs.pop(0)
        return io.BytesIO(completed(output if isinstance(output, str) else json.dumps(output)))


def plan_provider(tmp_path, monkeypatch, server):
    settings = StoryGraphSettings(tmp_path)
    settings.chatgpt_login = SyntheticLogin()
    apply_agent_config(settings, AgentRuntimeConfig(
        llm_api_key=LEGACY_KEY, llm_base_url="https://legacy.invalid/v1",
        connection_profiles=[{"id": "plan", "name": "Plan", "auth_mode": "chatgpt_plan",
            "protocol": "responses", "chatgpt_account_id": "synthetic-account", "model": "synthetic-model"}],
        task_assignments={"discussion": "plan"}))
    runtime = settings_for_task(settings, "discussion")
    assert runtime.llm_api_key == runtime.llm_base_url == ""
    monkeypatch.setattr("storygraph.services.chatgpt_plan_provider.request.build_opener", lambda *args: server)
    return create_llm_provider(runtime)


def test_main_first_tool_loop_and_followup_history_pass_strict_plan_admission(tmp_path, monkeypatch):
    server = StrictPlanServer({"tool": "inspect_canon", "args": {}}, finish("先明确动机。"), finish("再讨论后果。"))
    provider = plan_provider(tmp_path, monkeypatch, server)
    service, session = make_service(provider)
    first = service.turn(project_id="project", session_id=session.id, expected_version=1,
                         message="请讨论人物动机。", max_steps=2)
    assert first.turn_status == "idle" and first.turn_calls_started == 2
    assert len(server.requests) == 2
    assert any(m.tool_name == "inspect_canon" for m in first.messages)
    second = service.turn(project_id="project", session_id=session.id, expected_version=first.version,
                          message="接着讨论后果。", max_steps=1)
    assert second.turn_status == "idle" and second.turn_calls_started == 1
    assert len(server.requests) == 3 and server.outputs == []
    for body in server.bodies:
        assert body["text"]["format"]["type"] == "json_object"
        privileged = [m for m in body["input"] if m["role"] == "developer"]
        assert len(privileged) == 1 and "json" in privileged[0]["content"].lower()
        assert "人物动机" not in privileged[0]["content"]
        assert "inspect_canon" not in privileged[0]["content"]
        assert body["input"][0] == privileged[0]
    last = server.bodies[-1]["input"]
    assert any(m["role"] == "user" and "请讨论人物动机" in m["content"] for m in last)
    assert any(m["role"] == "user" and "接着讨论后果" in m["content"] for m in last)
    assert any(m["role"] == "assistant" and "先明确动机" in m["content"] for m in last)
    assert not any(m.tool_name == "format_correction" for m in second.messages)


def test_strict_server_rejects_old_instructions_only_shape_without_retry(tmp_path, monkeypatch):
    server = StrictPlanServer()
    provider = plan_provider(tmp_path, monkeypatch, server)
    # Emulate the historical wire by removing the new format-only developer item.
    original = server.open
    def old_shape(request, **kwargs):
        body = json.loads(request.data)
        body["input"] = [m for m in body["input"] if m["role"] != "developer"]
        request.data = json.dumps(body).encode()
        return original(request, **kwargs)
    provider._opener = old_shape
    with pytest.raises(ProviderError) as caught:
        provider.generate(LLMRequest(model="synthetic-model", messages=[
            LLMMessage("system", "Return JSON."), LLMMessage("user", "讨论动机。")]))
    assert caught.value.status == 400 and caught.value.outcome_known
    assert len(server.requests) == 1
    assert TOKEN not in str(caught.value) and "missing_json_input" not in str(caught.value)


@pytest.mark.parametrize("json_mode,response_format", [(True, None), (False, "json_object")])
def test_plain_text_has_no_injected_json_or_promoted_private_messages(tmp_path, monkeypatch, json_mode, response_format):
    server = StrictPlanServer("plain answer")
    provider = plan_provider(tmp_path, monkeypatch, server)
    provider.json_mode = json_mode
    result = provider.generate(LLMRequest(model="synthetic-model", response_format=response_format, messages=[
        LLMMessage("system", "trusted system instruction"),
        LLMMessage("developer", "trusted developer instruction"),
        LLMMessage("user", "private selected excerpt"),
        LLMMessage("assistant", "private character view")]))
    assert result.content == "plain answer"
    assert len(server.requests) == 1
    body = server.bodies[0]
    assert "text" not in body
    assert body["instructions"] == "trusted system instruction\n\ntrusted developer instruction"
    assert body["input"] == [{"role": "user", "content": "private selected excerpt"},
                             {"role": "assistant", "content": "private character view"}]


def test_plan_wire_keeps_selected_passage_out_of_character_subcall(tmp_path, monkeypatch):
    passage_pin = {"draft_id": "d", "version": 1, "text_sha256": "a" * 64, "start": 0, "end": 5}
    server = StrictPlanServer(
        {"tool": "simulate_character", "args": {"character_id": "actor", "question_kind": "next_action"}},
        {"options": [{"action": "耐心等待。", "rationale": "先观察。"}], "uncertainties": []},
        finish("我们可以先讨论这种可能性。"))
    provider = plan_provider(tmp_path, monkeypatch, server)
    service, session = make_service(provider, navigation_validator=lambda *args: None,
        passage_resolver=lambda p, s, pin: {**passage_pin, "scene_id": s, "text": "PASSAGE_CANARY"})
    service.character_view = lambda *args, **kwargs: {
        "subjective_items": [], "plan": None, "observations": [], "character_id": "actor"}
    result = service.turn(project_id="project", session_id=session.id, expected_version=1,
        message=session.messages[0].content, navigation_context={"scene_id": "scene"},
        selected_passage=passage_pin, max_steps=3)
    assert result.turn_status == "idle" and len(server.requests) == 3
    assert "PASSAGE_CANARY" in json.dumps(server.bodies[0])
    assert "PASSAGE_CANARY" not in json.dumps(server.bodies[1])
    assert all("PASSAGE_CANARY" not in m.content for m in result.messages)
    assert len([m for m in result.messages if m.role == "author"]) == 1
    for body in server.bodies:
        privileged = [m for m in body["input"] if m["role"] == "developer"]
        assert len(privileged) == 1
        assert "PASSAGE_CANARY" not in privileged[0]["content"]
        assert "actor" not in privileged[0]["content"]
