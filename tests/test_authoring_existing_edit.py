"""New pre-release upserts preserve omitted adopted design and Draft evidence."""
import pytest
from pydantic import ValidationError

from storygraph.core.errors import ContractError
from storygraph.models.authoring import AuthoringWorkspace, AuthoringPatch, AuthoringProposal, AuthoringToolAction, AuthoringSceneCard, authoring_tool_schema
from storygraph.services.authoring import workspace_hash, authoring_inputs_hash
from test_authoring_service import make_service, item, card, draft_fixture, FakeProvider, finish


def test_actual_wire_single_field_edit_preserves_full_adopted_card_and_evidence():
    draft, pin = draft_fixture()
    service, session = make_service(draft_resolver=lambda pid, p: draft)
    session.draft_pins = [pin]
    full = card(status="approved", version=5, chapter_title="原章节", author_summary="完整作者计划。",
        location="钟楼", timeline_position="第一夜", goal="原目标。", conflict="原冲突。", emotional_turn="原转折。",
        pov_character_id="actor", target_length=800, entry_knowledge=[{"character_id": "actor", "text": "原有入场认知。"}],
        intended_actions=[{"character_id": "actor", "intention": "原有动作。"}], withheld=["后台事实。"],
        acquisitions=[{"character_id": "actor", "text": "阿林在场。", "evidence": [{"draft": pin.model_dump(mode="json"), "start": 0, "end": 2, "expected_text": "阿林"}]}])
    session.workspace = AuthoringWorkspace(items=[item()], scene_cards=[full])
    session = service._save(session)
    original = session.workspace.scene_cards[0].model_dump(mode="json")
    service.provider = FakeProvider({"tool": "propose_workspace", "args": {"summary": "只调整当前目标。", "patch": {"upsert_scene_cards": [
        {"id": "card", "title": full["title"], "goal": "新的明确目标。", "writer_policy": full["writer_policy"]}]}}}, finish())
    proposed = service.turn(project_id="project", session_id=session.id, expected_version=session.version, message="改目标，保留其余内容。", max_steps=2)
    target = proposed.proposals[-1].patch.upsert_scene_cards[0]
    expected = {**original, "goal": "新的明确目标。", "status": "proposed", "version": 6}
    assert target.model_dump(mode="json") == expected
    assert proposed.workspace.scene_cards[0].model_dump(mode="json") == original
    adopted = service.review(project_id="project", session_id=session.id, expected_version=proposed.version,
        proposal_id=proposed.proposals[-1].id, decision="adopted")
    assert adopted.workspace.scene_cards[0].model_dump(mode="json") == {**expected, "status": "approved"}


def test_existing_explicit_clear_new_defaults_and_explicit_approval_are_distinct():
    service, session = make_service()
    session.workspace = AuthoringWorkspace(items=[item()], scene_cards=[card(status="approved", goal="原目标。", author_summary="原计划。", pov_character_id="actor")])
    service._tool(session, AuthoringToolAction(tool="propose_workspace", args={"summary": "明确清空指定字段。", "patch": {"upsert_scene_cards": [{
        "id": "card", "title": "钟楼相遇", "writer_policy": card()["writer_policy"], "author_summary": "", "pov_character_id": None, "entry_knowledge": []}]}}))
    target = session.proposals[-1].patch.upsert_scene_cards[0]
    assert target.goal == "原目标。" and target.author_summary == "" and target.pov_character_id is None and target.entry_knowledge == []
    assert target.status == "proposed"
    service._propose(session, AuthoringPatch(upsert_scene_cards=[{"id": "new", "title": "新场景", "writer_policy": card()["writer_policy"]}]), "新增未定场景。")
    new = session.proposals[-1].patch.upsert_scene_cards[0]
    assert new.goal == "" and new.scene_id is None and new.status == "proposed" and new.version == 1
    with pytest.raises(ContractError, match="cannot_approve"):
        service._propose(session, AuthoringPatch(upsert_scene_cards=[session.workspace.scene_cards[0]]), "模型尝试带回approved。")
    with pytest.raises(ValidationError):
        AuthoringToolAction(tool="propose_workspace", args={"summary": "非法空值。", "patch": {"upsert_scene_cards": [
            {"id": "card", "title": "钟楼相遇", "goal": None, "writer_policy": card()["writer_policy"]}]}})


def test_reader_records_remain_exact_complete_records_and_domain_approval_is_unchanged():
    with pytest.raises(ValidationError):
        AuthoringToolAction(tool="propose_workspace", args={"summary": "不能合并不完整引文。", "patch": {"add_reader_records": [
            {"draft_id": "draft", "presentation": "clue"}]}})
    assert AuthoringSceneCard.model_json_schema()["properties"]["status"]["enum"] == ["proposed", "approved"]
    assert authoring_tool_schema()["$defs"]["AuthoringSceneCard"]["properties"]["status"]["const"] == "proposed"


def test_preexisting_persisted_full_patch_is_not_reinterpreted_as_a_new_partial_command():
    service, session = make_service()
    session.workspace = AuthoringWorkspace(items=[item()], scene_cards=[card(goal="旧目标。", author_summary="旧计划。")])
    legacy = AuthoringProposal(id="already-stored-full-patch", base_workspace_sha256=workspace_hash(session.workspace),
        inputs_sha256=authoring_inputs_hash(session), summary="旧完整替换方案。", created_at="now",
        patch=AuthoringPatch(upsert_scene_cards=[{"id": "card", "title": "旧方案的新标题", "writer_policy": card()["writer_policy"]}]))
    session.proposals.append(legacy)
    session = service._save(session)
    approved = service.review(project_id="project", session_id=session.id, expected_version=session.version,
        proposal_id=legacy.id, decision="adopted")
    assert approved.workspace.scene_cards[0].goal == ""
    assert approved.workspace.scene_cards[0].author_summary == ""
    assert approved.workspace.scene_cards[0].title == "旧方案的新标题"
