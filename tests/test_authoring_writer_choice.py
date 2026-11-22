"""Session-scoped Writer choice crosses the MCP boundary without executing prose."""
import json

import pytest
from pydantic import ValidationError

from storygraph.core.errors import ContractError
from storygraph.models.authoring import AuthoringToolAction
from storygraph.services.authoring_mcp import AuthoringMCPClient, AuthoringMCPServer
from tests.test_authoring_service import FakeProvider, make_service, finish


def writers(project_id):
    assert project_id == "project"
    return [{"profile_id": "plan", "profile_name": "ChatGPT", "model": "account-model",
        "auth_mode": "chatgpt_plan", "fingerprint": "a" * 64, "ready": True,
        "api_key": "SECRET_CANARY", "base_url": "https://PRIVATE_CANARY"},
        {"profile_id": "offline", "profile_name": "Offline", "model": "unready-model",
         "auth_mode": "api_key", "fingerprint": "b" * 64, "ready": False}]


def test_session_local_real_configuration_choice_is_cas_saved_without_extra_provider_calls():
    provider = FakeProvider({"tool": "list_writers", "args": {}},
        {"tool": "pick_writer", "args": {"profile_id": "plan", "reason": "这个模型适合本场景的对白节奏。"}}, finish())
    service, session = make_service(provider, writer_resolver=writers)
    other = service.create(project_id="project", content_language="zh-CN", title="另一个会话", idea="另一条故事线。")
    result = service.turn(project_id="project", session_id=session.id, expected_version=1,
                          message="选择适合写正文的模型。", max_steps=3)
    assert len(provider.requests) == 3
    assert result.writer_choice.model_dump() == {"profile_id": "plan", "profile_name": "ChatGPT",
        "model": "account-model", "auth_mode": "chatgpt_plan", "fingerprint": "a" * 64,
        "reason": "这个模型适合本场景的对白节奏。"}
    assert service.get("project", session.id).writer_choice == result.writer_choice
    assert service.get("project", other.id).writer_choice is None
    assert not result.proposals and not result.workspace.items
    traces = [m.content for m in result.messages if m.role == "tool"]
    assert "SECRET_CANARY" not in str(provider.requests) + str(traces)
    assert "PRIVATE_CANARY" not in str(provider.requests) + str(traces)
    assert "fingerprint" not in "".join(traces)
    listed = json.loads(traces[0])["result"]["writers"]
    assert listed == [{"profile_id": "plan", "profile_name": "ChatGPT", "model": "account-model", "auth_mode": "chatgpt_plan"}]
    assert json.loads(traces[1])["result"]["executes_writer"] is False
    with pytest.raises(ContractError, match="stale_version"):
        service.turn(project_id="project", session_id=session.id, expected_version=1, message="再选一次。")
    assert len(provider.requests) == 3


@pytest.mark.parametrize("profile_id", ["missing", "offline"])
def test_unconfigured_or_unready_writer_cannot_be_selected(profile_id):
    service, session = make_service(writer_resolver=writers)
    with pytest.raises(ContractError, match="writer_not_available"):
        service._tool(session, AuthoringToolAction(tool="pick_writer", args={"profile_id": profile_id, "reason": "选择。"}))
    assert session.writer_choice is None


@pytest.mark.parametrize("mode", ["discuss", "review"])
def test_choice_tools_absent_and_blocked_in_read_only_modes(mode):
    calls = []
    client = AuthoringMCPClient(AuthoringMCPServer(dispatch=lambda a: calls.append(a),
        validate_context=lambda: None, mode=mode))
    client.initialize()
    assert not {"list_writers", "pick_writer"}.intersection(t["name"] for t in client.call("tools/list")["tools"])
    for action in [AuthoringToolAction(tool="list_writers"), AuthoringToolAction(tool="pick_writer", args={"profile_id": "plan", "reason": "选择。"})]:
        with pytest.raises(ContractError, match="not_allowed_in_mode"):
            client.execute(action)
    assert not calls


def test_reconciliation_removes_choice_from_catalog_and_rejects_unadvertised_call():
    client = AuthoringMCPClient(AuthoringMCPServer(dispatch=lambda a: pytest.fail("must not dispatch"),
        validate_context=lambda: None, excluded_tools={"list_writers", "pick_writer"}))
    client.initialize()
    assert not {"list_writers", "pick_writer"}.intersection(t["name"] for t in client.call("tools/list")["tools"])
    with pytest.raises(ContractError, match="not_allowed_in_mode"):
        client.execute(AuthoringToolAction(tool="list_writers"))
    service, session = make_service(writer_resolver=writers)
    with pytest.raises(ContractError, match="not_allowed_in_reconciliation"):
        service._tool(session, AuthoringToolAction(tool="list_writers"), reconcile_pin=object())


def test_choice_does_not_accept_fabricated_model_or_fingerprint_and_no_resolver_defaults_to_empty():
    with pytest.raises(ValidationError):
        AuthoringToolAction(tool="pick_writer", args={"profile_id": "plan", "reason": "选择。", "model": "invented"})
    service, session = make_service()
    assert service._tool(session, AuthoringToolAction(tool="list_writers"))["writers"] == []
    assert session.writer_choice is None


def test_persisted_choice_is_initial_context_on_next_turn_without_relisting_or_reselecting():
    provider = FakeProvider({"tool": "pick_writer", "args": {"profile_id": "plan", "reason": "适合对白。"}}, finish(), finish())
    service, session = make_service(provider, writer_resolver=writers)
    result = service.turn(project_id="project", session_id=session.id, expected_version=1, message="选好后继续。", max_steps=2)
    continued = service.turn(project_id="project", session_id=session.id, expected_version=result.version, message="接下来设计冲突。", max_steps=1)
    context = json.loads(provider.requests[2].messages[1].content)
    assert context["writer_choice"]["model"] == "account-model" and "fingerprint" not in context["writer_choice"]
    assert continued.writer_choice == result.writer_choice and len(provider.requests) == 3
