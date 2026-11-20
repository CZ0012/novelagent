import pytest
from pydantic import ValidationError

from storygraph.core.errors import ContractError
from storygraph.models.draft import Draft
from storygraph.services.authoring_passage import AuthoringSelectedPassage, resolve_selected_passage
from storygraph.services.canon_snapshot import content_hash


def saved_passage():
    draft = Draft(id="d", version=3, project_id="p", scene_id="s", created_at="time",
                  updated_at="time", text="甲😀乙，隐情只在下文。", content_language="zh-CN")
    pin = AuthoringSelectedPassage(draft_id=draft.id, version=draft.version,
                                   text_sha256=content_hash(draft.text), start=1, end=4)
    return draft, pin


def test_selected_passage_returns_only_the_granted_utf16_span():
    draft, pin = saved_passage()
    assert resolve_selected_passage(pin, "p", "s", draft) == {
        **pin.model_dump(), "scene_id": "s", "offset_unit": "utf16", "text": "😀乙",
    }


@pytest.mark.parametrize("updates", [
    {"project_id": "other"}, {"scene_id": "other"}, {"id": "other"},
    {"version": 4}, {"text": "新版本，恰好有同样的😀乙"}, {"discarded": True},
])
def test_selected_passage_requires_exact_live_scope_and_content(updates):
    draft, pin = saved_passage()
    with pytest.raises(ContractError):
        resolve_selected_passage(pin, "p", "s", draft.model_copy(update=updates))


@pytest.mark.parametrize(("start", "end"), [(1, 2), (2, 4), (1, 100)])
def test_selected_passage_rejects_invalid_utf16_ranges(start, end):
    draft, pin = saved_passage()
    with pytest.raises(ContractError):
        resolve_selected_passage(pin.model_copy(update={"start": start, "end": end}), "p", "s", draft)


def test_selected_passage_rejects_an_unbounded_selection_or_client_supplied_prose():
    _, pin = saved_passage()
    for change in ({"end": 9000}, {"text": "这段未被保存"}, {"start": True}, {"end": 1}):
        with pytest.raises(ValidationError):
            AuthoringSelectedPassage.model_validate({**pin.model_dump(), **change})
