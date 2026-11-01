"""One known-completed format correction shares the original turn allowance."""
import json

import pytest

from storygraph.core.errors import ContractError, ModelOutputError
from storygraph.services.canon_snapshot import content_hash
from storygraph.services.llm_provider import LLMResponse, ProviderError
from test_authoring_service import make_service, item


class SequenceProvider:
    def __init__(self, *outputs):
        self.outputs, self.requests = list(outputs), []

    def generate(self, request):
        self.requests.append(request)
        output = self.outputs.pop(0)
        if callable(output):
            output = output()
        if isinstance(output, Exception):
            raise output
        return LLMResponse(json.dumps(output, ensure_ascii=False) if isinstance(output, dict) else output)


FINISH = {"tool": "finish", "args": {"message": "我们保留原有设计，继续讨论人物选择。"}}


def test_known_malformed_output_is_corrected_once_without_sending_bad_raw_text():
    provider = SequenceProvider('{"tool":"RAW_INVALID_CANARY" BROKEN', FINISH)
    service, session = make_service(provider)
    result = service.turn(project_id="project", session_id=session.id, expected_version=1, message="继续讨论。", max_steps=2)
    assert result.turn_status == "idle" and result.turn_calls_started == 2
    assert sum(m.tool_name == "format_correction" for m in result.messages) == 1
    assert "RAW_INVALID_CANARY" not in "\n".join(m.content for m in provider.requests[1].messages)
    assert "format_diagnostic" in "\n".join(m.content for m in provider.requests[1].messages)


@pytest.mark.parametrize("category", ["invalid_response", "incomplete_response", "unsupported_output"])
def test_completed_empty_or_unsupported_output_can_use_one_remaining_main_call(category):
    provider = SequenceProvider(ProviderError(category, outcome_known=True), FINISH)
    service, session = make_service(provider)
    result = service.turn(project_id="project", session_id=session.id, expected_version=1, message="继续讨论。", max_steps=2)
    assert result.turn_status == "idle" and len(provider.requests) == result.turn_calls_started == 2
    diagnostic = json.loads(next(m.content for m in result.messages if m.tool_name == "format_diagnostic"))
    assert diagnostic["result"]["diagnostic"] == {"kind": "completed_output_format", "category": category}


def test_second_malformed_output_fails_even_with_unused_call_allowance():
    provider = SequenceProvider("BROKEN_ONE", "BROKEN_TWO", FINISH)
    service, session = make_service(provider)
    with pytest.raises(ModelOutputError):
        service.turn(project_id="project", session_id=session.id, expected_version=1, message="继续讨论。", max_steps=8)
    result = service.get("project", session.id)
    assert result.turn_status == "failed" and len(provider.requests) == result.turn_calls_started == 2
    assert sum(m.tool_name == "format_correction" for m in result.messages) == 1


def test_no_remaining_allowance_keeps_failure_without_a_correction_dispatch():
    provider = SequenceProvider("BROKEN", FINISH)
    service, session = make_service(provider)
    with pytest.raises(ModelOutputError):
        service.turn(project_id="project", session_id=session.id, expected_version=1, message="继续讨论。", max_steps=1)
    result = service.get("project", session.id)
    assert result.turn_status == "failed" and len(provider.requests) == 1
    assert not any(m.tool_name == "format_correction" for m in result.messages)


def test_successful_character_result_survives_later_main_format_correction():
    provider = SequenceProvider({"tool": "simulate_character", "args": {"character_id": "actor", "question_kind": "next_action"}},
        {"options": [{"action": "先听对方怎样解释。", "rationale": "我还没有足够线索。"}], "uncertainties": []},
        ProviderError("invalid_response", outcome_known=True), FINISH)
    service, session = make_service(provider)
    result = service.turn(project_id="project", session_id=session.id, expected_version=1, message="推演人物并讨论。", max_steps=4)
    assert result.turn_status == "idle" and len(provider.requests) == result.turn_calls_started == 4
    assert sum(m.tool_name == "simulate_character" for m in result.messages) == 1
    assert sum(m.tool_name == "format_correction" for m in result.messages) == 1
    assert "先听对方怎样解释" in "\n".join(m.content for m in provider.requests[-1].messages)


def reference_command(*, valid):
    return {"tool": "propose_workspace", "args": {"summary": "增加一条设计。", "patch": {
        "upsert_items": [item("new-item", depends_on=[] if valid else ["CANONICAL_SCENE_PRIVATE_REF"])]}}}


def test_known_dangling_design_reference_can_be_corrected_once_without_echo_or_substitution():
    provider = SequenceProvider(reference_command(valid=False), reference_command(valid=True))
    service, session = make_service(provider)
    result = service.turn(project_id="project", session_id=session.id, expected_version=1, message="设计下一场。", max_steps=2)
    assert result.turn_status == "idle" and result.turn_calls_started == len(provider.requests) == 2
    assert len(result.proposals) == 1 and result.proposals[0].patch.upsert_items[0].depends_on == []
    diagnostic = next(message.content for message in result.messages if message.tool_name == "format_diagnostic")
    assert '"code":"authoring_patch_dangling_reference"' in diagnostic
    assert "CANONICAL_SCENE_PRIVATE_REF" not in diagnostic
    assert "CANONICAL_SCENE_PRIVATE_REF" not in "\n".join(m.content for m in provider.requests[1].messages)
    assert result.workspace.items == []


def test_two_bad_design_reference_commands_stop_with_original_contract_error():
    provider = SequenceProvider(reference_command(valid=False), reference_command(valid=False), reference_command(valid=True))
    service, session = make_service(provider)
    with pytest.raises(ContractError, match="authoring_patch_dangling_reference"):
        service.turn(project_id="project", session_id=session.id, expected_version=1, message="设计下一场。", max_steps=8)
    failed = service.get("project", session.id)
    assert failed.turn_status == "failed" and failed.turn_calls_started == len(provider.requests) == 2
    assert failed.proposals == [] and failed.workspace.items == []


@pytest.mark.parametrize("changed", ["source", "canon"])
def test_source_or_canon_change_cannot_be_treated_as_design_reference_correction(changed):
    source, canon = ["原始资料。"], ["canonical-state"]
    service, _ = make_service(source_resolver=lambda pid, pin: source[0],
        canon_resolver=lambda pid: {"fingerprint": content_hash(canon[0])})
    session = service.create(project_id="project", content_language="zh-CN", title="引用校验", idea="设计下一场。",
        source_pins=[{"kind": "source_document", "id": "source", "sha256": content_hash(source[0])}])
    def changed_reply():
        if changed == "source":
            source[0] = "已变化的资料。"
        else:
            canon[0] = "changed canonical state"
        return reference_command(valid=True)
    provider = SequenceProvider(reference_command(valid=False), changed_reply, reference_command(valid=True))
    service.provider = provider
    with pytest.raises(ContractError, match="source_stale|canon_changed"):
        service.turn(project_id="project", session_id=session.id, expected_version=1, message="设计下一场。", max_steps=8)
    failed = service.get("project", session.id)
    assert len(provider.requests) == failed.turn_calls_started == 2 and failed.turn_status == "failed"
    assert failed.proposals == []
