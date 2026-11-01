"""Pending-design revision composes virtual workspaces without adopting them."""
import json

import pytest
from pydantic import ValidationError

from storygraph.core.errors import ContractError, ModelOutputError
from storygraph.models.authoring import AuthoringPatch, AuthoringToolAction, authoring_tool_schema
from test_authoring_service import make_service, item, card, draft_fixture, FakeProvider, finish


def test_revision_preserves_nine_pending_items_and_original_record():
    service, session = make_service()
    service._propose(session, AuthoringPatch(upsert_items=[item(f"idea-{n}") for n in range(9)],
        upsert_scene_cards=[card(depends_on=["idea-0"])]), "完整的九项方案。")
    original = session.proposals[0]
    before = original.model_dump(mode="json")
    result = service._tool(session, AuthoringToolAction(tool="revise_proposal", args={
        "proposal_id": original.id, "summary": "只调整第一项，其余不变。", "patch": {"upsert_items": [item("idea-0", text="钟楼的钟在清晨停摆。") ]}}))
    revised = session.proposals[-1]
    assert len(revised.patch.upsert_items) == 9 and len(revised.patch.upsert_scene_cards) == 1
    assert revised.patch.upsert_items[0].text == "钟楼的钟在清晨停摆。"
    assert original.model_dump(mode="json") == before and original.status == "pending"
    assert revised.supersedes_proposal_id == original.id and result["proposal_id"] == revised.id
    assert session.workspace.items == [] and session.workspace.scene_cards == []


@pytest.mark.parametrize("base_contains_reader", [False, True])
def test_reader_add_remove_and_remove_add_cancel_into_unambiguous_final_delta(base_contains_reader):
    draft, pin = draft_fixture()
    service, session = make_service(draft_resolver=lambda pid, p: draft)
    session.draft_pins.append(pin)
    record = {"draft_id": pin.draft_id, "version": pin.version, "text_sha256": pin.text_sha256,
              "start": 0, "end": 2, "expected_text": "阿林", "presentation": "narration"}
    if base_contains_reader:
        session.workspace.reader_records = [record]
        session = type(session).model_validate(session.model_dump(mode="json"))
    original_patch = AuthoringPatch(**{("remove_reader_records" if base_contains_reader else "add_reader_records"): [record]})
    delta = AuthoringPatch(**{("add_reader_records" if base_contains_reader else "remove_reader_records"): [record]})
    service._propose(session, original_patch, "待审读者记录。")
    original = session.proposals[0]
    with pytest.raises(ContractError, match="authoring_empty_patch"):
        service._revise_proposal(session, original.id, delta, "撤销这一条读者记录变化。")
    assert len(session.proposals) == 1 and original.status == "pending"
    with pytest.raises(ValidationError):
        AuthoringPatch(add_reader_records=[record], remove_reader_records=[record])


def test_revision_cannot_bypass_reconciliation_only_evidence_scope():
    draft, pin = draft_fixture()
    service, session = make_service(draft_resolver=lambda pid, p: draft)
    session.draft_pins.append(pin)
    service._propose(session, AuthoringPatch(upsert_items=[item()]), "普通待审设计。")
    original = session.proposals[0]
    with pytest.raises(ContractError, match="only_evidence"):
        service._revise_proposal(session, original.id, AuthoringPatch(), "核对正文。", reconcile_pin=pin)
    assert len(session.proposals) == 1 and original.status == "pending" and session.workspace.items == []


@pytest.mark.parametrize("patch", [
    {"upsert_scene_cards": [card(depends_on=[])], "upsert_character_plans": [{"character_id": "actor", "goal": "寻找线索。", "belief_item_ids": ["card"]}]},
    {"upsert_scene_cards": [card(depends_on=[], entry_knowledge=[{"character_id": "actor", "text": "看见一道痕迹。", "item_id": "card"}])]},
    {"upsert_items": [item(depends_on=["actor"])], "upsert_character_plans": [{"character_id": "actor", "goal": "寻找线索。"}]},
])
def test_references_must_exist_in_the_correct_final_item_or_card_collection(patch):
    service, session = make_service()
    with pytest.raises(ContractError, match="dangling"):
        service._propose(session, AuthoringPatch.model_validate(patch), "引用边界检查。")
    assert session.proposals == []


def test_main_advertises_one_complete_tool_schema_with_all_patch_references():
    schema = authoring_tool_schema()
    tools = {variant["properties"]["tool"]["const"] for variant in schema["oneOf"]}
    assert {"propose_workspace", "revise_proposal", "inspect_proposal", "simulate_character"} <= tools
    def validate_refs(value):
        if isinstance(value, dict):
            if "$ref" in value:
                assert value["$ref"].startswith("#/$defs/")
                assert value["$ref"].split("/")[-1] in schema["$defs"]
            for nested in value.values():
                validate_refs(nested)
        elif isinstance(value, list):
            for nested in value:
                validate_refs(nested)
    validate_refs(schema)
    provider = FakeProvider(finish())
    service, session = make_service(provider)
    service.turn(project_id="project", session_id=session.id, expected_version=1, message="继续讨论。", max_steps=1)
    system = provider.requests[0].messages[0].content
    assert "Patch JSON schema:" not in system
    actual = json.JSONDecoder().raw_decode(system.split("Allowed tool JSON schema:\n", 1)[1])[0]
    assert actual == schema and "AuthoringPatch" in actual["$defs"]


def test_revision_actual_presence_controls_recursive_merge_null_empty_and_list_replacement():
    service, session = make_service()
    original_card = card(chapter_title="原章节", author_summary="完整作者计划。", location="钟楼", goal="寻找线索。",
        conflict="双方不愿先解释。", pov_character_id="actor", entry_knowledge=[{"character_id": "actor", "text": "看见钟楼。"}],
        withheld=["后台设定。"], writer_policy={"access_mode": "surface", "surface_plan": {"kind": "literal", "text": "两人在钟楼相遇。"},
            "writer_style": {"tone": "克制", "pov": "第三人称", "banned_patterns": ["避免冗长解释。"]}})
    service._propose(session, AuthoringPatch(upsert_items=[item()], upsert_scene_cards=[original_card]), "完整场景方案。")
    original = session.proposals[0]
    action = AuthoringToolAction.model_validate({"tool": "revise_proposal", "args": {"proposal_id": original.id,
        "summary": "只清空明确提交的字段。", "patch": {"upsert_scene_cards": [{"id": "card", "title": "钟楼相遇",
            "author_summary": "", "scene_id": None, "entry_knowledge": [], "withheld": [],
            "writer_policy": {"access_mode": "surface", "surface_plan": {"kind": "literal", "text": "两人在钟楼相遇。"},
                              "writer_style": {"tone": None, "banned_patterns": []}}}]}}})
    wire_card = action.args["patch"]["upsert_scene_cards"][0]
    assert "goal" not in wire_card and "chapter_title" not in wire_card
    assert wire_card["writer_policy"]["writer_style"]["tone"] is None
    service._tool(session, action)
    revised = session.proposals[-1].patch.upsert_scene_cards[0]
    assert revised.chapter_title == "原章节" and revised.goal == "寻找线索。" and revised.location == "钟楼"
    assert revised.author_summary == "" and revised.scene_id is None and revised.entry_knowledge == [] and revised.withheld == []
    assert revised.writer_policy.writer_style.tone is None and revised.writer_policy.writer_style.pov == "第三人称"
    assert revised.writer_policy.writer_style.banned_patterns == ()


def test_explicit_invalid_null_is_rejected_not_replaced_by_old_value():
    service, session = make_service()
    service._propose(session, AuthoringPatch(upsert_items=[item()], upsert_scene_cards=[card(goal="原目标。")]), "原方案。")
    session = service._save(session)
    original = session.proposals[0]
    service.provider = FakeProvider({"tool": "revise_proposal", "args": {"proposal_id": original.id, "summary": "非法空值。",
        "patch": {"upsert_scene_cards": [{**card(depends_on=[]), "goal": None}]}}})
    with pytest.raises(ModelOutputError):
        service.turn(project_id="project", session_id=session.id, expected_version=session.version, message="调整场景。", max_steps=1)
    failed = service.get("project", session.id)
    assert failed.turn_status == "failed" and len(failed.proposals) == 1
    assert failed.proposals[0].patch.upsert_scene_cards[0].goal == "原目标。"


def test_normal_propose_preserves_omitted_fields_for_existing_objects():
    service, session = make_service()
    session.workspace.items = [item()]
    session.workspace.scene_cards = [card(goal="原目标。", chapter_title="原章节")]
    session = type(session).model_validate(session.model_dump(mode="json"))
    minimal = {"id": "card", "title": "新标题", "writer_policy": card()["writer_policy"]}
    service._tool(session, AuthoringToolAction(tool="propose_workspace", args={"summary": "完整替换。", "patch": {"upsert_scene_cards": [minimal]}}))
    assert session.proposals[-1].patch.upsert_scene_cards[0].goal == "原目标。"
    assert session.proposals[-1].patch.upsert_scene_cards[0].chapter_title == "原章节"


def test_reconciliation_rejects_revision_that_partially_changes_scene_intention():
    draft, pin = draft_fixture()
    service, session = make_service(draft_resolver=lambda pid, p: draft)
    session.draft_pins.append(pin)
    session.workspace.items = [item()]
    session.workspace.scene_cards = [card(goal="原本的场景目标。")]
    session = type(session).model_validate(session.model_dump(mode="json"))
    service._propose(session, AuthoringPatch(upsert_scene_cards=[session.workspace.scene_cards[0]]), "原待审方案。")
    original = session.proposals[0]
    delta = AuthoringPatch(upsert_scene_cards=[{"id": "card", "title": "钟楼相遇", "goal": "改成另一个目标。", "writer_policy": card()["writer_policy"]}])
    with pytest.raises(ContractError, match="only_evidence"):
        service._revise_proposal(session, original.id, delta, "核对正文。", reconcile_pin=pin, reconcile_card=("card", 1))
    assert len(session.proposals) == 1 and session.workspace.scene_cards[0].goal == "原本的场景目标。"
