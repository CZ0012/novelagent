"""Independent HTTP integration of bounded journals and explicit source rebinding."""
from storygraph.models.authoring import AuthoringMessage, AuthoringProposal, AuthoringPatch
from storygraph.services.authoring import AuthoringService, workspace_hash
from storygraph.services.llm_provider import ProviderError, LLMResponse
from test_api_authoring_sessions import api as api, start_and_approve
from test_api_sources import _source_payload


def create_session(client, project, **extra):
    base = f"/projects/{project}/authoring-sessions"
    response = client.post(base, json={"title": "长期协作", "idea": "姐姐的行动需要逐步设计。", **extra})
    assert response.status_code == 200, response.text
    session = response.json()["session"]
    return base + "/" + session["id"], session


def test_history_and_old_proposal_detail_are_complete_and_project_scoped(api):
    client, app, provider, project, _ = api
    path, initial = create_session(client, project)
    service = AuthoringService(store=app.state.authoring_store)
    session = service.get(project, initial["id"])
    session.messages += [AuthoringMessage(id=f"old-message-{n}", role="author", content=f"历史讨论第{n}轮。", created_at="now") for n in range(420)]
    session.proposals += [AuthoringProposal(id=f"old-proposal-{n}", base_workspace_sha256=workspace_hash(session.workspace),
        patch=AuthoringPatch(), summary=f"历史方案第{n}份。", status="rejected", created_at="now") for n in range(110)]
    service._save(session)
    latest = client.get(path).json()["session"]
    assert len(latest["messages"]) == 40 and latest["history_counts"]["messages"] == 421
    assert latest["history_has_more"] == {"messages": True, "proposals": True}
    found = client.get(path + "/history", params={"query": "历史讨论第0轮", "limit": 5})
    assert found.status_code == 200, found.text
    assert found.json()["records"][0]["id"] == "old-message-0" and found.json()["order"] == "newest_first"
    page = client.get(path + "/history", params={"kind": "proposals", "offset": 100, "limit": 10}).json()
    assert page["total_matches"] == 110 and page["returned_count"] == 10 and not page["more"]
    assert client.get(path + "/proposals/old-proposal-0").json()["proposal"]["status"] == "rejected"
    assert client.get(path + "/history", params={"offset": -1}).status_code == 409
    other = client.post("/projects", json={"title": "另一个作品", "language": "zh-CN"}).json()["project_id"]
    foreign = f"/projects/{other}/authoring-sessions/{initial['id']}"
    assert client.get(foreign + "/history").status_code == 409
    assert client.get(foreign + "/proposals/old-proposal-0").status_code == 409
    assert provider.requests == []


def test_source_rebind_blocks_old_pending_adoption_but_preserves_rejection_and_history(api):
    client, _, provider, project, _ = api
    first = client.post(f"/projects/{project}/sources", json=_source_payload(text="旧资料中姐姐赶去车站。", relative_path="资料/旧资料.md")).json()["document"]["id"]
    path, session = create_session(client, project, source_document_ids=[first])
    provider.actions = [{"tool": "propose_workspace", "args": {"summary": "讨论姐姐的目的。", "patch": {"upsert_items": [
        {"id": "motive", "kind": "true_cause", "text": "姐姐可能想保护妹妹。", "status": "alternative"}]}}},
        {"tool": "finish", "args": {"message": "这个动机仍待作者决定。"}}]
    response = client.post(path + "/turn", json={"expected_version": session["version"], "message": "提出一个动机候选。", "max_steps": 2})
    assert response.status_code == 200, response.text
    session = response.json()["session"]
    pending = session["proposals"][0]
    second = client.post(f"/projects/{project}/sources", json=_source_payload(text="新资料中姐姐根本没有去车站。", relative_path="资料/新资料.md")).json()["document"]["id"]
    stale = client.post(path + "/sources", json={"expected_version": 1, "source_document_ids": [second]})
    assert stale.status_code == 409
    archived = client.post(f"/projects/{project}/sources/{first}/archive")
    assert archived.status_code == 200
    rebound = client.post(path + "/sources", json={"expected_version": session["version"], "source_document_ids": [second]})
    assert rebound.status_code == 200, rebound.text
    session = rebound.json()["session"]
    assert session["source_pins"][0]["id"] == second and session["proposals"][0]["stale"]
    decision = path + f"/proposals/{pending['id']}/decision"
    refused = client.post(decision, json={"expected_version": session["version"], "decision": "adopt"})
    assert refused.status_code == 409 and refused.json()["detail"]["category"] == "authoring_proposal_inputs_changed"
    rejected = client.post(decision, json={"expected_version": session["version"], "decision": "reject"})
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["session"]["proposals"][0]["status"] == "rejected"
    history = client.get(path + "/history", params={"query": "作者明确更新"}).json()
    assert history["total_matches"] == 1
    assert client.get(path + f"/proposals/{pending['id']}").json()["proposal"]["inputs_sha256"] == pending["inputs_sha256"]
    assert len(provider.requests) == 2


def test_selected_old_outline_version_remains_exact_until_explicit_rebind(api):
    client, _, provider, project, _ = api
    outline = client.post(f"/projects/{project}/proposals", json={"artifact_type": "outline_draft", "title": "已有大纲", "body": "旧版大纲：姐姐赶去车站。"})
    assert outline.status_code == 200, outline.text
    ident = outline.json()["id"]
    path, session = create_session(client, project, outline_proposal_ids=[ident])
    updated = client.patch(f"/projects/{project}/proposals/{ident}", json={"expected_version": 1, "body": "新版大纲：姐姐留在医院。", "actor": "author"})
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 2
    provider.actions = [{"tool": "read_source", "args": {"kind": "outline", "id": ident}},
        {"tool": "finish", "args": {"message": "当前会话仍明确引用旧版大纲。"}}]
    response = client.post(path + "/turn", json={"expected_version": session["version"], "message": "读取我此前选定的大纲。", "max_steps": 2})
    assert response.status_code == 200, response.text
    session = response.json()["session"]
    assert session["source_pins"][0]["version"] == 1
    assert "旧版大纲" in next(m["content"] for m in session["messages"] if m["tool_name"] == "read_source")
    rebound = client.post(path + "/sources", json={"expected_version": session["version"], "outline_proposal_ids": [ident]})
    assert rebound.status_code == 200, rebound.text
    session = rebound.json()["session"]
    assert session["source_pins"][0]["version"] == 2
    provider.actions = [{"tool": "read_source", "args": {"kind": "outline", "id": ident}},
        {"tool": "finish", "args": {"message": "现在明确使用作者选定的新版大纲。"}}]
    response = client.post(path + "/turn", json={"expected_version": session["version"], "message": "读取新选定的大纲。", "max_steps": 2})
    assert response.status_code == 200, response.text
    traces = [m["content"] for m in response.json()["session"]["messages"] if m["tool_name"] == "read_source"]
    assert "旧版大纲" in traces[0] and "新版大纲" in traces[-1]
    assert len(provider.requests) == 4


def test_unknown_provider_result_is_not_retried_by_get_or_recovery(api):
    client, app, provider, project, _ = api
    path, session = create_session(client, project)
    def failed(request):
        provider.requests.append(request)
        raise ProviderError("connection_error", outcome_known=False)
    provider.generate = failed
    response = client.post(path + "/turn", json={"expected_version": session["version"], "message": "继续讨论。", "max_steps": 3})
    assert response.status_code == 502, response.text
    saved = client.get(path).json()["session"]
    assert saved["turn_status"] == "unknown" and saved["turn_calls_started"] == 1
    assert client.post(path + "/recover", json={"expected_version": saved["version"]}).status_code == 409
    assert len(provider.requests) == 1
    # Simulate a process-interrupted reservation, not an automatic retry.
    service = AuthoringService(store=app.state.authoring_store)
    interrupted = service.get(project, session["id"])
    interrupted.turn_status, interrupted.turn_id = "running", "interrupted-fixture"
    interrupted = service._save(interrupted)
    stale = client.post(path + "/recover", json={"expected_version": saved["version"]})
    assert stale.status_code == 409
    recovered = client.post(path + "/recover", json={"expected_version": interrupted.version})
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["session"]["turn_status"] == "unknown"
    assert recovered.json()["session"]["turn_calls_started"] == 1
    assert len(provider.requests) == 1


def test_http_recovery_cannot_bypass_an_actively_running_provider_reservation(api):
    client, _, provider, project, _ = api
    path, session = create_session(client, project)
    attempted = []
    def generate(request):
        provider.requests.append(request)
        running = client.get(path).json()["session"]
        attempted.append(client.post(path + "/recover", json={"expected_version": running["version"]}))
        return LLMResponse('{"tool":"finish","args":{"message":"我们继续保留两种可能性。"}}')
    provider.generate = generate
    response = client.post(path + "/turn", json={"expected_version": session["version"], "message": "继续讨论。", "max_steps": 1})
    assert response.status_code == 200, response.text
    assert attempted[0].status_code == 409 and attempted[0].json()["detail"]["category"] == "authoring_turn_still_active"
    assert len(provider.requests) == 1


def test_create_and_rebind_reject_combined_source_count_before_source_lookup(api):
    client, _, provider, project, _ = api
    base = f"/projects/{project}/authoring-sessions"
    too_many = {"source_document_ids": [f"source-{n}" for n in range(25)],
                "outline_proposal_ids": [f"outline-{n}" for n in range(20)]}
    created = client.post(base, json={"title": "过多参考资料", "idea": "先选择来源。", **too_many})
    assert created.status_code == 422, created.text
    path, session = create_session(client, project)
    rebound = client.post(path + "/sources", json={"expected_version": session["version"], **too_many})
    assert rebound.status_code == 422, rebound.text
    assert client.get(path).json()["session"]["version"] == session["version"]
    # Duplicates count once per kind. A valid count reaches scoped lookup and
    # reports unavailable synthetic IDs instead of a count-validation error.
    duplicate_inputs = {"source_document_ids": [f"source-{n % 20}" for n in range(40)],
                        "outline_proposal_ids": [f"outline-{n % 20}" for n in range(40)]}
    accepted_shape = client.post(base, json={"title": "重复选择会去重", "idea": "先选择来源。", **duplicate_inputs})
    assert accepted_shape.status_code == 409, accepted_shape.text
    assert provider.requests == []


def test_api_reconcile_supplies_exact_framework_read_before_first_batch_command(api):
    import json
    from storygraph.services.canon_snapshot import content_hash
    client, _, provider, project, _ = api
    path, session = start_and_approve(api)
    preview = client.post(path + "/cards/first_card/structure-preview", json={"expected_version": session["version"]}).json()
    applied = client.post(path + "/cards/first_card/structure-apply", json={"expected_version": session["version"],
        "card_version": preview["card_version"], "source_sha256": preview["source_sha256"],
        "reviewer": "作者", "rationale": "确认测试场景的计划。"})
    assert applied.status_code == 200, applied.text
    session, scene = applied.json()["session"], applied.json()["scene_id"]
    text = "😀小夏看见门上的红灯，知道门已锁上。"
    saved = client.post(f"/projects/{project}/scenes/{scene}/draft", json={"text": text})
    assert saved.status_code == 200, saved.text
    draft = saved.json()
    before = len(provider.requests)
    provider.actions = [{"tool": "search_draft_quotes", "args": {"quotes": ["门已锁上"]}},
        {"tool": "finish", "args": {"message": "已定位当前正文的引文，尚未提出知识变更。"}}]
    card = session["workspace"]["scene_cards"][0]
    response = client.post(path + "/reconcile", json={"expected_version": session["version"],
        "draft_id": draft["id"], "draft_version": draft["version"], "text_sha256": content_hash(text),
        "card_id": card["id"], "card_version": card["version"], "max_steps": 2})
    assert response.status_code == 200, response.text
    result = response.json()["session"]
    assert len(provider.requests) - before == result["turn_calls_started"] == 2
    context = json.loads(provider.requests[before].messages[1].content)
    read = context["reconciliation_read"]
    assert read["text"] == text and read["start"] == 0 and read["end"] == len(text.encode("utf-16-le")) // 2
    assert read["pin"]["draft_id"] == draft["id"] and read["pin"]["text_sha256"] == content_hash(text)
    assert read["complete"] and not read["more"]
    reads = [message for message in result["messages"] if message["tool_name"] == "read_source"
             and json.loads(message["content"]).get("initiated_by") == "framework"]
    assert len(reads) == 1 and reads[0]["model_execution"] is None
