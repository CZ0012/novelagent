"""Actual scoped HTTP navigation/pin/selection integration with a fake provider."""
import json

from tests.test_api_authoring_sessions import api, start_and_approve  # noqa: F401
from storygraph.services.canon_snapshot import content_hash


def create_scene(api):  # noqa: F811
    client, app, provider, project, root = api
    path, session = start_and_approve(api)
    preview = client.post(path + "/cards/first_card/structure-preview", json={"expected_version": session["version"]}).json()
    response = client.post(path + "/cards/first_card/structure-apply", json={"expected_version": session["version"],
        "card_version": preview["card_version"], "source_sha256": preview["source_sha256"], "reviewer": "作者", "rationale": "确认测试结构。"})
    assert response.status_code == 200, response.text
    result = response.json()
    return path, result["session"], result["scene_id"]


def test_actual_structure_navigation_and_scope(api):  # noqa: F811
    client, app, provider, project, _ = api
    path, session, scene = create_scene(api)
    provider.actions = [{"tool": "inspect_project", "args": {}}, {"tool": "inspect_reviews", "args": {}},
        {"tool": "open_workflow", "args": {"target": "writer"}}, {"tool": "finish", "args": {"message": "已查到实际场景，请打开写作工具核对输入。"}}]
    response = client.post(path + "/turn", json={"expected_version": session["version"], "message": "查看实际项目。", "navigation_context": {"scene_id": scene}, "collaboration_mode": "review"})
    assert response.status_code == 200, response.text
    result = response.json()["session"]
    traces = {m["tool_name"]: json.loads(m["content"])["result"] for m in result["messages"] if m["role"] == "tool"}
    assert any(e["id"] == scene for e in traces["inspect_project"]["entries"])
    assert traces["open_workflow"]["navigation"] == {"target": "writer", "scene_id": scene}
    assert traces["open_workflow"]["executed"] is False
    calls = len(provider.requests)
    invalid = client.post(path + "/turn", json={"expected_version": result["version"], "message": "查看", "navigation_context": {"scene_id": "foreign"}})
    assert invalid.status_code >= 400 and len(provider.requests) == calls


def test_pin_update_is_explicit_cas_and_navigation_does_not_read_prose(api):  # noqa: F811
    client, app, provider, project, _ = api
    path, session, scene = create_scene(api)
    response = client.post(f"/projects/{project}/scenes/{scene}/draft", json={"text": "前文。只选这句。后文不应发送。"})
    assert response.status_code == 200, response.text
    draft = response.json()
    pin = client.post(path + "/draft-pins", json={"expected_version": session["version"], "draft_ids": [draft["id"]]})
    assert pin.status_code == 200, pin.text
    session = pin.json()["session"]
    assert session["draft_pins"][0]["text_sha256"] == content_hash(draft["text"])
    calls = len(provider.requests)
    stale = client.post(path + "/draft-pins", json={"expected_version": session["version"] - 1, "draft_ids": []})
    assert stale.status_code == 409 and len(provider.requests) == calls
    provider.actions = [{"tool": "finish", "args": {"message": "这句可以更明确。"}}]
    response = client.post(path + "/turn", json={"expected_version": session["version"], "message": "只讨论选文。",
        "navigation_context": {"scene_id": scene}, "selected_passage": {"draft_id": draft["id"], "version": draft["version"],
            "text_sha256": content_hash(draft["text"]), "start": 3, "end": 8}})
    assert response.status_code == 200, response.text
    context = json.loads(provider.requests[-1].messages[1].content)
    assert context["selected_passage"]["text"] == "只选这句。"
    assert "后文不应发送" not in str(provider.requests[-1].messages)
    session = response.json()["session"]
    provider.actions = [{"tool": "read_source", "args": {"kind": "draft", "id": draft["id"]}}]
    response = client.post(path + "/turn", json={"expected_version": session["version"], "message": "仅选段。", "navigation_context": {"scene_id": scene},
        "selected_passage": {"draft_id": draft["id"], "version": draft["version"], "text_sha256": content_hash(draft["text"]), "start": 3, "end": 8}})
    assert response.status_code >= 400

def test_unbinding_a_cited_draft_preserves_adopted_evidence_and_session(api):  # noqa: F811
    client, _, provider, project, _ = api
    path, session, scene = create_scene(api)
    text = "她拉开抽屉。"
    draft = client.post(f"/projects/{project}/scenes/{scene}/draft", json={"text": text}).json()
    pins = {"draft_ids": [draft["id"]], "expected_version": session["version"]}
    session = client.post(path + "/draft-pins", json=pins).json()["session"]
    repeat = client.post(path + "/draft-pins", json={**pins, "expected_version": session["version"]})
    assert repeat.json()["session"]["version"] == session["version"]
    record = {"draft_id": draft["id"], "version": draft["version"], "text_sha256": content_hash(text),
              "start": 0, "end": len(text), "expected_text": text, "presentation": "narration"}
    provider.actions = [{"tool": "propose_workspace", "args": {
        "summary": "保留读者已见的动作。", "patch": {"add_reader_records": [record]}}},
        {"tool": "finish", "args": {"message": "请核对原文。"}}]
    turn = client.post(path + "/turn", json={"message": "登记已见的动作。", "expected_version": session["version"]})
    assert turn.status_code == 200, turn.text
    session = turn.json()["session"]
    proposal = next(p for p in session["proposals"] if p["status"] == "pending")
    session = client.post(path + "/proposals/" + proposal["id"] + "/decision",
                          json={"expected_version": session["version"], "decision": "adopt"}).json()["session"]
    refused = client.post(path + "/draft-pins", json={"draft_ids": [], "expected_version": session["version"]})
    assert refused.status_code == 409
    assert refused.json()["detail"]["category"] == "authoring_draft_pin_in_use"
    assert client.get(path).json()["session"] == session
