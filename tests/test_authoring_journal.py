"""Bounded session windows preserve the complete durable collaboration journal."""
import json

import pytest

from storygraph.core.errors import ContractError
from storygraph.models.authoring import (
    AuthoringMessage, AuthoringProposal, AuthoringPatch, AuthoringDraftPin,
    AuthoringToolAction, AuthoringWorkspace,
)
from storygraph.models.draft import Draft
from storygraph.services.authoring import AuthoringService, workspace_hash
from storygraph.services.canon_snapshot import content_hash
from storygraph.stores.authoring_store import SQLiteAuthoringStore
from storygraph.stores.proposal_store import SQLiteProposalStore
from test_authoring_service import FakeProvider, finish, item, card


def fixture(tmp_path):
    path = tmp_path / "journal.sqlite"
    proposals = SQLiteProposalStore(path)
    store = SQLiteAuthoringStore(proposals)
    service = AuthoringService(store=store)
    session = service.create(project_id="p", content_language="zh-CN", title="长篇协作", idea="最初的作者想法。")
    return path, proposals, service, session


def test_more_than_400_messages_100_closed_proposals_survive_window_save_and_restart(tmp_path):
    path, proposals, service, session = fixture(tmp_path)
    session.messages += [AuthoringMessage(id=f"message-{n}", role="author", content=f"历史讨论第{n}轮。", created_at="now") for n in range(501)]
    session.proposals = [AuthoringProposal(id=f"proposal-{n}", base_workspace_sha256=workspace_hash(session.workspace),
        patch=AuthoringPatch(), summary=f"历史方案第{n}份。", status="rejected", created_at="now") for n in range(111)]
    session.proposals.append(AuthoringProposal(id="old-pending", base_workspace_sha256=workspace_hash(session.workspace),
        patch=AuthoringPatch(), summary="仍然等待作者审阅的方案。", created_at="now"))
    saved = service._save(session)
    assert len(saved.messages) == 40 and saved.history_counts.messages == 502
    assert len(saved.proposals) == 21 and saved.history_counts.proposals == 112
    assert saved.history_has_more.messages and saved.history_has_more.proposals
    assert any(p.id == "old-pending" for p in saved.proposals)
    saved.messages.append(AuthoringMessage(id="newest", role="author", content="最新讨论。", created_at="now"))
    saved = service._save(saved)
    assert saved.history_counts.messages == 503
    raw = json.loads(proposals._connection.execute("SELECT payload FROM authoring_sessions ORDER BY version DESC LIMIT 1").fetchone()[0])
    assert "messages" not in raw and "proposals" not in raw and "workspace" not in raw
    assert "_journal_v1" in raw
    assert proposals._connection.execute("SELECT COUNT(*) FROM authoring_blobs WHERE payload=?", ('{"character_plans":[],"items":[],"reader_records":[],"scene_cards":[]}',)).fetchone()[0] == 1
    reopened = AuthoringService(store=SQLiteAuthoringStore(SQLiteProposalStore(path)))
    latest = reopened.get("p", session.id)
    assert latest.history_counts.messages == 503 and latest.history_counts.proposals == 112
    history = reopened.history("p", session.id, query="历史讨论第0轮")
    assert history["total_matches"] == 1 and history["records"][0]["id"] == "message-0"
    assert history["order"] == "newest_first"
    old = reopened.get_proposal("p", session.id, "proposal-0")
    assert old.status == "rejected"
    detail = reopened._tool(latest, AuthoringToolAction(tool="inspect_proposal", args={"proposal_id": "proposal-0"}))
    assert detail["id"] == "proposal-0" and "model_execution" not in detail
    with pytest.raises(ContractError, match="not_found"):
        reopened.get_proposal("foreign", session.id, "proposal-0")
    old_version = reopened.store.get("p", session.id, version=1)
    assert old_version["history_counts"]["messages"] == 1


def test_legacy_inline_payload_stays_readable_and_migrates_on_next_save(tmp_path):
    _, proposals, service, session = fixture(tmp_path)
    inline = session.model_dump(mode="json")
    inline["messages"][0].pop("model_execution")
    proposals._connection.execute("UPDATE authoring_sessions SET payload=? WHERE version=1", (json.dumps(inline, ensure_ascii=False),))
    proposals._connection.commit()
    legacy = service.get("p", session.id)
    migrated = service._save(legacy)
    assert migrated.messages[0].content == session.messages[0].content
    assert service.store.get("p", session.id, version=1)["messages"][0]["content"] == session.messages[0].content


def test_many_draft_pins_and_reader_records_are_pageable_without_entering_role_wire(tmp_path):
    _, _, service, session = fixture(tmp_path)
    def resolve(pid, pin):
        return Draft(id=pin.draft_id, project_id=pid, scene_id=pin.scene_id, version=pin.version,
                     text="早期正文。", content_language="zh-CN", created_at="now", updated_at="now")
    service.draft_resolver = resolve
    session.draft_pins = [AuthoringDraftPin(scene_id=f"scene-{n}", draft_id=f"draft-{n}", version=1,
        text_sha256=content_hash("早期正文。")) for n in range(65)]
    session.workspace = AuthoringWorkspace(reader_records=[{"draft_id": p.draft_id, "version": p.version,
        "text_sha256": p.text_sha256, "start": 0, "end": 2, "expected_text": "早期", "presentation": "narration"} for p in session.draft_pins])
    session = service._save(session)
    source_page = service._tool(session, AuthoringToolAction(tool="inspect_sources", args={"query": "", "offset": 40, "limit": 10}))
    assert source_page["total_matches"] == 65 and source_page["returned_count"] == 10 and source_page["more"]
    early = service._tool(session, AuthoringToolAction(tool="read_source", args={"kind": "draft", "id": "draft-0"}))
    assert early["text"] == "早期正文。"
    reader_page = service._tool(session, AuthoringToolAction(tool="inspect_workspace", args={"query": "draft-0", "offset": 0, "limit": 5}))
    assert reader_page["reader_records"][0]["draft_id"] == "draft-0" and reader_page["complete"]
    provider = FakeProvider({"tool": "simulate_character", "args": {"character_id": "actor", "question_kind": "next_action"}},
        {"options": [{"action": "先观察对方的行动。", "rationale": "我需要更多线索。"}], "uncertainties": []})
    service.provider, service.model = provider, "fake"
    result = service.turn(project_id="p", session_id=session.id, expected_version=session.version, message="思考人物行动。", max_steps=2)
    initial = provider.requests[0].messages[1].content
    assert '"draft_pins_total":65' in initial and '"draft_pins_more":true' in initial
    assert '"draft_id":"draft-0"' not in initial
    assert "draft-0" not in "\n".join(m.content for m in provider.requests[1].messages)
    assert result.turn_calls_started == 2


def test_large_legal_patch_persists_without_copying_patch_into_trace(tmp_path):
    _, _, service, session = fixture(tmp_path)
    patch = {"upsert_items": [item(f"item-{n}", text="线索。" * 400) for n in range(30)]}
    provider = FakeProvider({"tool": "propose_workspace", "args": {"patch": patch, "summary": "添加一组待讨论的线索。"}}, finish())
    service.provider, service.model = provider, "fake"
    result = service.turn(project_id="p", session_id=session.id, expected_version=session.version, message="记录线索。", max_steps=2)
    assert len(result.proposals[0].patch.upsert_items) == 30
    trace = next(m.content for m in result.messages if m.tool_name == "propose_workspace")
    assert len(trace) < 10000 and "upsert_items" not in trace and '"diff"' not in trace
    inspected = service._tool(result, AuthoringToolAction(tool="inspect_proposal", args={"proposal_id": result.proposals[0].id, "limit": 5}))
    assert inspected["total_matches"] == 30 and inspected["returned_count"] == 5 and inspected["more"]


def test_explicit_source_rebinding_cannot_recertify_old_proposal(tmp_path):
    _, _, service, session = fixture(tmp_path)
    source = ["最初的资料。"]
    service.source_resolver = lambda pid, pin: source[0]
    session.source_pins = [{"kind": "source_document", "id": "source", "sha256": content_hash(source[0])}]
    session = type(session).model_validate(session.model_dump(mode="json"))
    service._propose(session, AuthoringPatch(upsert_items=[item()]), "依据最初的资料设计。")
    original_hash = session.proposals[0].inputs_sha256
    session = service._save(session)
    source[0] = "作者明确确认的新资料。"
    session.source_pins = [{"kind": "source_document", "id": "source", "sha256": content_hash(source[0])}]
    session = type(session).model_validate(session.model_dump(mode="json"))
    session = service._save(session)
    with pytest.raises(ContractError, match="proposal_inputs_changed"):
        service.review(project_id="p", session_id=session.id, expected_version=session.version,
                       proposal_id=session.proposals[0].id, decision="adopted")
    assert service.get_proposal("p", session.id, session.proposals[0].id).inputs_sha256 == original_hash
    assert service.get_proposal("p", session.id, session.proposals[0].id).status == "pending"


def test_explicit_unchanged_card_resubmission_reapproves_only_selected_card(tmp_path):
    _, _, service, session = fixture(tmp_path)
    session.workspace = AuthoringWorkspace(items=[item()], scene_cards=[card("selected", version=2), card("untouched", version=2)])
    session = service._save(session)
    selected = session.workspace.scene_cards[0]
    result = service._propose(session, AuthoringPatch(upsert_scene_cards=[selected]), "已经核对新资料，请重新确认这一场。")
    assert result["affected_card_ids"] == ["selected"]
    session = service._save(session)
    approved = service.review(project_id="p", session_id=session.id, expected_version=session.version,
                              proposal_id=result["proposal_id"], decision="adopted")
    assert approved.workspace.scene_cards[0].status == "approved"
    assert approved.workspace.scene_cards[1].status == "proposed"


def test_save_response_remains_its_exact_committed_version_during_concurrent_followup(tmp_path, monkeypatch):
    _, _, service, session = fixture(tmp_path)
    store, original_get = service.store, service.store.get
    dispatched = []
    def racing_get(project_id, session_id, **kwargs):
        value = original_get(project_id, session_id, **kwargs)
        if not dispatched and value["version"] == 2:
            dispatched.append(True)
            followup = original_get(project_id, session_id, full=True)
            followup.update(version=3, title="另一请求随后提交的版本")
            store.save(followup, expected_version=2)
            return original_get(project_id, session_id, **kwargs)
        return value
    monkeypatch.setattr(store, "get", racing_get)
    saved = service._save(session)
    assert saved.version == 2 and saved.title == "长篇协作"
    assert service.get("p", session.id).version == 3
    assert service.get("p", session.id).title == "另一请求随后提交的版本"


def test_duplicate_journal_ids_reject_atomically(tmp_path):
    _, proposals, service, session = fixture(tmp_path)
    old_blob_count = proposals._connection.execute("SELECT COUNT(*) FROM authoring_blobs").fetchone()[0]
    session.messages.append(session.messages[0].model_copy())
    with pytest.raises(ContractError, match="duplicate_journal_identity"):
        service._save(session)
    assert service.get("p", session.id).version == 1
    assert proposals._connection.execute("SELECT COUNT(*) FROM authoring_blobs").fetchone()[0] == old_blob_count
