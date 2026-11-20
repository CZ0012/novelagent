"""Offline MCP transport and Main Agent integration, never live model calls."""
import json

import pytest

from storygraph.core.errors import ContractError
from storygraph.models.authoring import AuthoringToolAction
from storygraph.services.authoring_mcp import AuthoringMCPServer, AuthoringMCPClient
from tests.test_authoring_service import FakeProvider, make_service, finish


def test_real_jsonrpc_handshake_tools_resources_and_calls():
    dispatched, validated = [], []
    server = AuthoringMCPServer(dispatch=lambda a: dispatched.append(a.tool) or {"ok": True},
        validate_context=lambda: validated.append(True))
    denied = json.loads(server.request(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})))
    assert "error" in denied and not dispatched
    client = AuthoringMCPClient(server)
    client.initialize()
    tools = client.call("tools/list")["tools"]
    assert any(t["name"] == "inspect_project" for t in tools)
    resources = client.call("resources/list")["resources"]
    assert len(resources) >= 5
    assert client.call("resources/read", {"uri": resources[0]["uri"]})["contents"][0]["text"]
    assert client.execute(AuthoringToolAction(tool="inspect_workspace")) == {"ok": True}
    assert dispatched == ["inspect_workspace"] and len(validated) >= 7
    invalid = json.loads(server.request('{"jsonrpc":"2.0","id":12,"method":"shell/exec","params":{"secret":"never echo"}}'))
    assert invalid["error"]["code"] == -32601 and "secret" not in json.dumps(invalid)


def test_mode_filters_registry_and_denies_mutation_before_dispatch():
    calls = []
    client = AuthoringMCPClient(AuthoringMCPServer(dispatch=lambda a: calls.append(a), validate_context=lambda: None, mode="review"))
    client.initialize()
    assert "propose_design_changes" not in {t["name"] for t in client.call("tools/list")["tools"]}
    with pytest.raises(ContractError, match="not_allowed_in_mode"):
        client.execute(AuthoringToolAction(tool="propose_workspace", args={"summary": "设计", "patch": {}}))
    assert calls == []


def test_main_discovery_project_reviews_and_navigation_traverse_mcp(monkeypatch):
    traversed = []
    original = AuthoringMCPServer.request
    def captured(self, wire):
        traversed.append(json.loads(wire)["method"])
        return original(self, wire)
    monkeypatch.setattr(AuthoringMCPServer, "request", captured)
    provider = FakeProvider({"tool": "discover_capabilities", "args": {}},
        {"tool": "inspect_project", "args": {}}, {"tool": "inspect_reviews", "args": {}},
        {"tool": "open_workflow", "args": {"target": "checks"}}, finish())
    service, session = make_service(provider, project_resolver=lambda p,a: {"entries": [{"id": "real_scene"}]})
    result = service.turn(project_id="project", session_id=session.id, expected_version=1, message="查看当前结构并解释审阅。")
    assert traversed.count("tools/call") == 5
    assert {"initialize", "tools/list", "resources/list", "resources/read"} <= set(traversed)
    traces = {m.tool_name: json.loads(m.content)["result"] for m in result.messages if m.role == "tool"}
    assert traces["inspect_project"]["entries"][0]["id"] == "real_scene"
    assert traces["open_workflow"]["executed"] is False
    assert traces["open_workflow"]["navigation"]["target"] == "checks"
    assert "Built-in executable working methods" in provider.requests[0].messages[0].content


def test_bad_navigation_and_discussion_proposal_do_not_dispatch_paid_extra_call():
    provider = FakeProvider({"tool": "propose_workspace", "args": {"summary": "方案", "patch": {}}})
    service, session = make_service(provider)
    with pytest.raises(ContractError, match="navigation_unavailable"):
        service.turn(project_id="project", session_id=session.id, expected_version=1, message="导航", navigation_context={"scene_id": "foreign"})
    assert not provider.requests
    with pytest.raises(ContractError, match="not_allowed_in_mode"):
        service.turn(project_id="project", session_id=session.id, expected_version=1, message="讨论", collaboration_mode="discuss")
    assert len(provider.requests) == 1


def test_single_passage_stays_out_of_character_request_and_initial_idea_is_not_duplicated():
    passage_pin = {"draft_id": "d", "version": 1, "text_sha256": "a" * 64, "start": 0, "end": 5}
    provider = FakeProvider({"tool": "simulate_character", "args": {"character_id": "actor", "question_kind": "next_action"}},
        {"options": [{"action": "耐心等待。", "rationale": "先观察。"}], "uncertainties": []}, finish())
    service, session = make_service(provider, navigation_validator=lambda p,f: None,
        passage_resolver=lambda p,s,pin: {**passage_pin, "scene_id": s, "text": "PASSAGE_CANARY"})
    service.character_view = lambda *a,**k: {"subjective_items": [], "plan": None, "observations": [], "character_id": "actor"}
    result = service.turn(project_id="project", session_id=session.id, expected_version=1,
        message=session.messages[0].content, navigation_context={"scene_id": "scene"}, selected_passage=passage_pin, max_steps=3)
    assert len([m for m in result.messages if m.role == "author"]) == 1
    assert "PASSAGE_CANARY" in str(provider.requests[0].messages)
    assert "PASSAGE_CANARY" not in str(provider.requests[1].messages)
    assert all("PASSAGE_CANARY" not in m.content for m in result.messages)


def test_explicit_navigation_focus_never_inherits_an_unrelated_target():
    service, session = make_service(navigation_validator=lambda *a: None)
    current = {"chapter_id": "old_chapter", "scene_id": "old_scene"}
    result = service._tool(session, AuthoringToolAction(tool="open_workflow", args={"target": "manuscript", "chapter_id": "new_chapter"}), navigation_context=current)
    assert result["navigation"] == {"target": "manuscript", "chapter_id": "new_chapter"}
    result = service._tool(session, AuthoringToolAction(tool="open_workflow", args={"target": "writer", "scene_id": "new_scene"}), navigation_context=current)
    assert result["navigation"] == {"target": "writer", "scene_id": "new_scene"}
    result = service._tool(session, AuthoringToolAction(tool="open_workflow", args={"target": "writer", "chapter_id": "new_chapter"}), navigation_context=current)
    assert result["status"] == "requires_scene_selection" and "scene_id" not in result["navigation"]
    result = service._tool(session, AuthoringToolAction(tool="open_workflow", args={"target": "continuity"}), navigation_context=current)
    assert result["navigation"] == {"target": "continuity", **current}


def test_continuity_without_scene_offers_explicit_scene_selection():
    service, session = make_service(navigation_validator=lambda *a: None)
    result = service._tool(session, AuthoringToolAction(tool="open_workflow", args={"target": "continuity", "chapter_id": "chapter"}))
    assert result["status"] == "requires_scene_selection"
    assert result["navigation"] == {"target": "manuscript", "chapter_id": "chapter"}
    assert result["executed"] is False
