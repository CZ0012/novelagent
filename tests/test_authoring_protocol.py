"""The single-command transport remains strict after prompt clarification."""
import json

import pytest

from storygraph.core.errors import ModelOutputError
from storygraph.services.canon_snapshot import content_hash
from storygraph.services.llm_provider import LLMResponse
from test_authoring_service import make_service


class RawProvider:
    def __init__(self, content):
        self.content, self.requests = content, []

    def generate(self, request):
        self.requests.append(request)
        return LLMResponse(self.content)


@pytest.mark.parametrize("suffix", ["second_command", "fake_result"])
def test_multiple_commands_or_invented_results_fail_without_dispatch_or_retry(suffix):
    command = {"tool": "read_source", "args": {"kind": "source_document", "id": "exact-pin"}}
    raw = json.dumps(command)
    if suffix == "second_command":
        raw += "\n\n" + json.dumps({"tool": "read_source", "args": {**command["args"], "start": 0, "end": 20000}})
    else:
        raw += "\n<result>Invented source text.</result>"
    provider = RawProvider(raw)
    service, _ = make_service(provider, source_resolver=lambda pid, pin: "真实且固定的底稿。")
    session = service.create(project_id="project", content_language="zh-CN", title="协议边界", idea="先读取所选底稿。",
        source_pins=[{"kind": "source_document", "id": "exact-pin", "sha256": content_hash("真实且固定的底稿。")}])
    with pytest.raises(ModelOutputError, match="invalid_tool_output"):
        service.turn(project_id="project", session_id=session.id, expected_version=1, message="先读取。", max_steps=1)
    saved = service.get("project", session.id)
    assert len(provider.requests) == 1 and saved.turn_calls_started == 1
    assert saved.turn_status == "failed" and saved.turn_error_category == "invalid_output"
    assert saved.workspace == session.workspace and saved.proposals == []
    assert not any(message.tool_name == "read_source" for message in saved.messages)
    assert sum(message.tool_name == "format_diagnostic" for message in saved.messages) == 1


def test_one_exact_command_executes_and_returns_only_real_source_evidence():
    provider = RawProvider('{"tool":"read_source","args":{"kind":"source_document","id":"exact-pin"}}')
    service, _ = make_service(provider, source_resolver=lambda pid, pin: "真实且固定的底稿。")
    session = service.create(project_id="project", content_language="zh-CN", title="协议边界", idea="先读取所选底稿。",
        source_pins=[{"kind": "source_document", "id": "exact-pin", "sha256": content_hash("真实且固定的底稿。")}])
    result = service.turn(project_id="project", session_id=session.id, expected_version=1, message="先读取。", max_steps=1)
    trace = json.loads(next(message.content for message in result.messages if message.tool_name == "read_source"))
    assert trace["result"]["text"] == "真实且固定的底稿。"
    assert len(provider.requests) == 1 and result.turn_status == "idle"


@pytest.mark.parametrize("raw", [
    '{"tool":"read_source","args":{"id":"RAW_SECRET_CANARY"}\n BROKEN_PAYLOAD}',
    '{"tool":"inspect_sources","args":{"UNTRUSTED_KEY_CANARY":"RAW_SECRET_CANARY"}}',
])
def test_safe_diagnostic_survives_failed_cas_and_only_enters_new_explicit_main_turn(raw):
    provider = RawProvider(raw)
    service, session = make_service(provider)
    with pytest.raises(ModelOutputError):
        service.turn(project_id="project", session_id=session.id, expected_version=1, message="讨论新的设计。", max_steps=1)
    failed = service.get("project", session.id)
    diagnostics = [message for message in failed.messages if message.tool_name == "format_diagnostic"]
    assert len(diagnostics) == 1 and failed.turn_status == "failed"
    assert failed.turn_calls_started == 1 and len(provider.requests) == 1
    assert failed.workspace == session.workspace and failed.proposals == []
    details = json.loads(diagnostics[0].content)["result"]
    assert details["accepted"] is False
    assert details["diagnostic"]["kind"] in {"invalid_json", "schema_validation"}
    assert "RAW_SECRET_CANARY" not in diagnostics[0].content
    assert "UNTRUSTED_KEY_CANARY" not in diagnostics[0].content
    assert "BROKEN_PAYLOAD" not in diagnostics[0].content
    provider.content = '{"tool":"finish","args":{"message":"上一条设计没有被接受，我们重新按作者选择继续。"}}'
    fresh = service.turn(project_id="project", session_id=session.id, expected_version=failed.version, message="我明确继续，请重新提出。", max_steps=1)
    fresh_wire = "\n".join(message.content for message in provider.requests[-1].messages)
    assert "format_diagnostic" in fresh_wire and '"accepted":false' in fresh_wire
    assert "RAW_SECRET_CANARY" not in fresh_wire and "UNTRUSTED_KEY_CANARY" not in fresh_wire
    assert len(provider.requests) == 2 and fresh.turn_status == "idle"
