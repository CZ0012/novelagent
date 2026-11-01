"""No-network tests of the main agent's noncanon tool and approval boundaries."""
import json

import pytest

from storygraph.core.errors import ContractError, ModelOutputError
from storygraph.models.authoring import AuthoringWorkspace, AuthoringPatch, AuthoringDraftPin, AuthoringToolAction
from storygraph.models.draft import Draft
from storygraph.services.authoring import AuthoringService, apply_authoring_patch
from storygraph.services.canon_snapshot import content_hash
from storygraph.services.llm_provider import LLMResponse, ProviderError
from storygraph.stores.authoring_store import SQLiteAuthoringStore
from storygraph.stores.proposal_store import SQLiteProposalStore


class FakeProvider:
    def __init__(self, *actions):
        self.actions, self.requests = list(actions), []

    def generate(self, request):
        self.requests.append(request)
        action = self.actions.pop(0)
        if isinstance(action, Exception):
            raise action
        if callable(action):
            action = action()
        return LLMResponse(json.dumps(action, ensure_ascii=False))


def make_service(provider=None, **kwargs):
    store = SQLiteAuthoringStore(SQLiteProposalStore())
    service = AuthoringService(store=store, provider=provider, model="fake", **kwargs)
    session = service.create(project_id="project", content_language="zh-CN", title="协作", idea="一个人发现过去的自己在撒谎。")
    return service, session


def finish(message="我们先确定主角隐瞒的动机，再设计第一场冲突。"):
    return {"tool": "finish", "args": {"message": message}}


def item(item_id="truth", **kwargs):
    return {"id": item_id, "kind": "world_fact", "status": "open", "text": "钟楼的钟在午夜停摆。", **kwargs}


def card(card_id="card", **kwargs):
    return {"id": card_id, "title": "钟楼相遇", "scene_id": "scene", "depends_on": ["truth"],
            "writer_policy": {"access_mode": "surface", "surface_plan": {"kind": "literal", "text": "两人在钟楼相遇。"}, "writer_style": {}}, **kwargs}


def test_idea_only_session_tool_loop_proposes_without_mutating_workspace():
    provider = FakeProvider({"tool": "inspect_canon", "args": {}},
        {"tool": "propose_workspace", "args": {"summary": "先保留这个可能性。", "patch": {"upsert_items": [item()]}}}, finish())
    service, session = make_service(provider)
    result = service.turn(project_id="project", session_id=session.id, expected_version=1, message="先设计原因。")
    assert result.workspace.items == []
    assert result.proposals[0].status == "pending"
    assert [m.tool_name for m in result.messages if m.role == "tool"] == ["inspect_canon", "propose_workspace"]
    assert len(provider.requests) == 3
    assert result.turn_status == "idle"
    adopted = service.review(project_id="project", session_id=session.id, expected_version=result.version,
        proposal_id=result.proposals[0].id, decision="adopted")
    assert adopted.workspace.items[0].status == "open"
    assert adopted.proposals[0].reviewed_by == "author"
    assert len(service.store.history("project", session.id)) >= 5


def test_patch_preserves_unrelated_records_and_refuses_missing_removal():
    workspace = AuthoringWorkspace(items=[item("a"), item("b")])
    result = apply_authoring_patch(workspace, AuthoringPatch(upsert_items=[item("a", text="新的线索。")]))
    assert result.items[1] == workspace.items[1]
    with pytest.raises(ContractError, match="remove_missing"):
        apply_authoring_patch(workspace, AuthoringPatch(remove_item_ids=["missing"]))


def test_project_scope_and_stale_cas_no_provider_call():
    provider = FakeProvider(finish())
    service, session = make_service(provider)
    with pytest.raises(ContractError, match="not_found"):
        service.get("other", session.id)
    with pytest.raises(ContractError, match="stale_version"):
        service.turn(project_id="project", session_id=session.id, expected_version=0, message="继续。")
    assert provider.requests == []


def test_reservation_blocks_concurrent_duplicate_before_paid_call():
    service, session = make_service()
    def inside_call():
        running = service.get("project", session.id)
        assert running.turn_status == "running"
        with pytest.raises(ContractError, match="turn_running"):
            service.turn(project_id="project", session_id=session.id, expected_version=running.version, message="重复。")
        with pytest.raises(ContractError, match="still_active"):
            service.recover_turn(project_id="project", session_id=session.id, expected_version=running.version)
        return finish()
    service.provider = FakeProvider(inside_call)
    service.turn(project_id="project", session_id=session.id, expected_version=1, message="开始。")
    assert len(service.provider.requests) == 1


def test_provider_unknown_is_durable_and_does_not_retry_or_leak_raw_error():
    service, session = make_service(FakeProvider(ProviderError("connection_error", outcome_known=False)))
    with pytest.raises(ProviderError):
        service.turn(project_id="project", session_id=session.id, expected_version=1, message="继续。")
    saved = service.get("project", session.id)
    assert saved.turn_status == "unknown"
    assert saved.turn_error_category == "connection_error"
    assert len(service.provider.requests) == 1


def test_strict_tool_shape_failure_preserves_reservation_failure():
    service, session = make_service(FakeProvider({"tool": "read_source", "args": {"id": "x", "kind": "draft", "path": "secret"}}))
    with pytest.raises(ModelOutputError):
        service.turn(project_id="project", session_id=session.id, expected_version=1, message="继续。", max_steps=1)
    assert service.get("project", session.id).turn_status == "failed"


def test_bounded_step_count_persists_trace():
    service, session = make_service(FakeProvider({"tool": "inspect_sources", "args": {}}))
    result = service.turn(project_id="project", session_id=session.id, expected_version=1, message="继续。", max_steps=1)
    assert result.turn_status == "idle"
    assert len(service.provider.requests) == 1
    assert any(m.tool_name == "inspect_sources" for m in result.messages)


def test_character_view_excludes_global_truth_and_other_actor():
    service, session = make_service()
    session.workspace = AuthoringWorkspace(items=[item("secret", kind="true_cause", text="凶手是王后。"),
        item("belief", kind="character_belief", character_id="a", text="我以为国王在说谎。", rationale="凶手是王后。"),
        item("other", kind="character_belief", character_id="b", text="我知道凶手是王后。")])
    view = service.character_view(session, "a")
    text = json.dumps(view, ensure_ascii=False)
    assert "王后" not in text
    assert "我以为国王在说谎" in text


def test_pinned_source_stale_and_foreign_ids_refused():
    service, session = make_service(source_resolver=lambda project, pin: "准确原文。")
    with pytest.raises(ContractError, match="source_stale"):
        service.create(project_id="project", content_language="zh-CN", title="测试", idea="想法。",
            source_pins=[{"kind": "source_document", "id": "s", "sha256": content_hash("别的原文。 ")}])
    with pytest.raises(ContractError, match="source_not_pinned"):
        service._tool(session, AuthoringToolAction(
            tool="read_source", args={"id": "foreign", "kind": "source_document"}))


def draft_fixture():
    text = "阿林看见红灯，知道门已经锁上。"
    draft = Draft(id="d", project_id="project", scene_id="scene", version=2, text=text,
                  content_language="zh-CN", created_at="now", updated_at="now")
    pin = AuthoringDraftPin(scene_id="scene", draft_id="d", version=2, text_sha256=content_hash(text))
    return draft, pin


def test_reader_evidence_exact_saved_draft_utf16_and_scope():
    draft, pin = draft_fixture()
    service, session = make_service(draft_resolver=lambda project, p: draft)
    session.draft_pins.append(pin)
    record = {"draft_id": "d", "version": 2, "text_sha256": pin.text_sha256, "start": 0, "end": 2,
              "expected_text": "阿林", "presentation": "narration"}
    service._validate_workspace(session, AuthoringWorkspace(reader_records=[record]))
    with pytest.raises(ContractError):
        service._validate_workspace(session, AuthoringWorkspace(reader_records=[{**record, "expected_text": "王后"}]))
    with pytest.raises(ContractError, match="unpinned"):
        service._validate_workspace(session, AuthoringWorkspace(reader_records=[{**record, "version": 1}]))


def test_failed_tool_after_success_keeps_prior_trace():
    service, session = make_service(FakeProvider({"tool": "inspect_sources", "args": {}},
        {"tool": "read_source", "args": {"id": "foreign", "kind": "outline"}}))
    with pytest.raises(ContractError, match="source_not_pinned"):
        service.turn(project_id="project", session_id=session.id, expected_version=1, message="继续。")
    saved = service.get("project", session.id)
    assert saved.turn_status == "failed"
    assert any(m.tool_name == "inspect_sources" for m in saved.messages)


def test_character_simulation_fresh_wire_false_belief_canary_and_shared_budget():
    provider = FakeProvider(
        {"tool": "simulate_character", "args": {"character_id": "a", "question_kind": "next_action"}},
        {"options": [{"action": "去寻找国王留下的信。", "rationale": "我相信国王隐瞒了重要线索。"}], "uncertainties": []})
    service, session = make_service(provider)
    session.workspace = AuthoringWorkspace(items=[item("hidden", kind="true_cause", text="SECRET_CANARY_9472"),
        item("false", kind="character_belief", character_id="a", text="我相信国王隐瞒了重要线索。", rationale="SECRET_CANARY_9472"),
        item("other", kind="character_belief", character_id="b", text="OTHER_PRIVATE_7831")])
    session = service._save(session)
    result = service.turn(project_id="project", session_id=session.id, expected_version=session.version,
                          message="SECRET_CANARY_9472 设计人物行动。", max_steps=2)
    assert len(provider.requests) == 2
    child_wire = "\n".join(m.content for m in provider.requests[1].messages)
    assert "SECRET_CANARY_9472" not in child_wire
    assert "OTHER_PRIVATE_7831" not in child_wire
    assert "我相信国王隐瞒了重要线索。" in child_wire
    assert "rationale" in child_wire  # Output schema has rationale, input evidence does not.
    assert result.workspace == session.workspace
    assert any(m.tool_name == "simulate_character" for m in result.messages)


def test_character_simulation_does_not_call_child_without_remaining_budget():
    provider = FakeProvider({"tool": "simulate_character", "args": {"character_id": "a", "question_kind": "next_action"}})
    service, session = make_service(provider)
    result = service.turn(project_id="project", session_id=session.id, expected_version=1, message="继续。", max_steps=1)
    assert len(provider.requests) == 1
    assert "budget_exhausted" in next(m.content for m in result.messages if m.tool_name == "simulate_character")


def test_card_requires_adoption_compiles_only_policy_and_revision_demotes_dependencies():
    service, session = make_service(FakeProvider(
        {"tool": "propose_workspace", "args": {"summary": "设计钟楼场景。", "patch": {"upsert_items": [item()], "upsert_scene_cards": [card(withheld=["隐藏的真相。"])]}}}, finish()))
    result = service.turn(project_id="project", session_id=session.id, expected_version=1, message="设计场景。")
    with pytest.raises(ContractError, match="not_approved"):
        service.compile_card(project_id="project", session_id=session.id, card_id="card")
    adopted = service.review(project_id="project", session_id=session.id, expected_version=result.version,
                             proposal_id=result.proposals[0].id, decision="adopted")
    policy = service.compile_card(project_id="project", session_id=session.id, card_id="card")
    assert "隐藏的真相" not in policy.model_dump_json()
    assert adopted.workspace.scene_cards[0].status == "approved"
    service.provider = FakeProvider({"tool": "propose_workspace", "args": {"summary": "钟声时间改变，需要重审。", "patch": {"upsert_items": [item(text="钟声在清晨响起。") ]}}}, finish())
    revised = service.turn(project_id="project", session_id=session.id, expected_version=adopted.version, message="改在清晨。")
    proposal = revised.proposals[-1]
    assert proposal.affected_scene_ids == ["scene"]
    revised = service.review(project_id="project", session_id=session.id, expected_version=revised.version,
                             proposal_id=proposal.id, decision="adopted")
    assert revised.workspace.scene_cards[0].status == "proposed"
    with pytest.raises(ContractError, match="not_approved"):
        service.compile_card(project_id="project", session_id=session.id, card_id="card")


def test_model_cannot_approve_its_card():
    service, session = make_service()
    with pytest.raises(ContractError, match="cannot_approve"):
        service._propose(session, AuthoringPatch(upsert_items=[item()], upsert_scene_cards=[card(status="approved")]), "越权批准。")


def test_reconciliation_rejects_unrelated_design_changes_and_false_quotes():
    draft, pin = draft_fixture()
    service, session = make_service(draft_resolver=lambda project, p: draft)
    session.draft_pins.append(pin)
    with pytest.raises(ContractError, match="only_evidence"):
        service._validate_reconciliation_patch(session, AuthoringPatch(upsert_items=[item()]), pin)
    record = {"draft_id": "d", "version": 2, "text_sha256": pin.text_sha256, "start": 0, "end": 2,
              "expected_text": "阿林", "presentation": "narration"}
    patch = AuthoringPatch(add_reader_records=[record])
    service._validate_reconciliation_patch(session, patch, pin)
    service._propose(session, patch, "正文证据。")
    assert session.workspace.reader_records == []


def test_unknown_arbitrary_provider_exception_sanitized_and_counted():
    service, session = make_service(FakeProvider(RuntimeError("SECRET_CREDENTIAL_VALUE")))
    with pytest.raises(ProviderError) as exc:
        service.turn(project_id="project", session_id=session.id, expected_version=1, message="继续。")
    assert "SECRET_CREDENTIAL_VALUE" not in str(exc.value)
    saved = service.get("project", session.id)
    assert saved.turn_status == "unknown"
    assert saved.turn_calls_started == 1


def test_large_source_pages_and_literal_search_are_exact_and_explicit():
    text = "开场。" * 4200 + "😀线索在钟楼。" + "尾声。" * 80000
    service, _ = make_service(source_resolver=lambda project, pin: text)
    session = service.create(project_id="project", content_language="zh-CN", title="长篇来源", idea="从已有作品继续设计。",
        source_pins=[{"kind": "source_document", "id": "novel", "sha256": content_hash(text)}])
    page = service._tool(session, AuthoringToolAction(tool="read_source", args={"kind": "source_document", "id": "novel"}))
    assert page["more"] and not page["complete"]
    assert page["end"] <= 12000
    assert page["text"] == text.encode("utf-16-le")[:page["end"] * 2].decode("utf-16-le")
    found = service._tool(session, AuthoringToolAction(tool="search_source", args={"kind": "source_document", "id": "novel", "query": "线索在钟楼"}))
    assert found["total_matches"] == 1
    match = found["matches"][0]
    exact = service._tool(session, AuthoringToolAction(tool="read_source", args={"kind": "source_document", "id": "novel", "start": match["start"], "end": match["end"]}))
    assert exact["text"] == match["text"]
    with pytest.raises(ContractError, match="splits_character"):
        service._tool(session, AuthoringToolAction(tool="read_source", args={"kind": "source_document", "id": "novel", "start": 12601, "end": 12605}))
    with pytest.raises(ContractError, match="range_invalid"):
        service._tool(session, AuthoringToolAction(tool="read_source", args={"kind": "source_document", "id": "novel", "start": found["total_utf16"], "end": found["total_utf16"] + 1}))


def test_large_source_tool_loop_does_not_fail_or_treat_first_page_as_whole():
    text = "长篇作品。" * 50000
    provider = FakeProvider({"tool": "read_source", "args": {"kind": "source_document", "id": "novel"}}, finish())
    service, _ = make_service(provider, source_resolver=lambda project, pin: text)
    session = service.create(project_id="project", content_language="zh-CN", title="长篇来源", idea="从已有作品继续设计。",
        source_pins=[{"kind": "source_document", "id": "novel", "sha256": content_hash(text)}])
    result = service.turn(project_id="project", session_id=session.id, expected_version=1, message="先读开头。")
    trace = json.loads(next(m.content for m in result.messages if m.tool_name == "read_source"))
    assert trace["result"]["more"]
    assert trace["result"]["total_utf16"] == 250000
    assert result.turn_calls_started == 2


def test_explicit_recovery_of_interrupted_running_record_uses_no_provider():
    service, session = make_service(FakeProvider())
    session.turn_status, session.turn_id, session.turn_calls_started = "running", "interrupted", 1
    session = service._save(session)
    recovered = service.recover_turn(project_id="project", session_id=session.id, expected_version=session.version)
    assert recovered.turn_status == "unknown"
    assert recovered.turn_calls_started == 1
    assert service.provider.requests == []


def test_pins_changed_during_provider_call_cannot_persist_proposal_or_reply():
    source = ["原来的证据。"]
    service, _ = make_service(source_resolver=lambda project, pin: source[0])
    session = service.create(project_id="project", content_language="zh-CN", title="来源变化", idea="想法。",
        source_pins=[{"kind": "source_document", "id": "source", "sha256": content_hash(source[0])}])
    def provider_result():
        source[0] = "发生变化的证据。"
        return finish()
    service.provider = FakeProvider(provider_result)
    with pytest.raises(ContractError, match="source_stale"):
        service.turn(project_id="project", session_id=session.id, expected_version=1, message="继续。")
    saved = service.get("project", session.id)
    assert saved.turn_status == "failed"
    assert not any(m.role == "assistant" for m in saved.messages)
    assert saved.turn_calls_started == 1


def test_character_canon_resolver_receives_only_selected_card_scene_time():
    calls = []
    def resolver(project_id, character_id, scene_id=None):
        calls.append((project_id, character_id, scene_id))
        return {"observations": ["钟楼此刻已经关闭。"] if scene_id == "scene" else [], "beliefs": []}
    service, session = make_service(character_resolver=resolver)
    session.workspace = AuthoringWorkspace(scene_cards=[card(), card("unbound", scene_id=None)])
    assert service.character_view(session, "actor")["canon_knowledge"]["observations"] == []
    assert service.character_view(session, "actor", "unbound")["canon_knowledge"]["observations"] == []
    assert service.character_view(session, "actor", "card")["canon_knowledge"]["observations"] == ["钟楼此刻已经关闭。"]
    assert calls == [("project", "actor", None), ("project", "actor", None), ("project", "actor", "scene")]


def test_project_language_change_without_source_pins_blocks_inflight_result():
    language = ["zh-CN"]
    def changed_language():
        language[0] = "en-US"
        return finish()
    service, session = make_service(FakeProvider(changed_language), project_language_resolver=lambda pid: language[0])
    with pytest.raises(ContractError, match="project_language_changed"):
        service.turn(project_id="project", session_id=session.id, expected_version=1, message="继续。")
    saved = service.get("project", session.id)
    assert saved.turn_calls_started == 1 and saved.turn_status == "failed"
    assert not any(m.role == "assistant" for m in saved.messages)


def test_canon_change_during_main_call_blocks_result_and_next_turn_uses_new_canon():
    canon = ["original"]
    def changed_canon():
        canon[0] = "revised"
        return finish()
    service, session = make_service(FakeProvider(changed_canon), canon_resolver=lambda pid: {"fingerprint": content_hash(canon[0])})
    with pytest.raises(ContractError, match="canon_changed"):
        service.turn(project_id="project", session_id=session.id, expected_version=1, message="继续。")
    saved = service.get("project", session.id)
    assert saved.turn_status == "failed"
    service.provider = FakeProvider(finish())
    current = service.turn(project_id="project", session_id=session.id, expected_version=saved.version, message="使用已修改的设定继续。")
    assert current.turn_status == "idle"


def test_canon_change_during_isolated_character_call_blocks_result():
    canon = ["original"]
    def changed_canon():
        canon[0] = "revised"
        return {"options": [{"action": "去寻找国王留下的信。", "rationale": "我相信国王隐瞒了线索。"}], "uncertainties": []}
    provider = FakeProvider({"tool": "simulate_character", "args": {"character_id": "a", "question_kind": "next_action"}}, changed_canon)
    service, session = make_service(provider, canon_resolver=lambda pid: {"fingerprint": content_hash(canon[0])})
    with pytest.raises(ContractError, match="canon_changed"):
        service.turn(project_id="project", session_id=session.id, expected_version=1, message="选择行动。", max_steps=2)
    saved = service.get("project", session.id)
    assert saved.turn_calls_started == 2
    assert not any(m.tool_name == "simulate_character" for m in saved.messages)


def test_proposal_canon_digest_blocks_changed_canon_adoption_without_recertifying():
    canon = ["original"]
    service, session = make_service(canon_resolver=lambda pid: {"fingerprint": content_hash(canon[0])})
    service._propose(session, AuthoringPatch(upsert_items=[item()]), "设计钟楼。")
    session = service._save(session)
    assert session.proposals[0].canon_sha256 == content_hash("original")
    canon[0] = "revised"
    with pytest.raises(ContractError, match="proposal_canon_changed"):
        service.review(project_id="project", session_id=session.id, expected_version=session.version,
                       proposal_id=session.proposals[0].id, decision="adopted")
    assert service.get("project", session.id).proposals[0].canon_sha256 == content_hash("original")


def test_reconciliation_exact_card_binding_cannot_substitute_same_scene_card():
    draft, pin = draft_fixture()
    service, session = make_service(draft_resolver=lambda pid, p: draft)
    session.draft_pins.append(pin)
    session.workspace = AuthoringWorkspace(scene_cards=[card("target", version=3), card("other")])
    evidence = {"draft": pin.model_dump(mode="json"), "start": 0, "end": 2, "expected_text": "阿林"}
    patch = AuthoringPatch(upsert_scene_cards=[card("other", acquisitions=[{"character_id": "actor", "text": "阿林出现在现场。", "evidence": [evidence]}])])
    with pytest.raises(ContractError, match="card_required"):
        service._validate_reconciliation_patch(session, patch, pin)
    with pytest.raises(ContractError, match="card_scope"):
        service._validate_reconciliation_patch(session, patch, pin, ("target", 3))
    with pytest.raises(ContractError, match="stale_or_scope"):
        service._validate_reconciliation_patch(session, AuthoringPatch(), pin, ("target", 2))
    with pytest.raises(ContractError, match="binding_required"):
        service.reconcile(project_id="project", session_id=session.id, expected_version=session.version,
                          draft_pin=pin, card_id="target")


def test_canon_query_tool_forwards_exact_project_query_and_limit_separately_from_fingerprint():
    calls = []
    def query_resolver(project_id, query, limit):
        calls.append((project_id, query, limit))
        return {"complete": True, "total_matches": 1, "returned_count": 1,
                "nodes": [{"id": "actor", "properties": {"name": "阿林", "goal": "找回姐姐。"}}]}
    service, session = make_service(canon_query_resolver=query_resolver,
        canon_resolver=lambda pid: {"fingerprint": content_hash("full canon")})
    result = service._tool(session, AuthoringToolAction(tool="inspect_canon", args={"query": "actor", "limit": 3}))
    assert calls == [("project", "actor", 3)]
    assert result["nodes"][0]["properties"]["goal"] == "找回姐姐。"
    assert service._canon_digest("project") == content_hash("full canon")


def test_generated_messages_and_proposals_keep_frozen_execution_outside_model_content():
    execution = {"profile_id": "PROFILE_METADATA_CANARY", "profile_name": "Frozen profile", "protocol": "chat_completions",
                 "model": "fake", "task": "discussion", "thinking_mode": "disabled"}
    provider = FakeProvider({"tool": "propose_workspace", "args": {"summary": "设计钟楼。", "patch": {"upsert_items": [item()]}}}, finish())
    service, session = make_service(provider, model_execution=execution)
    execution["profile_name"] = "Mutated external setting"
    result = service.turn(project_id="project", session_id=session.id, expected_version=1, message="继续。")
    generated = [m for m in result.messages if m.role in {"tool", "assistant"}]
    assert all(m.model_execution.profile_name == "Frozen profile" for m in generated)
    assert result.proposals[0].model_execution.profile_id == "PROFILE_METADATA_CANARY"
    assert all("PROFILE_METADATA_CANARY" not in m.content for m in result.messages)
    history = service._tool(result, AuthoringToolAction(tool="search_history", args={"query": "", "limit": 20}))
    assert "PROFILE_METADATA_CANARY" not in json.dumps(history, ensure_ascii=False)
    assert all("PROFILE_METADATA_CANARY" not in message.content for request in provider.requests for message in request.messages)
