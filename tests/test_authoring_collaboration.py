import pytest

from storygraph.core.errors import ContractError
from storygraph.services.authoring_collaboration import (
    allowed_authoring_tools,
    validate_authoring_mode_tool,
)
from test_api_authoring_sessions import api as api


@pytest.mark.parametrize("mode", ["discuss", "review"])
def test_read_only_turn_blocks_a_valid_design_command_from_the_provider(api, mode):
    client, _, provider, project_id, _ = api
    base = f"/projects/{project_id}/authoring-sessions"
    session = client.post(base, json={"idea": "有人在等一封信。", "title": "信"}).json()["session"]
    path = f"{base}/{session['id']}"
    provider.actions = [{"tool": "propose_workspace", "args": {
        "summary": "确定了信的位置。",
        "patch": {"upsert_items": [{"id": "letter", "kind": "world_fact",
                                    "status": "author_decided", "text": "信锁在抽屉里。"}]},
    }}]
    response = client.post(path + "/turn", json={
        "expected_version": session["version"], "collaboration_mode": mode,
        "message": "我们只讨论可能性。", "max_steps": 1,
    })
    assert response.status_code >= 400
    saved = client.get(path).json()["session"]
    assert len(provider.requests) == 1
    assert saved["workspace"] == session["workspace"]
    assert saved["proposals"] == []


def test_default_collaboration_exposes_proposals_and_unknown_modes_fail_closed():
    assert "propose_workspace" in allowed_authoring_tools("collaborate")
    for mode in ("discuss", "review"):
        assert "simulate_character" in allowed_authoring_tools(mode)
        assert "revise_proposal" not in allowed_authoring_tools(mode)
        with pytest.raises(ContractError):
            validate_authoring_mode_tool(mode, "propose_design_changes")
    with pytest.raises(ContractError):
        allowed_authoring_tools("unknown")
