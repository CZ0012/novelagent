"""Independent final review: real API authoring plus source retirement."""
from test_api_authoring_sessions import api as api, start_and_approve
from test_api_sources import _source_payload


def test_archived_selected_source_revokes_compiled_authoring_policy(api):
    client, app, provider, project, _ = api
    path, session = start_and_approve(api)
    source = client.post(f"/projects/{project}/sources", json=_source_payload(text="姐姐在车站等候。"))
    assert source.status_code == 200, source.text
    source_id = source.json()["document"]["id"]
    session = client.post(path + "/sources", json={"expected_version": session["version"], "source_document_ids": [source_id]}).json()["session"]
    # Re-review the unchanged card against the newly selected source.
    card = session["workspace"]["scene_cards"][0]
    card["title"] += "（复核）"
    provider.actions = [{"tool":"propose_workspace", "args":{"summary":"保留已核对的场景卡。", "patch":{"upsert_scene_cards":[card]}}}, {"tool":"finish", "args":{"message":"请确认场景卡。"}}]
    response = client.post(path + "/turn", json={"expected_version":session["version"], "message":"确认参考资料后重新审阅场景卡。"})
    assert response.status_code == 200, response.text
    session = response.json()["session"]
    proposal = session["proposals"][-1]
    response = client.post(path + f"/proposals/{proposal['id']}/decision", json={"expected_version":session["version"], "decision":"adopt"})
    assert response.status_code == 200, response.text
    session = response.json()["session"]
    spec = client.post(path + "/cards/first_card/structure-preview", json={"expected_version":session["version"]}).json()
    response = client.post(path + "/cards/first_card/structure-apply", json={"expected_version":session["version"], "card_version":spec["card_version"], "source_sha256":spec["source_sha256"], "reviewer":"作者", "rationale":"批准试写结构。"})
    assert response.status_code == 200, response.text
    session, scene = response.json()["session"], response.json()["scene_id"]
    body = {"expected_version":session["version"], "target_scene_id":scene}
    response = client.post(path + "/cards/first_card/preview", json=body)
    assert response.status_code == 200, response.text
    spec = response.json()
    response = client.post(path + "/cards/first_card/compile", json={**body, "expected_policy_version":spec["expected_policy_version"], "expected_source_context_sha256":spec["source_context_sha256"]})
    assert response.status_code == 200, response.text
    assert app.state.writer_visibility_context_builder.build(project_id=project, scene_id=scene).writer_visibility is not None
    response = client.post(f"/projects/{project}/sources/{source_id}/archive")
    assert response.status_code == 200, response.text
    # Explicit recompilation correctly rejects this invalid selected pin.
    assert client.post(path + "/cards/first_card/preview", json=body).status_code == 409
    pack = app.state.writer_visibility_context_builder.build(project_id=project, scene_id=scene)
    assert pack.writer_visibility_required
    assert pack.writer_visibility is None



def test_identical_card_can_be_explicitly_reapproved_after_source_rebind(api):
    client, app, provider, project, _ = api
    path, session = start_and_approve(api)
    source = client.post(f"/projects/{project}/sources", json=_source_payload(text="姐姐在车站等候。"))
    assert source.status_code == 200
    session = client.post(path + "/sources", json={"expected_version":session["version"], "source_document_ids":[source.json()["document"]["id"]]}).json()["session"]
    card = session["workspace"]["scene_cards"][0]
    assert card["status"] == "proposed"
    provider.actions = [{"tool":"propose_workspace", "args":{"summary":"重新核对后保留原方案。", "patch":{"upsert_scene_cards":[card]}}}, {"tool":"finish", "args":{"message":"请重新确认这张场景卡。"}}]
    response = client.post(path + "/turn", json={"expected_version":session["version"], "message":"资料已更新，复核场景卡。"})
    assert response.status_code == 200, response.text
    session = response.json()["session"]
    proposal = session["proposals"][-1]
    response = client.post(path + f"/proposals/{proposal['id']}/decision", json={"expected_version":session["version"], "decision":"adopt"})
    assert response.status_code == 200, response.text
    assert response.json()["session"]["workspace"]["scene_cards"][0]["status"] == "approved"


def test_independent_child_does_not_receive_author_chat_or_truth(api):
    import json
    client, app, provider, project, _ = api
    path, session = start_and_approve(api)
    provider.actions = [
        {"tool":"simulate_character", "args":{"character_id":"xia", "card_id":"first_card", "question_kind":"next_action"}},
        {"options":[{"action":"继续在站台等待。", "rationale":"目前还不知道姐姐在哪里。"}], "uncertainties":["姐姐尚未出现。"]},
        {"tool":"finish", "args":{"message":"她可以先等待。"}},
    ]
    before = len(provider.requests)
    response = client.post(path + "/turn", json={"expected_version":session["version"], "message":"PRIVATE_AUTHOR_CHAT_CANARY：姐姐是幕后策划者，请独立推演小夏。", "max_steps":3})
    assert response.status_code == 200, response.text
    assert len(provider.requests) == before + 3
    child = json.dumps([{"role":m.role,"content":m.content} for m in provider.requests[before + 1].messages], ensure_ascii=False)
    for canary in ["PRIVATE_AUTHOR_CHAT_CANARY", "PRIVATE_CAUSE_CANARY", "PRIVATE_AUTHOR_PLAN", "author_summary", "withheld"]:
        assert canary not in child
    assert "姐姐可能骗了我" not in child  # Writer permission alone is not actor knowledge.



def test_format_diagnostic_stale_cas_cannot_replace_newer_session():
    import json
    import pytest
    from storygraph.core.errors import ContractError
    from test_authoring_service import make_service
    service, stale = make_service()
    newer = service.get("project", stale.id)
    newer.title = "作者刚保存的新标题"
    newer = service._save(newer)
    error = None
    try:
        json.loads('{"RAW_OUTPUT_CANARY": broken}')
    except json.JSONDecodeError as exc:
        error = exc
    with pytest.raises(ContractError, match="stale_version"):
        service._record_format_diagnostic(stale, error, None)
    latest = service.get("project", stale.id)
    assert latest.title == newer.title and latest.version == newer.version
    assert not any(m.tool_name == "format_diagnostic" for m in latest.messages)


def test_invalid_nested_schema_never_persists_output_values_or_unknown_keys():
    import json
    import pytest
    from storygraph.core.errors import ModelOutputError
    from test_authoring_protocol import RawProvider
    from test_authoring_service import make_service
    raw = json.dumps({"tool":"propose_workspace", "args":{"summary":"待审方案。", "patch":{"upsert_items":[{"id":"raw-value-canary", "kind":"world_fact", "text":"未通过校验的文本。", "UNKNOWN_SECRET_KEY_CANARY":{"unexpected":"RAW_NESTED_SECRET_CANARY"}}]}}})
    provider = RawProvider(raw)
    service, session = make_service(provider)
    with pytest.raises(ModelOutputError):
        service.turn(project_id="project", session_id=session.id, expected_version=1, message="请提出方案。", max_steps=1)
    latest = service.get("project", session.id)
    assert latest.turn_status == "failed" and len(provider.requests) == 1
    assert latest.workspace == session.workspace and latest.proposals == []
    payloads = service.store._connection.execute("SELECT payload FROM authoring_blobs").fetchall()
    stored = "\n".join(row[0] for row in payloads)
    for canary in ["RAW_NESTED_SECRET_CANARY", "UNKNOWN_SECRET_KEY_CANARY", "raw-value-canary"]:
        assert canary not in stored
    diagnostic = next(m for m in latest.messages if m.tool_name == "format_diagnostic")
    assert "<unknown_field>" in diagnostic.content


def test_new_patch_cannot_reference_items_only_present_in_another_pending_proposal():
    import pytest
    from storygraph.core.errors import ContractError
    from storygraph.models.authoring import AuthoringPatch
    from test_authoring_service import make_service, card, item
    service, session = make_service()
    service._propose(session, AuthoringPatch(upsert_items=[item("pending-only")]), "原完整方案待审。")
    session = service._save(session)
    revised = card(depends_on=["pending-only"], entry_knowledge=[{"character_id":"actor", "text":"人物尚未采用的信念。", "item_id":"pending-only"}])
    with pytest.raises(ContractError):
        service._propose(session, AuthoringPatch(upsert_character_plans=[{"character_id":"actor", "goal":"取信。", "belief_item_ids":["pending-only"]}], upsert_scene_cards=[revised]), "只包含修正片段的新方案。")


def _pending_revision_fixture():
    from storygraph.models.authoring import AuthoringPatch
    from test_authoring_service import make_service, card, item
    service, session = make_service()
    base = service._propose(session, AuthoringPatch(upsert_items=[item("truth"), item("untouched", text="另一条未修改的作者设计。")], upsert_character_plans=[{"character_id":"actor", "goal":"取信。", "belief_item_ids":["truth"]}], upsert_scene_cards=[card()]), "完整原提案。")
    return service, service._save(session), base["proposal_id"]


def test_revision_composes_complete_pending_delta_without_adoption_or_original_mutation():
    from storygraph.models.authoring import AuthoringToolAction
    from storygraph.services.authoring import apply_authoring_patch
    from test_authoring_service import item
    service, session, original_id = _pending_revision_fixture()
    old = service.get_proposal("project", session.id, original_id).model_dump(mode="json")
    before = session.workspace.model_dump(mode="json")
    action = AuthoringToolAction(tool="revise_proposal", args={"proposal_id":original_id, "summary":"只修正第一条设计。", "patch":{"upsert_items":[item("truth", text="修订后的作者设计。")], "remove_item_ids":["untouched"]}})
    result = service._tool(session, action)
    saved = service._save(session)
    revised = service.get_proposal("project", session.id, result["proposal_id"])
    assert revised.supersedes_proposal_id == original_id and revised.status == "pending"
    assert service.get_proposal("project", session.id, original_id).model_dump(mode="json") == old
    assert saved.workspace.model_dump(mode="json") == before
    projected = apply_authoring_patch(saved.workspace, revised.patch)
    assert [i.id for i in projected.items] == ["truth"]
    assert projected.items[0].text == "修订后的作者设计。"
    assert len(projected.character_plans) == len(projected.scene_cards) == 1
    assert not revised.patch.remove_item_ids  # Removing an original unadopted addition cancels it.


def test_revision_retains_untouched_pending_items_and_cannot_borrow_other_pending():
    import pytest
    from storygraph.core.errors import ContractError
    from storygraph.models.authoring import AuthoringPatch
    from storygraph.services.authoring import apply_authoring_patch
    from test_authoring_service import item
    service, session, original_id = _pending_revision_fixture()
    result = service._revise_proposal(session, original_id, AuthoringPatch(upsert_items=[item("truth", text="修订第一条。")]), "保留其余部分。")
    projected = apply_authoring_patch(session.workspace, session.proposals[-1].patch)
    assert {i.id for i in projected.items} == {"truth", "untouched"}
    assert result["proposal_id"] != original_id
    service._propose(session, AuthoringPatch(upsert_items=[item("another-pending")]), "另一待审提案。")
    with pytest.raises(ContractError):
        service._revise_proposal(session, original_id, AuthoringPatch(upsert_items=[item("new", depends_on=["another-pending"])]), "不能借用其他待审方案。")


def test_revision_rejects_old_workspace_baseline():
    import pytest
    from storygraph.core.errors import ContractError
    from storygraph.models.authoring import AuthoringPatch
    from test_authoring_service import item
    service, session, original_id = _pending_revision_fixture()
    change = service._propose(session, AuthoringPatch(upsert_items=[item("adopted")]), "先采用另一条设计。")
    session = service._save(session)
    session = service.review(project_id="project", session_id=session.id, expected_version=session.version, proposal_id=change["proposal_id"], decision="adopted")
    before = session.model_dump(mode="json")
    with pytest.raises(ContractError):
        service._revise_proposal(session, original_id, AuthoringPatch(), "过期基底不能修订。")
    assert session.model_dump(mode="json") == before


def test_real_api_revision_is_new_pending_complete_design_and_adopts_only_explicitly(api):
    from test_api_authoring_sessions import fixture_card
    client, app, provider, project, _ = api
    base = f"/projects/{project}/authoring-sessions"
    session = client.post(base, json={"title":"待审方案修订", "idea":"让原因保持未定。"}).json()["session"]
    path = base + "/" + session["id"]
    provider.actions = [{"tool":"propose_workspace", "args":{"summary":"完整原方案。", "patch":{"upsert_items":[{"id":"cause", "kind":"true_cause", "status":"open", "text":"作者未决定真实原因。"}], "upsert_scene_cards":[fixture_card()]}}}, {"tool":"finish", "args":{"message":"请审阅完整方案。"}}]
    response = client.post(path + "/turn", json={"expected_version":session["version"], "message":"提出完整方案。"})
    assert response.status_code == 200, response.text
    session = response.json()["session"]
    original = session["proposals"][0]
    revised_card = dict(original["patch"]["upsert_scene_cards"][0], title="雨夜相遇修订")
    provider.actions = [{"tool":"revise_proposal", "args":{"proposal_id":original["id"], "summary":"只调整场景标题。", "patch":{"upsert_scene_cards":[revised_card]}}}, {"tool":"finish", "args":{"message":"新完整修订等待审阅。"}}]
    response = client.post(path + "/turn", json={"expected_version":session["version"], "message":"修订待审标题，保留其余。"})
    assert response.status_code == 200, response.text
    session = response.json()["session"]
    revised = session["proposals"][-1]
    assert session["workspace"]["items"] == session["workspace"]["scene_cards"] == []
    assert session["proposals"][0] == original
    assert revised["supersedes_proposal_id"] == original["id"]
    assert revised["patch"]["upsert_items"] == original["patch"]["upsert_items"]
    response = client.post(path + f"/proposals/{revised['id']}/decision", json={"expected_version":session["version"], "decision":"adopt"})
    assert response.status_code == 200, response.text
    workspace = response.json()["session"]["workspace"]
    assert workspace["items"][0]["id"] == "cause"
    assert workspace["scene_cards"][0]["title"] == "雨夜相遇修订"
    assert workspace["scene_cards"][0]["status"] == "approved"



def test_revision_rejects_changed_input_canon_language_and_foreign_proposal():
    import pytest
    from storygraph.core.errors import ContractError
    from storygraph.models.authoring import AuthoringPatch, AuthoringSourcePin
    from storygraph.services.canon_snapshot import content_hash
    for changed in ["inputs", "canon", "language", "foreign"]:
        service, session, original_id = _pending_revision_fixture()
        if changed == "inputs":
            service.source_resolver = lambda pid, pin: "新选择的资料。"
            session.source_pins = [AuthoringSourcePin(kind="source_document", id="new-source", sha256=content_hash("新选择的资料。"))]
        elif changed == "canon":
            service.canon_resolver = lambda pid: {"fingerprint":"a" * 64}
        elif changed == "language":
            service.project_language_resolver = lambda pid: "en-US"
        else:
            session = service.create(project_id="foreign", content_language="zh-CN", title="其他作品", idea="另一作品。")
        before = session.model_dump(mode="json")
        with pytest.raises(ContractError):
            service._revise_proposal(session, original_id, AuthoringPatch(), "不能偷偷改绑基线。")
        assert session.model_dump(mode="json") == before


def test_actual_wire_partial_card_revision_preserves_entire_unmentioned_card():
    import copy
    from storygraph.models.authoring import AuthoringPatch
    from test_authoring_service import FakeProvider, finish, item, make_service
    from test_api_authoring_sessions import fixture_card
    provider = FakeProvider()
    service, session = make_service(provider)
    complete = fixture_card()
    complete.update(depends_on=["truth"], target_length=800,
        entry_knowledge=[{"character_id":"xia", "text":"她进场相信姐姐会出现。", "item_id":"truth"}],
        intended_actions=[{"character_id":"xia", "intention":"在站台等待姐姐。", "depends_on":["truth"]}],
        acquisitions=[{"character_id":"xia", "text":"场景中听见发车铃声。"}])
    complete["writer_policy"]["expected_reader_inference"] = "姐姐的意图尚未确定。"
    base = service._propose(session, AuthoringPatch(upsert_items=[item("truth")], upsert_scene_cards=[complete]), "保存完整场景待审设计。")
    session = service._save(session)
    original = service.get_proposal("project", session.id, base["proposal_id"])
    before = original.patch.upsert_scene_cards[0].model_dump(mode="json")
    claims = [{"text":"姐姐可能骗了我。", "presentation":"belief", "phase":"during_scene", "character_id":"xia"}]
    # Actual model wire omits all optional card fields and nonrequired policy fields.
    wire_card = {"id":before["id"], "title":before["title"], "writer_policy":{
        "access_mode":"pov", "surface_plan":before["writer_policy"]["surface_plan"],
        "writer_style":{}, "visible_claims":claims}}
    provider.actions = [{"tool":"revise_proposal", "args":{"proposal_id":original.id, "summary":"仅修正信念出现阶段。", "patch":{"upsert_scene_cards":[wire_card]}}}, finish()]
    revised_session = service.turn(project_id="project", session_id=session.id, expected_version=session.version, message="只修正信念phase，其余完整保留。", max_steps=2)
    after = revised_session.proposals[-1].patch.upsert_scene_cards[0].model_dump(mode="json")
    expected = copy.deepcopy(before)
    expected["writer_policy"]["visible_claims"] = claims
    assert after == expected  # Every card, policy and nested style field must be retained.
    assert revised_session.workspace == session.workspace
    assert service.get_proposal("project", session.id, original.id).model_dump(mode="json") == original.model_dump(mode="json")



def test_completed_format_repair_is_once_and_within_original_call_budget():
    import pytest
    from storygraph.core.errors import ModelOutputError
    from storygraph.services.llm_provider import ProviderError
    from test_authoring_service import FakeProvider, finish, make_service
    provider = FakeProvider(ProviderError("invalid_response", outcome_known=True), finish())
    service, session = make_service(provider)
    saved = service.turn(project_id="project", session_id=session.id, expected_version=1, message="继续设计。", max_steps=2)
    assert len(provider.requests) == saved.turn_calls_started == 2
    assert saved.turn_status == "idle"
    assert sum(m.tool_name == "format_diagnostic" for m in saved.messages) == 1
    assert "format_diagnostic" in provider.requests[1].messages[-1].content
    provider = FakeProvider({"tool":"unknown"}, {"tool":"unknown"}, finish())
    service, session = make_service(provider)
    with pytest.raises(ModelOutputError):
        service.turn(project_id="project", session_id=session.id, expected_version=1, message="继续设计。", max_steps=8)
    assert len(provider.requests) == service.get("project", session.id).turn_calls_started == 2


def test_transport_auth_rate_errors_never_use_completed_format_repair():
    import pytest
    from storygraph.services.llm_provider import ProviderError
    from test_authoring_service import FakeProvider, finish, make_service
    for category, known in [("connection_error",False),("rate_limit",True),("invalid_credentials",True),("request_failed",False)]:
        provider = FakeProvider(ProviderError(category, outcome_known=known), finish())
        service, session = make_service(provider)
        with pytest.raises(ProviderError):
            service.turn(project_id="project", session_id=session.id, expected_version=1, message="继续设计。", max_steps=8)
        saved = service.get("project", session.id)
        assert len(provider.requests) == saved.turn_calls_started == 1
        assert saved.turn_status == ("failed" if known else "unknown")
        assert not any(m.tool_name == "format_diagnostic" for m in saved.messages)


def test_format_repair_does_not_replay_saved_proposal():
    from test_authoring_service import FakeProvider, finish, make_service, item
    provider = FakeProvider({"tool":"propose_workspace", "args":{"summary":"待审设计。", "patch":{"upsert_items":[item()]}}}, {"tool":"bad"}, finish())
    service, session = make_service(provider)
    saved = service.turn(project_id="project", session_id=session.id, expected_version=1, message="提出方案后总结。", max_steps=3)
    assert len(provider.requests) == saved.turn_calls_started == 3
    assert len(saved.proposals) == 1 and saved.proposals[0].status == "pending"
    assert len([m for m in saved.messages if m.tool_name == "propose_workspace"]) == 1
    assert saved.workspace.items == []


def test_format_repair_capacity_is_shared_by_both_character_failures():
    import pytest
    from storygraph.core.errors import ModelOutputError
    from test_authoring_service import FakeProvider, finish, make_service
    simulation = {"tool":"simulate_character", "args":{"character_id":"actor", "question_kind":"next_action"}}
    provider = FakeProvider(simulation, {"bad":"PRIVATE_RESPONSE_CANARY"}, simulation, {"bad":"SECOND_PRIVATE_CANARY"}, finish())
    service, session = make_service(provider)
    with pytest.raises(ModelOutputError):
        service.turn(project_id="project", session_id=session.id, expected_version=1, message="推演角色。", max_steps=8)
    saved = service.get("project", session.id)
    assert len(provider.requests) == saved.turn_calls_started == 4
    assert saved.turn_status == "failed" and saved.proposals == []
    assert all("PRIVATE_RESPONSE_CANARY" not in m.content and "SECOND_PRIVATE_CANARY" not in m.content for m in saved.messages)


def test_format_correction_never_swallows_new_source_canon_or_session_conflicts():
    import pytest
    from storygraph.core.errors import ContractError
    from storygraph.models.authoring import AuthoringSourcePin
    from storygraph.services.canon_snapshot import content_hash
    from test_authoring_service import FakeProvider, finish, make_service
    for changed in ["source", "canon", "session"]:
        source = ["最初资料。"]
        canon = ["最初正典。"]
        provider = FakeProvider({"tool":"bad"})
        service, session = make_service(provider, source_resolver=lambda pid,pin:source[0], canon_resolver=lambda pid:{"fingerprint":content_hash(canon[0])})
        if changed == "source":
            session.source_pins=[AuthoringSourcePin(kind="source_document", id="pin", sha256=content_hash(source[0]))]
            session=service._save(session)
        def concurrent_change():
            if changed == "source":
                source[0]="作者刚改过资料。"
            elif changed == "canon":
                canon[0]="作者刚审阅新正典。"
            else:
                latest=service.get("project",session.id)
                latest.title="另一请求刚保存的标题"
                service._save(latest)
            return finish("不应该保存的修正结果。")
        provider.actions += [concurrent_change, finish()]
        with pytest.raises(ContractError):
            service.turn(project_id="project", session_id=session.id, expected_version=session.version, message="继续设计。", max_steps=8)
        saved=service.get("project",session.id)
        assert len(provider.requests)==saved.turn_calls_started==2
        assert all(m.content!="不应该保存的修正结果。" for m in saved.messages)
        if changed=="session":
            assert saved.title=="另一请求刚保存的标题"


def _exact_evidence_fixture():
    from storygraph.models.authoring import AuthoringWorkspace, AuthoringDraftPin
    from storygraph.models.draft import Draft
    from storygraph.services.canon_snapshot import content_hash
    from test_authoring_service import FakeProvider, make_service
    from test_api_authoring_sessions import fixture_card
    draft=Draft(id="exact-draft",project_id="project",scene_id="scene",version=1,text="😀她看见新锁。她看见新锁。",content_language="zh-CN",created_at="now",updated_at="now")
    provider=FakeProvider()
    service,session=make_service(provider,draft_resolver=lambda pid,pin:draft)
    complete=fixture_card()
    complete.update(scene_id="scene",status="approved",depends_on=[],target_length=800, acquisitions=[{"character_id":"xia","text":"原先保留的计划获知。"}], entry_knowledge=[{"character_id":"xia","text":"她入场仍相信姐姐会来。"}])
    session.workspace=AuthoringWorkspace(scene_cards=[complete])
    session=service._save(session)
    pin=AuthoringDraftPin(draft_id=draft.id,scene_id=draft.scene_id,version=draft.version,text_sha256=content_hash(draft.text))
    return service,session,provider,draft,pin


def test_actual_wire_exact_draft_evidence_uses_real_quote_ref_and_preserves_all_design():
    import copy
    import json
    from test_authoring_service import finish
    service,session,provider,draft,pin=_exact_evidence_fixture()
    before=session.workspace.model_dump(mode="json")
    captured={}
    def select_actual_second_match():
        trace=provider.requests[-1].messages[-1].content
        actual=json.loads(trace.removeprefix("Tool result: "))
        match=actual["matches"][1]
        captured.update(match)
        return {"tool":"propose_draft_evidence","args":{"summary":"只记录已写出的新锁。","acquisitions":[{"character_id":"xia","text":"她在场景中看到新锁。","quote_refs":[match["quote_ref"]]}],"reader_records":[{"quote_ref":match["quote_ref"],"presentation":"narration"}]}}
    provider.actions=[{"tool":"read_source","args":{"kind":"draft","id":draft.id}}, {"tool":"search_source","args":{"kind":"draft","id":draft.id,"query":"新锁"}}, select_actual_second_match, finish()]
    saved=service.reconcile(project_id="project",session_id=session.id,expected_version=session.version,draft_pin=pin.model_dump(mode="json"),card_id="first_card",card_version=1,max_steps=4)
    assert len(provider.requests)==saved.turn_calls_started==4
    assert saved.workspace.model_dump(mode="json")==before
    proposal=saved.proposals[-1]
    assert proposal.status=="pending" and len(proposal.patch.upsert_scene_cards)==1
    revised=proposal.patch.upsert_scene_cards[0].model_dump(mode="json")
    expected=copy.deepcopy(before["scene_cards"][0])
    expected["status"]="proposed"
    expected["version"]=2
    expected["acquisitions"].append({"character_id":"xia","text":"她在场景中看到新锁。","item_id":None,"evidence":[{"draft":pin.model_dump(mode="json"),"start":captured["match_start"],"end":captured["match_end"],"expected_text":"新锁","offset_unit":"utf16"}]})
    assert revised==expected
    record=proposal.patch.add_reader_records[0]
    assert (record.draft_id,record.version,record.text_sha256)==(draft.id,draft.version,pin.text_sha256)
    assert (record.start,record.end,record.expected_text)==(captured["match_start"],captured["match_end"],"新锁")
    assert record.start==len("😀她看见新锁。她看见".encode("utf-16-le"))//2


def test_evidence_tool_rejects_forged_prior_turn_and_outside_reconcile_refs():
    import json
    import pytest
    from storygraph.core.errors import ContractError
    from test_authoring_service import finish
    for scenario in ["forged","prior_turn","not_reconciliation"]:
        service,session,provider,draft,pin=_exact_evidence_fixture()
        ref="q_forged123456"
        if scenario=="prior_turn":
            provider.actions=[{"tool":"read_source","args":{"kind":"draft","id":draft.id}}, {"tool":"search_source","args":{"kind":"draft","id":draft.id,"query":"新锁"}}]
            session=service.reconcile(project_id="project",session_id=session.id,expected_version=session.version,draft_pin=pin.model_dump(mode="json"),card_id="first_card",card_version=1,max_steps=2)
            trace=json.loads(next(m.content for m in session.messages if m.tool_name=="search_source"))
            ref=trace["result"]["matches"][0]["quote_ref"]
        provider.actions=[{"tool":"read_source","args":{"kind":"draft","id":draft.id}}, {"tool":"propose_draft_evidence","args":{"summary":"试图使用无效引用。","reader_records":[{"quote_ref":ref,"presentation":"narration"}]}}, finish()]
        before=len(provider.requests)
        with pytest.raises(ContractError):
            if scenario=="not_reconciliation":
                session.draft_pins=[pin]
                session=service._save(session)
                service.turn(project_id="project",session_id=session.id,expected_version=session.version,message="普通设计讨论不能写回查记录。",max_steps=3)
            else:
                service.reconcile(project_id="project",session_id=session.id,expected_version=session.version,draft_pin=pin.model_dump(mode="json"),card_id="first_card",card_version=1,max_steps=3)
        saved=service.get("project",session.id)
        assert len(provider.requests)-before==2 and saved.proposals==[]
        assert saved.workspace==session.workspace


def test_evidence_ref_cannot_certify_changed_draft_or_unowned_actor():
    import json
    import pytest
    from storygraph.core.errors import ContractError
    from test_authoring_service import finish
    for scenario in ["changed_draft","foreign_actor"]:
        service,session,provider,draft,pin=_exact_evidence_fixture()
        def propose_from_match():
            result=json.loads(provider.requests[-1].messages[-1].content.removeprefix("Tool result: "))
            ref=result["matches"][0]["quote_ref"]
            if scenario=="changed_draft":
                draft.text="作者刚改写了原正文。"
            return {"tool":"propose_draft_evidence","args":{"summary":"核对角色获知。","acquisitions":[{"character_id":"foreign-actor" if scenario=="foreign_actor" else "xia","text":"看到新锁。","quote_refs":[ref]}]}}
        provider.actions=[{"tool":"read_source","args":{"kind":"draft","id":draft.id}}, {"tool":"search_source","args":{"kind":"draft","id":draft.id,"query":"新锁"}}, propose_from_match, finish()]
        with pytest.raises(ContractError):
            service.reconcile(project_id="project",session_id=session.id,expected_version=session.version,draft_pin=pin.model_dump(mode="json"),card_id="first_card",card_version=1,max_steps=4)
        saved=service.get("project",session.id)
        assert len(provider.requests)==3 and saved.proposals==[]
        assert saved.workspace==session.workspace



def test_other_selected_draft_search_cannot_issue_reconciliation_quote_ref():
    import json
    import pytest
    from storygraph.core.errors import ContractError
    from storygraph.models.authoring import AuthoringDraftPin
    from storygraph.services.canon_snapshot import content_hash
    from test_authoring_service import finish
    service,session,provider,draft,pin=_exact_evidence_fixture()
    other=draft.model_copy(update={"id":"another-draft","scene_id":"other-scene"})
    other_pin=AuthoringDraftPin(draft_id=other.id,scene_id=other.scene_id,version=other.version,text_sha256=content_hash(other.text))
    service.draft_resolver=lambda pid,p:draft if p.draft_id==draft.id else other
    session.draft_pins=[pin,other_pin]
    session=service._save(session)
    def after_foreign_search():
        result=json.loads(provider.requests[-1].messages[-1].content.removeprefix("Tool result: "))
        assert result["matches"] and all("quote_ref" not in match for match in result["matches"])
        return {"tool":"propose_draft_evidence","args":{"summary":"不能用另一正文作证。","reader_records":[{"quote_ref":"q_not-issued-for-other-draft","presentation":"clue"}]}}
    provider.actions=[{"tool":"read_source","args":{"kind":"draft","id":draft.id}},{"tool":"search_source","args":{"kind":"draft","id":other.id,"query":"新锁"}},after_foreign_search,finish()]
    with pytest.raises(ContractError):
        service.reconcile(project_id="project",session_id=session.id,expected_version=session.version,draft_pin=pin.model_dump(mode="json"),card_id="first_card",card_version=1,max_steps=4)
    assert len(provider.requests)==3 and service.get("project",session.id).proposals==[]


def test_framework_reconcile_preread_is_exact_current_draft_and_first_call_is_batch():
    import json
    from test_authoring_service import finish
    service,session,provider,draft,pin=_exact_evidence_fixture()
    from storygraph.core.agent_config import ModelExecution
    service.model_execution=ModelExecution(profile_id="fixture",profile_name="Fixture",protocol="chat_completions",model="fake",task="discussion")
    provider.actions=[{"tool":"search_draft_quotes","args":{"quotes":["新锁"]}},finish()]
    saved=service.reconcile(project_id="project",session_id=session.id,expected_version=session.version,draft_pin=pin.model_dump(mode="json"),card_id="first_card",card_version=1,max_steps=2)
    assert len(provider.requests)==saved.turn_calls_started==2
    first_context=json.loads(provider.requests[0].messages[1].content)
    actual=first_context["reconciliation_read"]
    assert actual["pin"]==pin.model_dump(mode="json")
    assert actual["text"]==draft.text and actual["start"]==0
    assert actual["end"]==len(draft.text.encode("utf-16-le"))//2 and not actual["more"]
    framework=[m for m in saved.messages if m.tool_name=="read_source" and json.loads(m.content).get("initiated_by")=="framework"]
    assert len(framework)==1 and framework[0].model_execution is None
    assert json.loads(framework[0].content)["result"]==actual
    trace=json.loads(next(m.content for m in saved.messages if m.tool_name=="search_draft_quotes"))
    assert trace["result"]["quotes"][0]["matches"][0]["quote_ref"]



def test_framework_preread_long_page_has_honest_more_and_does_not_read_other_pin():
    import json
    from storygraph.models.authoring import AuthoringDraftPin
    from storygraph.services.canon_snapshot import content_hash
    from test_authoring_service import finish
    service,session,provider,draft,pin=_exact_evidence_fixture()
    draft.text="甲😀"*5000+"未预读尾部CANARY"
    pin=pin.model_copy(update={"text_sha256":content_hash(draft.text)})
    other=draft.model_copy(update={"id":"other-draft","scene_id":"other-scene","text":"OTHER_DRAFT_PRIVATE_BODY_CANARY"})
    other_pin=AuthoringDraftPin(draft_id=other.id,scene_id=other.scene_id,version=1,text_sha256=content_hash(other.text))
    service.draft_resolver=lambda pid,p:draft if p.draft_id==draft.id else other
    session.draft_pins=[pin,other_pin]
    session=service._save(session)
    provider.actions=[finish()]
    saved=service.reconcile(project_id="project",session_id=session.id,expected_version=session.version,draft_pin=pin.model_dump(mode="json"),card_id="first_card",card_version=1,max_steps=1)
    context=json.loads(provider.requests[0].messages[1].content)
    page=context["reconciliation_read"]
    assert page["more"] and not page["complete"]
    assert page["start"]==0 and page["next_start"]==page["end"]<page["total_utf16"]
    assert page["text"]==draft.text.encode("utf-16-le")[:page["end"]*2].decode("utf-16-le")
    assert page["end"]<=12000 and "未预读尾部CANARY" not in page["text"]
    assert all("OTHER_DRAFT_PRIVATE_BODY_CANARY" not in m.content for m in provider.requests[0].messages)
    assert len(provider.requests)==saved.turn_calls_started==1


def test_framework_preread_rechecks_source_before_any_paid_call(monkeypatch):
    import pytest
    from storygraph.core.errors import ContractError
    from test_authoring_service import finish
    service,session,provider,draft,pin=_exact_evidence_fixture()
    original=service._read_source_page
    def changed_after_local_read(*args,**kwargs):
        page=original(*args,**kwargs)
        draft.text="作者在预读完成后立即改写正文。"
        return page
    monkeypatch.setattr(service,"_read_source_page",changed_after_local_read)
    provider.actions=[finish()]
    with pytest.raises(ContractError,match="draft_stale"):
        service.reconcile(project_id="project",session_id=session.id,expected_version=session.version,draft_pin=pin.model_dump(mode="json"),card_id="first_card",card_version=1,max_steps=8)
    saved=service.get("project",session.id)
    assert provider.requests==[] and saved.turn_calls_started==0 and saved.proposals==[]



def test_ordinary_propose_actual_wire_existing_card_goal_preserves_all_saved_metadata_and_evidence():
    import copy
    from test_authoring_service import finish
    service,session,provider,draft,pin=_exact_evidence_fixture()
    card=session.workspace.scene_cards[0]
    session.draft_pins=[pin]
    from storygraph.models.authoring import AuthoringEvidence
    card.acquisitions[-1].evidence=[AuthoringEvidence(draft=pin,start=2,end=3,expected_text="她",offset_unit="utf16")]
    # Materialize synthetic exact evidence and make it part of the saved baseline.
    from storygraph.models.authoring import AuthoringWorkspace
    session.workspace=AuthoringWorkspace.model_validate(session.workspace.model_dump(mode="json"))
    session=service._save(session)
    before=session.workspace.scene_cards[0].model_dump(mode="json")
    wire_card={"id":before["id"],"title":before["title"],"goal":"作者改为先确认姐姐是否愿意谈。","writer_policy":{"access_mode":before["writer_policy"]["access_mode"],"surface_plan":before["writer_policy"]["surface_plan"],"writer_style":{}}}
    provider.actions=[{"tool":"propose_workspace","args":{"summary":"只改变当前目标。","patch":{"upsert_scene_cards":[wire_card]}}},finish()]
    saved=service.turn(project_id="project",session_id=session.id,expected_version=session.version,message="只改场景目标，其余设计保留。",max_steps=2)
    after=saved.proposals[-1].patch.upsert_scene_cards[0].model_dump(mode="json")
    expected=copy.deepcopy(before)
    expected.update(goal=wire_card["goal"],status="proposed",version=before["version"]+1)
    assert after==expected
    assert saved.workspace.scene_cards[0].model_dump(mode="json")==before
    assert saved.proposals[-1].status=="pending"



def test_narrow_design_changes_actual_wire_updates_only_named_paths_and_preserves_belief_owner():
    import copy
    from storygraph.models.authoring import AuthoringDesignItem
    from test_authoring_service import finish
    service,session,provider,draft,pin=_exact_evidence_fixture()
    session.workspace.items=[AuthoringDesignItem(id="belief",kind="character_belief",status="author_decided",character_id="xia",text="她原先相信信仍在抽屉。")]
    session=service._save(session)
    before=session.workspace.model_dump(mode="json")
    provider.actions=[{"tool":"propose_design_changes","args":{"summary":"只调整作者明确指定的路径。","changes":[{"target_type":"item","target_id":"belief","fields":{"text":"她现在只是怀疑信也许还在抽屉。"}},{"target_type":"scene_card","target_id":"first_card","fields":{"goal":"她只凭记忆询问，不带锁。","author_summary":"她凭记忆询问，停在回答之前。","writer_policy":{"expected_reader_inference":"读者只见她凭记忆提问。"}}}]}},finish()]
    saved=service.turn(project_id="project",session_id=session.id,expected_version=session.version,message="只改指定处，等我审阅。",max_steps=2)
    proposal=saved.proposals[-1]
    expected=copy.deepcopy(before["scene_cards"][0])
    expected.update(goal="她只凭记忆询问，不带锁。",author_summary="她凭记忆询问，停在回答之前。",status="proposed",version=2)
    expected["writer_policy"]["expected_reader_inference"]="读者只见她凭记忆提问。"
    assert proposal.patch.upsert_scene_cards[0].model_dump(mode="json")==expected
    expected_item=copy.deepcopy(before["items"][0])
    expected_item["text"]="她现在只是怀疑信也许还在抽屉。"
    assert proposal.patch.upsert_items[0].model_dump(mode="json")==expected_item
    assert saved.workspace.model_dump(mode="json")==before and proposal.status=="pending"
    assert len(provider.requests)==saved.turn_calls_started==2


def test_narrow_design_changes_wire_rejects_new_identity_protected_binding_and_reconcile():
    import pytest
    from storygraph.core.errors import ContractError
    for scenario in ["new_identity","protected_binding","reconcile"]:
        service,session,provider,draft,pin=_exact_evidence_fixture()
        fields={"scene_id":"foreign-scene"} if scenario=="protected_binding" else {"goal":"只应形成待审改动。"}
        provider.actions=[{"tool":"propose_design_changes","args":{"summary":"不得绕过既定范围。","changes":[{"target_type":"scene_card","target_id":"new-card" if scenario=="new_identity" else "first_card","fields":fields}]}}]
        before=session.workspace.model_dump(mode="json")
        with pytest.raises(ContractError):
            if scenario=="reconcile":
                service.reconcile(project_id="project",session_id=session.id,expected_version=session.version,draft_pin=pin,card_id="first_card",card_version=1,max_steps=1)
            else:
                service.turn(project_id="project",session_id=session.id,expected_version=session.version,message="核对范围。",max_steps=1)
        saved=service.get("project",session.id)
        assert saved.workspace.model_dump(mode="json")==before and saved.proposals==[]
        assert len(provider.requests)==1



def test_actual_wire_card_review_preserves_full_snapshot_and_human_adopt_really_approves():
    import copy
    from test_authoring_service import finish
    service,session,provider,draft,pin=_exact_evidence_fixture()
    session.workspace.scene_cards[0].status="proposed"
    from storygraph.models.authoring import AuthoringEvidence
    session.draft_pins=[pin]
    session.workspace.scene_cards[0].acquisitions[0].evidence=[AuthoringEvidence(draft=pin,start=2,end=3,expected_text="她")]
    session=service._save(session)
    before=session.workspace.scene_cards[0].model_dump(mode="json")
    provider.actions=[{"tool":"propose_card_review","args":{"summary":"重新核对完整场景卡，保持所有创作内容。","card_ids":["first_card"]}},finish()]
    saved=service.turn(project_id="project",session_id=session.id,expected_version=session.version,message="重新审阅这张场景卡。",max_steps=2)
    assert saved.workspace==session.workspace and len(saved.proposals)==1
    proposal=saved.proposals[0]
    patch=proposal.patch.model_dump(mode="json")
    for key,value in patch.items():
        if key!="upsert_scene_cards":
            assert value==[]
    snapshot=patch["upsert_scene_cards"][0]
    expected=copy.deepcopy(before)
    expected.update(status=snapshot["status"],version=snapshot["version"])
    assert snapshot==expected and snapshot["status"]=="proposed"
    approved=service.review(project_id="project",session_id=session.id,expected_version=saved.version,proposal_id=proposal.id,decision="adopted")
    actual=approved.workspace.scene_cards[0].model_dump(mode="json")
    expected.update(status="approved",version=actual["version"])
    assert actual==expected


def test_new_empty_proposal_uses_only_one_existing_correction_budget_and_creates_no_fake_review():
    import pytest
    from storygraph.core.errors import ContractError
    from test_authoring_service import finish
    empty={"tool":"propose_workspace","args":{"summary":"不应伪装成卡片复核的空提案。","patch":{}}}
    service,session,provider,draft,pin=_exact_evidence_fixture()
    provider.actions=[empty,{"tool":"propose_card_review","args":{"summary":"明确复核原场景。","card_ids":["first_card"]}},finish()]
    saved=service.turn(project_id="project",session_id=session.id,expected_version=session.version,message="保持设计，重新核对卡片。",max_steps=3)
    assert len(provider.requests)==saved.turn_calls_started==3
    assert len(saved.proposals)==1 and saved.proposals[0].patch.upsert_scene_cards
    assert len([m for m in saved.messages if m.tool_name=="format_correction"])==1
    provider.actions=[empty,empty,finish()]
    before=len(provider.requests)
    with pytest.raises(ContractError):
        service.turn(project_id="project",session_id=session.id,expected_version=saved.version,message="不能重复空提案。",max_steps=8)
    latest=service.get("project",session.id)
    assert len(provider.requests)-before==latest.turn_calls_started==2
    assert len(latest.proposals)==1


def test_historical_empty_proposal_remains_readable_and_rejectable():
    from storygraph.models.authoring import AuthoringProposal,AuthoringPatch
    from storygraph.services.authoring import workspace_hash
    service,session,provider,draft,pin=_exact_evidence_fixture()
    legacy=AuthoringProposal(id="legacy-empty",base_workspace_sha256=workspace_hash(session.workspace),patch=AuthoringPatch(),summary="历史空提案。",created_at="now")
    session.proposals.append(legacy)
    session=service._save(session)
    found=service.get_proposal("project",session.id,legacy.id)
    assert found.patch==AuthoringPatch() and found.status=="pending"
    saved=service.review(project_id="project",session_id=session.id,expected_version=session.version,proposal_id=legacy.id,decision="rejected")
    assert saved.workspace==session.workspace
    assert service.get_proposal("project",session.id,legacy.id).status=="rejected"



def test_card_review_rejects_unknown_foreign_and_duplicate_ids_before_any_fake_review():
    import pytest
    from storygraph.core.errors import ContractError
    from pydantic import ValidationError
    from storygraph.models.authoring import AuthoringToolAction
    for ids in [["missing"],["foreign-card"],["first_card","first_card"],[]]:
        service,session,provider,draft,pin=_exact_evidence_fixture()
        before=session.workspace.model_dump(mode="json")
        with pytest.raises((ContractError,ValidationError)):
            action=AuthoringToolAction.model_validate({"tool":"propose_card_review","args":{"summary":"不能复核无归属或重复卡。","card_ids":ids}})
            service._tool(session,action)
        assert session.workspace.model_dump(mode="json")==before and session.proposals==[]
