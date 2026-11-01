"""Explicit unchanged-card review is a pending state transition, not empty prose."""
import json

import pytest
from pydantic import ValidationError

from storygraph.core.errors import ContractError
from storygraph.models.authoring import AuthoringProposal, AuthoringPatch, AuthoringToolAction
from storygraph.services.authoring import workspace_hash
from test_authoring_draft_evidence import prepared
from test_authoring_format_correction import SequenceProvider


def review(*ids):
    return {"tool": "propose_card_review", "args": {"summary": "保持全部内容，提交当前卡片复核。", "card_ids": list(ids)}}


def test_actual_wire_review_copies_complete_card_and_requires_author_adoption():
    service, session, _, _ = prepared(SequenceProvider(review("card")))
    before = session.workspace.scene_cards[0].model_dump(mode="json")
    session.workspace.scene_cards[0].status = "proposed"
    session = service._save(session)
    before["status"] = "proposed"
    result = service.turn(project_id="project", session_id=session.id, expected_version=session.version, message="本场不改内容，重新提交复核。", max_steps=1)
    proposal = result.proposals[0]
    target = proposal.patch.upsert_scene_cards[0].model_dump(mode="json")
    assert target == before and proposal.affected_card_ids == ["card"]
    assert result.workspace.scene_cards[0].status == "proposed"
    assert result.turn_calls_started == len(service.provider.requests) == 1
    approved = service.review(project_id="project", session_id=session.id, expected_version=result.version,
        proposal_id=proposal.id, decision="adopted")
    assert approved.workspace.scene_cards[0].model_dump(mode="json") == {**before, "status": "approved"}
    trace = next(m.content for m in result.messages if m.tool_name == "propose_card_review")
    assert '"upsert_scene_cards"' not in trace


@pytest.mark.parametrize("ids", [[], ["card", "card"], ["card"] * 21])
def test_card_review_invalid_card_count_and_duplicates_rejected(ids):
    with pytest.raises(ValidationError):
        AuthoringToolAction.model_validate(review(*ids))


def test_unknown_foreign_card_and_reconcile_cannot_create_review_proposal():
    service, session, _, pin = prepared(SequenceProvider(review("foreign-card")))
    before = session.workspace.model_dump(mode="json")
    with pytest.raises(ContractError, match="target_not_found"):
        service.turn(project_id="project", session_id=session.id, expected_version=session.version, message="提交复核。", max_steps=6)
    current = service.get("project", session.id)
    assert current.workspace.model_dump(mode="json") == before and current.proposals == []
    assert len(service.provider.requests) == 1
    service.provider = SequenceProvider(review("card"))
    with pytest.raises(ContractError, match="reconciliation_only_evidence"):
        service.reconcile(project_id="project", session_id=session.id, expected_version=current.version,
            draft_pin=pin, card_id="card", card_version=4, max_steps=6)
    assert len(service.provider.requests) == 1


def test_new_empty_patch_can_only_use_existing_single_correction_and_does_not_fake_review():
    empty = {"tool": "propose_workspace", "args": {"summary": "空方案不能声称已复核。", "patch": {}}}
    service, session, _, _ = prepared(SequenceProvider(empty, review("card")))
    result = service.turn(project_id="project", session_id=session.id, expected_version=session.version, message="提交复核。", max_steps=2)
    assert len(result.proposals) == 1 and result.proposals[0].patch.upsert_scene_cards[0].id == "card"
    assert result.turn_calls_started == len(service.provider.requests) == 2
    diagnostic = json.loads(next(m.content for m in result.messages if m.tool_name == "format_diagnostic"))
    assert diagnostic["result"]["diagnostic"]["code"] == "authoring_empty_patch"
    current = service.get("project", session.id)
    service.provider = SequenceProvider(empty, empty, review("card"))
    with pytest.raises(ContractError, match="authoring_empty_patch"):
        service.turn(project_id="project", session_id=session.id, expected_version=current.version, message="再次讨论。", max_steps=6)
    failed = service.get("project", session.id)
    assert len(service.provider.requests) == failed.turn_calls_started == 2 and len(failed.proposals) == 1


def test_legacy_empty_record_remains_readable_and_rejectable_without_migration():
    service, session, _, _ = prepared()
    legacy = AuthoringProposal(id="legacy-empty", base_workspace_sha256=workspace_hash(session.workspace),
        summary="历史空提案。", patch=AuthoringPatch(), created_at="now")
    session.proposals.append(legacy)
    session = service._save(session)
    before = service.get_proposal("project", session.id, legacy.id).model_dump(mode="json")
    rejected = service.review(project_id="project", session_id=session.id, expected_version=session.version,
        proposal_id=legacy.id, decision="rejected")
    after = service.get_proposal("project", session.id, legacy.id)
    assert after.patch == legacy.patch and after.status == "rejected"
    assert rejected.workspace == session.workspace
    historic = service.store.get("project", session.id, version=session.version, full=True)
    assert next(p for p in historic["proposals"] if p["id"] == legacy.id) == before
