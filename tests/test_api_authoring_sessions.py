"""The actual HTTP author loop, reviewed scene bridge and stale writer boundary."""
import json

import pytest
from fastapi.testclient import TestClient

from apps.api import main
from storygraph.core.config import StoryGraphSettings
from storygraph.services.canon_snapshot import content_hash
from storygraph.services.llm_provider import LLMResponse


class ScriptedProvider:
    def __init__(self):
        self.actions = []
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return LLMResponse(json.dumps(self.actions.pop(0), ensure_ascii=False))


@pytest.fixture
def api(tmp_path, monkeypatch):
    settings = StoryGraphSettings(tmp_path)
    settings.llm_base_url = "https://example.invalid/v1"
    settings.llm_api_key = "fixture-only-not-a-real-key"
    settings.llm_model = "fixture"
    settings.scene_writer = "llm"
    provider = ScriptedProvider()
    monkeypatch.setattr(main, "create_llm_provider", lambda *_: provider)
    app = main.create_app(settings)
    client = TestClient(app)
    response = client.post("/projects", json={"title": "车站故事", "genre": "悬疑", "language": "zh-CN"})
    assert response.status_code == 200, response.text
    project = response.json()["project_id"]
    return client, app, provider, project, tmp_path


def fixture_card():
    return {"id": "first_card", "title": "车站相遇", "chapter_title": "第一章", "location": "车站",
        "author_summary": "小夏在车站等姐姐，真实原因PRIVATE_AUTHOR_PLAN仍对读者隐藏。",
        "timeline_position": "第一日08:00—08:20", "goal": "找到姐姐", "conflict": "发车前必须决定是否相信她",
        "emotional_turn": "怀疑转为克制", "intended_outcome": "她暂时拒绝同行", "pov_character_id": "xia",
        "depends_on": ["cause"], "withheld": ["PRIVATE_CAUSE_CANARY"],
        "writer_policy": {"access_mode": "pov", "surface_plan": {"kind": "literal", "text": "小夏在车站等姐姐，暂时拒绝同行。"},
            "characters": [{"character_id": "xia", "public_name": "小夏"}],
            "visible_claims": [{"text": "姐姐可能骗了我。", "presentation": "belief", "phase": "entry", "character_id": "xia"}],
            "writer_style": {"pov": "第三人称有限视角", "tone": "克制具体"}}}


def start_and_approve(api):
    client, app, provider, project, _ = api
    base = f"/projects/{project}/authoring-sessions"
    r = client.post(base, json={"title": "从灵感试写", "idea": "姐姐像是在说谎，原因先不决定。"})
    assert r.status_code == 200, r.text
    session = r.json()["session"]
    assert provider.requests == []
    assert session["workspace"]["items"] == []
    path = base + "/" + session["id"]
    provider.actions = [
        {"tool": "propose_workspace", "args": {"summary": "保留原因未定，先安排一次相遇。", "patch": {
            "upsert_items": [{"id": "cause", "kind": "true_cause", "status": "open", "text": "PRIVATE_CAUSE_CANARY：姐姐为何说谎仍未决定。"}],
            "upsert_scene_cards": [fixture_card()]}}},
        {"tool": "finish", "args": {"message": "真相仍未确定。请审阅这张试写卡。"}},
    ]
    r = client.post(path + "/turn", json={"expected_version": session["version"], "message": "给我一个试写方案。"})
    assert r.status_code == 200, r.text
    session = r.json()["session"]
    assert session["workspace"]["scene_cards"] == []
    proposal = session["proposals"][0]
    assert proposal["diff"]
    r = client.post(path + f"/proposals/{proposal['id']}/decision", json={"expected_version": session["version"], "decision": "adopt"})
    assert r.status_code == 200, r.text
    session = r.json()["session"]
    assert session["workspace"]["items"][0]["status"] == "open"
    return path, session


def test_idea_to_scene_compilation_then_decision_change_blocks_old_policy(api):
    client, app, provider, project, root = api
    path, session = start_and_approve(api)
    graph_before = json.loads((root / "graph.json").read_text(encoding="utf-8"))
    preview = client.post(path + "/cards/first_card/structure-preview", json={"expected_version": session["version"]})
    assert preview.status_code == 200, preview.text
    spec = preview.json()
    assert not spec["gaps"]
    assert json.loads((root / "graph.json").read_text(encoding="utf-8")) == graph_before
    apply_body = {"expected_version": session["version"], "card_version": spec["card_version"],
        "source_sha256": spec["source_sha256"], "reviewer": "试用作者", "rationale": "确认人物与场景计划，真相仍未定。"}
    response = client.post(path + "/cards/first_card/structure-apply", json=apply_body)
    assert response.status_code == 200, response.text
    session, scene = response.json()["session"], response.json()["scene_id"]
    before_compile = {"expected_version": session["version"], "target_scene_id": scene}
    response = client.post(path + "/cards/first_card/preview", json=before_compile)
    assert response.status_code == 200, response.text
    view = response.json()
    assert "PRIVATE_CAUSE_CANARY" not in json.dumps(view["messages"])
    assert "PRIVATE_AUTHOR_PLAN" not in json.dumps(view["messages"])
    assert "xia" not in json.dumps(view["writer_view"]["characters"])
    body = {**before_compile, "expected_policy_version": view["expected_policy_version"],
            "expected_source_context_sha256": view["source_context_sha256"]}
    response = client.post(path + "/cards/first_card/compile", json=body)
    assert response.status_code == 200, response.text
    session = response.json()["session"]
    pack = app.state.writer_visibility_context_builder.build(project_id=project, scene_id=scene)
    assert pack.writer_visibility is not None
    provider.actions = [
        {"tool": "propose_workspace", "args": {"summary": "改变原因候选，需要重新审阅场景卡。", "patch": {
            "upsert_items": [{"id": "cause", "kind": "true_cause", "status": "alternative", "text": "姐姐可能只是认错了人。"}]}}},
        {"tool": "finish", "args": {"message": "这个变化会影响已经确认的场景卡。"}},
    ]
    response = client.post(path + "/turn", json={"expected_version": session["version"], "message": "换一个原因候选。"})
    assert response.status_code == 200, response.text
    session = response.json()["session"]
    proposal = session["proposals"][-1]
    response = client.post(path + f"/proposals/{proposal['id']}/decision", json={"expected_version": session["version"], "decision": "adopt"})
    assert response.status_code == 200, response.text
    pack = app.state.writer_visibility_context_builder.build(project_id=project, scene_id=scene)
    assert pack.writer_visibility_required and pack.writer_visibility is None
    calls = len(provider.requests)
    response = client.post(f"/projects/{project}/scenes/{scene}/writer-visibility/preview")
    assert response.status_code == 409, response.text
    response = client.post(f"/projects/{project}/scenes/{scene}/agent-discussion/preview", json={
        "mode": "create_scene", "instruction": "起草这一场。", "include_context_pack": True,
        "prose_input_grants": {"instruction": True, "instruction_sha256": content_hash("起草这一场。"), "target": "none"}})
    assert response.status_code == 409, response.text
    assert len(provider.requests) == calls


def test_foreign_source_and_permission_and_cas_rejected_without_model(api):
    client, app, provider, project, _ = api
    base = f"/projects/{project}/authoring-sessions"
    response = client.post(base, json={"title": "坏引用", "idea": "读取不属于本作品的资料。", "source_document_ids": ["missing"]})
    assert response.status_code == 409
    session = client.post(base, json={"title": "灵感", "idea": "从空白开始。"}).json()["session"]
    response = client.post(base + f"/{session['id']}/turn", json={"expected_version": 90, "message": "继续。"})
    assert response.status_code == 409
    client.put("/settings/agent", json={"permission_level": "read_only"})
    response = client.post(base + f"/{session['id']}/turn", json={"expected_version": session["version"], "message": "继续。"})
    assert response.status_code == 403
    assert provider.requests == []


def test_canonical_role_query_is_at_scene_entry_and_never_exposes_false_topic_truth(api):
    client, app, provider, project, _ = api
    path, session = start_and_approve(api)
    preview = client.post(path + "/cards/first_card/structure-preview", json={"expected_version": session["version"]}).json()
    response = client.post(path + "/cards/first_card/structure-apply", json={
        "expected_version": session["version"], "card_version": preview["card_version"],
        "source_sha256": preview["source_sha256"], "reviewer": "作者", "rationale": "确认试写计划。"})
    assert response.status_code == 200, response.text
    session = response.json()["session"]
    graph = app.state.writer_visibility_context_builder.graph_store
    seed = {"source_ref": "explicit_test_author", "reviewer": "作者", "rationale": "只构建隔离测试的既定信息。"}
    for ident, description in [("known", "车站八点开门。"), ("false_topic", "PRIVATE_ACTUAL_PLACE红色保险柜")]:
        graph.seed_canon_node(node_id=ident, node_type="Secret",
            properties={"project_id": project, "description": description}, **seed)
    actor = preview["character_mapping"]["xia"]
    for kind, target in [("KNOWS_SECRET", "known"), ("BELIEVES_FALSELY", "false_topic")]:
        graph.seed_canon_relation(relation_id="test_" + kind, relation_type=kind, source_id=actor,
            target_id=target, properties={"project_id": project, "initial_knowledge": True}, **seed)
    provider.actions = [
        {"tool": "simulate_character", "args": {"character_id": "xia", "card_id": "first_card", "question_kind": "next_action"}},
        {"options": [{"action": "在车站门口等待。", "rationale": "等待不需要知道姐姐的真实动机。"}], "uncertainties": ["还不能确定她是否说谎。"]},
        {"tool": "finish", "args": {"message": "先等待是一个可讨论的行动。"}},
    ]
    before = len(provider.requests)
    result = client.post(path + "/turn", json={"expected_version": session["version"], "message": "推演小夏。", "max_steps": 3})
    assert result.status_code == 200, result.text
    child = json.loads(provider.requests[before + 1].messages[-1].content)
    child_text = json.dumps(child, ensure_ascii=False)
    assert "车站八点开门" in child_text
    assert "PRIVATE_ACTUAL_PLACE" not in child_text
    assert "false_topic" not in child_text and "BELIEVES_FALSELY" not in child_text
    assert result.json()["session"]["turn_calls_started"] == 3


def test_revised_card_needs_explicit_plan_update_before_new_writer_policy(api):
    client, app, provider, project, _ = api
    path, session = start_and_approve(api)
    preview = client.post(path + "/cards/first_card/structure-preview", json={"expected_version": session["version"]}).json()
    response = client.post(path + "/cards/first_card/structure-apply", json={
        "expected_version": session["version"], "card_version": preview["card_version"],
        "source_sha256": preview["source_sha256"], "reviewer": "作者", "rationale": "批准试写场景。"})
    assert response.status_code == 200, response.text
    session, scene = response.json()["session"], response.json()["scene_id"]
    changed = dict(session["workspace"]["scene_cards"][0])
    changed.update(goal="先核对公告，再决定是否离开。", status="proposed",
                   author_summary="她先核对公告。PRIVATE_NEW_AUTHOR_PLAN不在本场向读者解释。")
    provider.actions = [
        {"tool": "propose_workspace", "args": {"summary": "调整本场的行动理由。", "patch": {"upsert_scene_cards": [changed]}}},
        {"tool": "finish", "args": {"message": "已提出新的场景安排，请审阅。"}},
    ]
    response = client.post(path + "/turn", json={"expected_version": session["version"], "message": "先查公告。"})
    assert response.status_code == 200, response.text
    session = response.json()["session"]
    proposal = session["proposals"][-1]
    session = client.post(path + f"/proposals/{proposal['id']}/decision", json={"expected_version": session["version"], "decision": "adopt"}).json()["session"]
    graph = app.state.writer_visibility_context_builder.graph_store
    assert graph.get_node(scene).properties["goal"] == "找到姐姐"
    request = {"expected_version": session["version"], "target_scene_id": scene}
    blocked = client.post(path + "/cards/first_card/preview", json=request)
    assert blocked.status_code == 409 and blocked.json()["detail"]["category"] == "authoring_scene_plan_review_required"
    preview = client.post(path + "/cards/first_card/structure-preview", json={"expected_version": session["version"]}).json()
    assert preview["operation"] == "update" and {c["field"] for c in preview["changes"]} == {"goal", "summary"}
    result = client.post(path + "/cards/first_card/structure-apply", json={
        "expected_version": session["version"], "card_version": preview["card_version"],
        "source_sha256": preview["source_sha256"], "reviewer": "作者", "rationale": "确认这次计划变更。"})
    assert result.status_code == 200, result.text
    assert graph.get_node(scene).properties["goal"] == changed["goal"]
    rendered = client.post(path + "/cards/first_card/preview", json=request)
    assert rendered.status_code == 200, rendered.text
    assert "PRIVATE_NEW_AUTHOR_PLAN" not in json.dumps(rendered.json()["messages"])
