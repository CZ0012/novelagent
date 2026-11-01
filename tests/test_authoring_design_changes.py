"""Small existing-record edits never require retyping a complete card."""
import copy

import pytest
from pydantic import ValidationError

from storygraph.core.errors import ContractError
from storygraph.models.authoring import AuthoringSession, AuthoringToolAction
from test_authoring_draft_evidence import prepared
from test_authoring_service import FakeProvider, item


def change(fields, *, target_type="scene_card", target_id="card"):
    return {"target_type": target_type, "target_id": target_id, "fields": fields}


def command(*changes):
    return {"tool": "propose_design_changes", "args": {"summary": "仅调整指定的已采用设计。", "changes": list(changes)}}


def test_actual_wire_only_fields_preserves_entire_card_evidence_and_belief_ownership():
    service, session, _, pin = prepared()
    data = session.model_dump(mode="json")
    data["draft_pins"] = [pin.model_dump(mode="json")]
    data["workspace"]["items"].append(item("belief", kind="character_belief", status="author_decided", character_id="actor", text="原有信念。"))
    data["workspace"]["character_plans"] = [{"character_id": "actor", "goal": "原人物目标。", "belief_item_ids": ["belief"]}]
    card = data["workspace"]["scene_cards"][0]
    card["acquisitions"].append({"character_id": "actor", "text": "阿林在场。", "evidence": [{"draft": pin.model_dump(mode="json"), "start": 2, "end": 4, "expected_text": "阿林"}]})
    card["writer_policy"]["writer_style"] = {"tone": "克制", "pov": "第三人称"}
    session = service._save(AuthoringSession.model_validate(data))
    before = session.workspace.scene_cards[0].model_dump(mode="json")
    original = copy.deepcopy(before)
    provider = FakeProvider(command(change({"text": "更新后的主观信念。"}, target_type="item", target_id="belief"),
        change({"goal": "更新人物目标。"}, target_type="character_plan", target_id="actor"),
        change({"goal": "只凭记忆询问。", "author_summary": "她只凭记忆询问，未取下锁。",
                "writer_policy": {"expected_reader_inference": "读者只能猜测她有所回避。"}})))
    service.provider = provider
    result = service.turn(project_id="project", session_id=session.id, expected_version=session.version, message="局部修改。", max_steps=1)
    expected = copy.deepcopy(before)
    expected.update(goal="只凭记忆询问。", author_summary="她只凭记忆询问，未取下锁。", status="proposed", version=5)
    expected["writer_policy"]["expected_reader_inference"] = "读者只能猜测她有所回避。"
    proposal = result.proposals[-1]
    assert proposal.patch.upsert_scene_cards[0].model_dump(mode="json") == expected
    assert result.workspace.scene_cards[0].model_dump(mode="json") == original
    belief = next(i for i in proposal.patch.upsert_items if i.id == "belief")
    assert belief.character_id == "actor" and belief.status == "author_decided" and belief.text == "更新后的主观信念。"
    assert len(provider.requests) == result.turn_calls_started == 1
    trace = next(m.content for m in result.messages if m.tool_name == "propose_design_changes")
    assert '"changes"' not in trace and '"upsert_scene_cards"' not in trace


@pytest.mark.parametrize("entry,category", [
    (change({"id": "renamed"}), "protected_field"),
    (change({"status": "approved"}), "protected_field"),
    (change({"version": 999}), "protected_field"),
    (change({"scene_id": "foreign-scene"}), "protected_field"),
    (change({"unknown_field": "value"}), "unknown_field"),
    (change({"goal": "改目标。"}, target_id="foreign-card"), "target_not_found"),
    (change({"text": "改信念。"}, target_type="item", target_id="pending-only-item"), "target_not_found"),
])
def test_unknown_protected_or_foreign_target_does_not_create_or_modify_design(entry, category):
    service, session, _, _ = prepared()
    before = session.workspace.model_dump(mode="json")
    with pytest.raises(ContractError, match=category):
        service._tool(session, AuthoringToolAction.model_validate(command(entry)))
    assert session.workspace.model_dump(mode="json") == before and session.proposals == []


@pytest.mark.parametrize("changes", [[], [change({})], [change({"goal": "甲。"}), change({"goal": "乙。"})]])
def test_empty_or_duplicate_changes_are_rejected_by_strict_arguments(changes):
    with pytest.raises(ValidationError):
        AuthoringToolAction.model_validate({"tool": "propose_design_changes", "args": {"summary": "无效修改。", "changes": changes}})


def test_final_domain_validation_rejects_unknown_nested_field_and_reconcile_is_hard_blocked():
    service, session, _, pin = prepared()
    with pytest.raises(ValidationError):
        service._tool(session, AuthoringToolAction.model_validate(command(change({"writer_policy": {"invented_field": "value"}}))))
    provider = FakeProvider(command(change({"goal": "不能在核对正文时换目标。"})))
    service.provider = provider
    with pytest.raises(ContractError, match="reconciliation_only_evidence"):
        service.reconcile(project_id="project", session_id=session.id, expected_version=session.version,
            draft_pin=pin, card_id="card", card_version=4, max_steps=6)
    failed = service.get("project", session.id)
    assert failed.turn_status == "failed" and len(provider.requests) == failed.turn_calls_started == 1
    assert failed.proposals == [] and failed.workspace == session.workspace
