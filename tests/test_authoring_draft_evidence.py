"""Runtime-owned quote references remove model offset math and card copying."""
import json

import pytest
from pydantic import ValidationError

from storygraph.core.errors import ContractError
from storygraph.models.authoring import AuthoringWorkspace, AuthoringDraftPin, AuthoringToolAction
from storygraph.models.draft import Draft
from storygraph.services.canon_snapshot import content_hash
from storygraph.services.llm_provider import LLMResponse
from test_authoring_service import make_service, item, card, FakeProvider


class EvidenceProvider:
    def __init__(self, draft_id="draft", old_ref=None):
        self.requests, self.refs, self.draft_id, self.old_ref = [], [], draft_id, old_ref

    def generate(self, request):
        self.requests.append(request)
        step = len(self.requests)
        if step == 1:
            output = {"tool": "read_source", "args": {"kind": "draft", "id": self.draft_id}}
        elif step == 2 and self.old_ref is None:
            output = {"tool": "search_draft_quotes", "args": {"quotes": ["阿林看见红灯", "门已经锁上"]}}
        elif step == 3 or self.old_ref is not None:
            if self.old_ref is None:
                result = json.loads(request.messages[-1].content.removeprefix("Tool result: "))
                self.refs = [page["matches"][0]["quote_ref"] for page in result["quotes"]]
            else:
                self.refs = [self.old_ref, self.old_ref]
            output = {"tool": "propose_draft_evidence", "args": {"summary": "根据已保存正文补充待审证据。",
                "acquisitions": [{"character_id": "actor", "text": "门已经锁上。", "quote_refs": [self.refs[1]]}],
                "reader_records": [{"quote_ref": self.refs[0], "presentation": "clue"}]}}
        else:
            output = {"tool": "finish", "args": {"message": "这些证据尚待作者审阅，原场景计划没有改写。"}}
        return LLMResponse(json.dumps(output, ensure_ascii=False))


def prepared(provider=None, text="😀阿林看见红灯，知道门已经锁上。"):
    draft = Draft(id="draft", project_id="project", scene_id="scene", version=2, text=text,
        content_language="zh-CN", created_at="now", updated_at="now")
    pin = AuthoringDraftPin(scene_id="scene", draft_id="draft", version=2, text_sha256=content_hash(text))
    service, session = make_service(provider, draft_resolver=lambda pid, p: draft)
    session.workspace = AuthoringWorkspace(items=[item()], scene_cards=[card(status="approved", version=4,
        pov_character_id="actor", chapter_title="原章节", author_summary="完整作者计划。", location="钟楼", goal="原目标。",
        entry_knowledge=[{"character_id": "actor", "text": "还不知道门是否锁上。"}],
        acquisitions=[{"character_id": "actor", "text": "原有计划认知。"}], withheld=["后台仍未公开的设置。"])])
    session = service._save(session)
    return service, session, draft, pin


def test_read_batch_evidence_adopt_preserves_every_unedited_card_field_and_exact_utf16():
    provider = EvidenceProvider()
    service, session, draft, pin = prepared(provider)
    before = session.workspace.scene_cards[0].model_dump(mode="json", exclude={"version", "status", "acquisitions"})
    result = service.reconcile(project_id="project", session_id=session.id, expected_version=session.version,
        draft_pin=pin, card_id="card", card_version=4, max_steps=4)
    assert len(provider.requests) == result.turn_calls_started == 4 and result.turn_status == "idle"
    assert result.workspace == session.workspace and len(result.proposals) == 1
    proposal = result.proposals[0]
    proposed = proposal.patch.upsert_scene_cards[0]
    assert proposed.model_dump(mode="json", exclude={"version", "status", "acquisitions"}) == before
    assert proposed.acquisitions[0] == session.workspace.scene_cards[0].acquisitions[0]
    evidence = proposed.acquisitions[-1].evidence[0]
    assert evidence.draft == pin and evidence.expected_text == "门已经锁上"
    assert draft.text.encode("utf-16-le")[evidence.start * 2:evidence.end * 2].decode("utf-16-le") == evidence.expected_text
    reader = proposal.patch.add_reader_records[0]
    assert reader.start == 2 and reader.expected_text == "阿林看见红灯"
    assert reader.text_sha256 == pin.text_sha256 and reader.version == pin.version
    adopted = service.review(project_id="project", session_id=session.id, expected_version=result.version,
        proposal_id=proposal.id, decision="adopted")
    assert adopted.workspace.scene_cards[0].model_dump(mode="json", exclude={"version", "status", "acquisitions"}) == before
    assert len(adopted.workspace.reader_records) == 1 and adopted.workspace.scene_cards[0].status == "approved"


def test_quote_ref_from_previous_turn_is_not_reused_and_no_extra_call_occurs():
    provider = EvidenceProvider()
    service, session, _, pin = prepared(provider)
    result = service.reconcile(project_id="project", session_id=session.id, expected_version=session.version,
        draft_pin=pin, card_id="card", card_version=4, max_steps=4)
    service.provider = EvidenceProvider(old_ref=provider.refs[0])
    with pytest.raises(ContractError, match="quote_ref_invalid"):
        service.reconcile(project_id="project", session_id=session.id, expected_version=result.version,
            draft_pin=pin, card_id="card", card_version=4, max_steps=2)
    failed = service.get("project", session.id)
    assert len(service.provider.requests) == failed.turn_calls_started == 2
    assert len(failed.proposals) == 1 and failed.workspace == session.workspace


def test_batch_requires_active_exact_reconcile_and_read_preflight():
    provider = FakeProvider({"tool": "search_draft_quotes", "args": {"quotes": ["门已经锁上"]}})
    service, session, _, pin = prepared(provider)
    result = service.reconcile(project_id="project", session_id=session.id, expected_version=session.version,
        draft_pin=pin, card_id="card", card_version=4, max_steps=1)
    assert len(provider.requests) == 1
    assert result.turn_status == "idle"
    with pytest.raises(ContractError, match="read_required"):
        service._tool(result, AuthoringToolAction(tool="search_draft_quotes", args={"quotes": ["门已经锁上"]}),
            reconcile_pin=pin, reconcile_card=("card", 4), quote_registry={}, read_draft_ids=set())
    current = service.get("project", session.id)
    service.provider = FakeProvider({"tool": "propose_draft_evidence", "args": {"summary": "没有活动核对上下文。"}})
    with pytest.raises(ContractError, match="reconciliation_required"):
        service.turn(project_id="project", session_id=session.id, expected_version=current.version, message="普通讨论。", max_steps=1)
    assert len(service.provider.requests) == 1


def test_batch_literal_matches_are_bounded_explicit_and_ambiguity_not_selected():
    service, session, draft, pin = prepared(text="钟" * 12000)
    session.draft_pins.append(pin)
    session.turn_id = "fixture-turn"
    registry = {}
    action = AuthoringToolAction(tool="search_draft_quotes", args={"quotes": ["钟" * 1000] * 4})
    result = service._tool(session, action, reconcile_pin=pin, reconcile_card=("card", 4), quote_registry=registry, read_draft_ids={"draft"})
    assert result["more"] and result["returned_count"] == 6
    assert all(page["ambiguous"] and page["total_matches"] == 12 for page in result["quotes"])
    assert len(registry) == 6
    trace = json.dumps({"tool": action.tool, "args": action.args, "result": result}, ensure_ascii=False)
    assert len(trace) < 30000
    for binding in registry.values():
        assert draft.text.encode("utf-16-le")[binding["start"] * 2:binding["end"] * 2].decode("utf-16-le") == binding["text"]
    with pytest.raises(ValidationError):
        AuthoringToolAction(tool="search_draft_quotes", args={"quotes": ["钟" * 1001]})
    with pytest.raises(ValidationError):
        AuthoringToolAction(tool="search_draft_quotes", args={"quotes": ["钟" * 1000] * 5})
