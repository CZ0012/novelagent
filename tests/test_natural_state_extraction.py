"""Offline state-extraction boundary tests over synthetic natural prose."""

from copy import deepcopy
import json

import pytest

from storygraph.core.errors import ContractError, ModelOutputError
from storygraph.models.draft import Draft
from storygraph.services.llm_provider import LLMResponse
from storygraph.services.natural_state_extraction import (
    extract_natural_draft_state, validate_natural_candidate_source,
)
from storygraph.services.review_service import ReviewService
from storygraph.stores.candidate_store import InMemoryCandidateStore
from storygraph.stores.draft_store import SQLiteDraftStore
from storygraph.stores.memory_graph import InMemoryGraphStore


@pytest.fixture
def context():
    graph = InMemoryGraphStore()
    for ref, label, properties in [
        ("p", "Project", {"language": "zh-CN", "title": "潮汐"}),
        ("hero", "Character", {"project_id": "p", "name": "林烬"}),
        ("secret", "Secret", {"project_id": "p", "description": "身世"}),
        ("s", "Scene", {"project_id": "p", "pov_character_id": "hero", "timeline_position": "第九日"}),
    ]:
        graph.seed_canon_node(node_id=ref, node_type=label, properties=properties)
    draft = Draft(id="d", project_id="p", scene_id="s", content_language="zh-CN",
                  version=3, text="林烬终于确认了自己的身世。", created_at="now", updated_at="now")
    return graph, draft


def fact(**overrides):
    return {
        "fact_type": "SecretReveal", "subject_id": "hero", "relation": "KNOWS_SECRET",
        "object_id": "secret", "value": None, "operation": "create_relation",
        "target": "hero -> KNOWS_SECRET -> secret", "properties": {"known": True},
        "source_span": {"start_offset": 0, "end_offset": 14, "quote": "林烬终于确认了自己的身世。"},
        "temporal_scope": {"scene_id": "s", "timeline_position": "第九日"},
        "confidence": 0.9, "certainty": "asserted", "rationale": "原文明确说明主角已经得知身世。",
        **overrides,
    }


class Replay:
    def __init__(self, output, callback=None):
        self.output = output
        self.requests = []
        self.callback = callback

    def generate(self, request):
        self.requests.append(request)
        if self.callback:
            self.callback()
        if isinstance(self.output, Exception):
            raise self.output
        return LLMResponse(content=self.output if isinstance(self.output, str)
                           else json.dumps(self.output, ensure_ascii=False))


def run(context, provider, **overrides):
    graph, draft = context
    return extract_natural_draft_state(**{
        "graph": graph, "project_id": "p", "source_draft": draft,
        "provider": provider, "model": "exact-model", "output_language": "zh-CN", **overrides,
    })


def test_exact_natural_chinese_prose_produces_pending_candidate_only(context):
    graph, draft = context
    before = (len(graph.nodes), len(graph.relationships), len(graph.event_log.list()))
    quote = draft.text
    raw = fact(source_span={"start_offset": 0, "end_offset": len(quote), "quote": quote})
    provider = Replay({"facts": [raw]})
    candidates = run(context, provider)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.status == "DRAFT_FACT" and candidate.review.status == "pending"
    assert candidate.source_span.quote == quote
    assert candidate.source_draft_id == candidate.proposed_graph_patch.source_ref == draft.id
    assert candidate.proposed_graph_patch.properties["project_id"] == "p"
    assert candidate.proposed_graph_patch.properties["valid_from_scene"] == "s"
    note = json.loads(candidate.evidence[0].note)
    assert note["draft_version"] == 3 and note["temporal_scope"]["scene_id"] == "s"
    assert before == (len(graph.nodes), len(graph.relationships), len(graph.event_log.list()))
    assert provider.requests[0].model == "exact-model"
    assert json.loads(provider.requests[0].messages[1].content)["source_text"] == quote


@pytest.mark.parametrize("changed", [
    {"project_id": "foreign"}, {"scene_id": "missing"}, {"content_language": None},
    {"content_language": "en-US"}, {"text": ""}, {"text": "字" * 32001},
])
def test_bad_scope_language_or_oversize_rejected_before_model(context, changed):
    provider = Replay({"facts": []})
    with pytest.raises(ContractError):
        run(context, provider, source_draft=context[1].model_copy(update=changed))
    assert provider.requests == []


@pytest.mark.parametrize("change", [
    {"subject_id": "unknown"}, {"object_id": "unknown"},
    {"target": "other -> KNOWS_SECRET -> secret"},
    {"operation": "create_node"},
    {"status": "CANON"}, {"review": {"status": "accepted"}},
    {"properties": {"project_id": "foreign"}},
    {"properties": {"llm_api_key": "sensitive"}},
    {"properties": {"state": {"nested": "mutation"}}},
    {"temporal_scope": {"scene_id": "elsewhere", "timeline_position": "第九日"}},
    {"temporal_scope": {"scene_id": "s", "timeline_position": "第一日"}},
    {"source_span": {"start_offset": 1, "end_offset": 13, "quote": "林烬终于确认了自己的身世。"}},
    {"source_span": {"start_offset": 0, "end_offset": 3, "quote": "不存在"}},
    {"relation": "INVENTED_EDGE"},
    {"subject_id": "secret", "target": "secret -> KNOWS_SECRET -> secret"},
    {"object_id": "hero", "target": "hero -> KNOWS_SECRET -> hero"},
    {"properties": {"strength": float("inf")}},
    {"properties": {"valid_from": "第九日"}},
    {"properties": {"valid_from_scene": "earlier_scene"}},
    {"properties": {"timeline_position": "第九日"}},
    {"properties": {"known": False}},
])
def test_invalid_output_is_atomic_and_sanitized(context, change):
    graph, draft = context
    good = fact(source_span={"start_offset": 0, "end_offset": len(draft.text), "quote": draft.text})
    bad = {**deepcopy(good), **change}
    provider = Replay({"facts": [good, bad]})
    before = (len(graph.nodes), len(graph.relationships), len(graph.event_log.list()))
    with pytest.raises(ModelOutputError, match="^natural_state_invalid_output$"):
        run(context, provider)
    assert before == (len(graph.nodes), len(graph.relationships), len(graph.event_log.list()))


def test_foreign_known_ids_cannot_be_referenced(context):
    graph, draft = context
    graph.seed_canon_node(node_id="q", node_type="Project", properties={"language": "zh-CN"})
    graph.seed_canon_node(node_id="foreign", node_type="Secret",
                          properties={"project_id": "q", "description": "私密文本"})
    provider = Replay({"facts": [fact(object_id="foreign")]})
    with pytest.raises(ModelOutputError):
        run(context, provider)
    assert "私密文本" not in provider.requests[0].messages[1].content


def test_emoji_offsets_are_unicode_codepoints_and_repeated_text_keeps_position(context):
    graph, draft = context
    text = "🌙林烬闭眼。林烬闭眼。"
    draft = draft.model_copy(update={"text": text})
    start = text.rfind("林烬闭眼。")
    raw = fact(fact_type="CharacterState", relation="state", object_id=None,
        operation="update_node", target="hero", properties={"state": "闭眼"},
        source_span={"start_offset": start, "end_offset": len(text), "quote": "林烬闭眼。"})
    result = run((graph, draft), Replay({"facts": [raw]}))
    assert result[0].source_span.start_offset == start == 6
    assert result[0].source_span.end_offset == len(text)


@pytest.mark.parametrize("certainty,status", [("inferred", "HYPOTHESIS"), ("conflicting", "CONFLICT")])
def test_inference_and_conflict_never_become_accepted(context, certainty, status):
    draft = context[1]
    raw = fact(certainty=certainty,
        source_span={"start_offset": 0, "end_offset": len(draft.text), "quote": draft.text})
    result = run(context, Replay({"facts": [raw]}))
    assert result[0].status == status and result[0].review.reviewer is None


def test_valid_negation_empty_extraction_is_not_silently_fabricated(context):
    draft = context[1].model_copy(update={"text": "林烬仍不知道自己的身世。"})
    assert run((context[0], draft), Replay({"facts": []})) == []


@pytest.mark.parametrize("output", ["bad json", "```json\n{}\n```", {"facts": [{}]},
                                      {"facts": [fact()] * 17}, {"facts": [], "canon": True}])
def test_strict_json_and_fact_count_do_not_salvage_partial_output(context, output):
    with pytest.raises(ModelOutputError, match="natural_state_invalid_output"):
        run(context, Replay(output))


def test_provider_errors_are_safe_and_never_retried(context):
    provider = Replay(RuntimeError("sk-secret https://private endpoint author text"))
    with pytest.raises(ModelOutputError, match="^natural_state_provider_failed$"):
        run(context, provider)
    assert len(provider.requests) == 1


def test_canon_changed_during_paid_call_rejects_candidates(context):
    graph, draft = context
    provider = Replay({"facts": []}, callback=lambda: graph.nodes["hero"].properties.update({"name": "改名"}))
    with pytest.raises(ContractError, match="^natural_state_canon_changed$"):
        run(context, provider)


def test_replayed_identical_assertions_have_stable_deduplicated_ids(context):
    draft = context[1]
    raw = fact(source_span={"start_offset": 0, "end_offset": len(draft.text), "quote": draft.text})
    first = run(context, Replay({"facts": [raw, raw]}))
    second = run(context, Replay({"facts": [raw]}))
    assert len(first) == 1 and first[0].id == second[0].id


def stored_candidate(context, **overrides):
    graph, original = context
    drafts = SQLiteDraftStore()
    draft = drafts.create_draft(project_id="p", scene_id="s", content_language="zh-CN",
                                text=original.text)
    raw = fact(source_span={"start_offset": 0, "end_offset": len(draft.text), "quote": draft.text},
               **overrides)
    candidate = run((graph, draft), Replay({"facts": [raw]}))[0]
    return graph, drafts, draft, candidate


@pytest.mark.parametrize("action", ["accept", "edit_and_accept"])
def test_review_checks_full_source_hash_even_when_quote_is_unchanged(context, action):
    graph, drafts, draft, candidate = stored_candidate(context)
    candidates = InMemoryCandidateStore()
    review = ReviewService(candidates, graph, draft_store=drafts)
    review.submit([candidate])
    before = len(graph.event_log.list())
    changed = drafts.update_draft(draft.id, text=draft.text + "但这只是一个梦。")
    assert changed.version == draft.version and candidate.source_span.quote in changed.text
    kwargs = {"patch_properties": {"description": "作者调整"}} if action == "edit_and_accept" else {}
    with pytest.raises(ContractError, match="natural_state_source_changed"):
        getattr(review, action)(candidate.id, reviewer="author", **kwargs)
    assert candidates.get(candidate.id).review.status == "pending"
    assert len(graph.event_log.list()) == before
    assert not any(r.source_ref == draft.id for r in graph.relationships.values())


def test_submit_rejects_stale_batch_without_creating_candidates(context):
    graph, drafts, draft, candidate = stored_candidate(context)
    drafts.update_draft(draft.id, text=draft.text + "此事并未发生。")
    candidates = InMemoryCandidateStore()
    with pytest.raises(ContractError, match="natural_state_source_changed"):
        ReviewService(candidates, graph, draft_store=drafts).submit([candidate])
    assert candidates.list() == []


def test_natural_source_requires_store_and_exact_metadata(context):
    graph, drafts, _, candidate = stored_candidate(context)
    with pytest.raises(ContractError, match="natural_state_source_unverifiable"):
        ReviewService(InMemoryCandidateStore(), graph).submit([candidate])
    bad = candidate.model_copy(update={"evidence": []})
    with pytest.raises(ContractError, match="natural_state_source_unverifiable"):
        validate_natural_candidate_source(bad, draft_store=drafts)


def test_source_changed_between_review_persistence_and_commit_compensates(context):
    graph, drafts, draft, candidate = stored_candidate(context)
    class RacingCandidates(InMemoryCandidateStore):
        def update_if_pending(self, value):
            result = super().update_if_pending(value)
            drafts.update_draft(draft.id, text=draft.text + "原来他记错了。")
            return result
    candidates = RacingCandidates()
    review = ReviewService(candidates, graph, draft_store=drafts)
    review.submit([candidate])
    before = len(graph.event_log.list())
    with pytest.raises(ContractError, match="natural_state_source_changed"):
        review.accept(candidate.id, reviewer="author")
    assert candidates.get(candidate.id).review.status == "pending"
    assert len(graph.event_log.list()) == before


def test_new_knowledge_relation_uses_actual_scene_validity(context):
    graph, _ = context
    for scene_id in ("early", "later"):
        graph.seed_canon_node(node_id=scene_id, node_type="Scene", properties={"project_id": "p"})
    for ref, source, target_ref in (("next1", "early", "s"), ("next2", "s", "later")):
        graph.seed_canon_relation(relation_id=ref, relation_type="NEXT_SCENE", source_id=source,
                                  target_id=target_ref, properties={"project_id": "p"})
    graph, drafts, _, candidate = stored_candidate(context)
    candidates = InMemoryCandidateStore()
    review = ReviewService(candidates, graph, draft_store=drafts)
    review.submit([candidate])
    review.accept(candidate.id, reviewer="author")
    assert "secret" not in graph.get_character_knowledge("hero", scene_id="early").knows
    assert "secret" in graph.get_character_knowledge("hero", scene_id="s").knows
    assert "secret" in graph.get_character_knowledge("hero", scene_id="later").knows
    relation = next(r for r in graph.relationships.values() if r.source_ref == candidate.source_draft_id)
    assert relation.properties["valid_from_scene"] == "s"
    assert "valid_from" not in relation.properties and "timeline_position" not in relation.properties


def test_human_edit_cannot_remove_natural_relation_validity(context):
    graph, drafts, _, candidate = stored_candidate(context)
    review = ReviewService(InMemoryCandidateStore(), graph, draft_store=drafts)
    review.submit([candidate])
    with pytest.raises(ContractError, match="natural_state_relation_scope_invalid"):
        review.edit_and_accept(candidate.id, reviewer="author", patch_properties={"valid_from_scene": None})


def test_historical_node_update_is_explicit_observation_not_graph_mutation(context):
    graph, drafts, _, candidate = stored_candidate(context, fact_type="CharacterState", relation="state",
        object_id=None, operation="update_node", target="hero", properties={"state": "震惊"})
    assert candidate.proposed_graph_patch.operation == "none"
    assert candidate.proposed_graph_patch.properties == {}
    assert json.loads(candidate.value) == {"state": "震惊"}
    assert "不修改正典状态" in candidate.rationale
    metadata = json.loads(candidate.evidence[0].note)
    assert metadata["observation_only"] and metadata["requested_operation"] == "update_node"
    before = graph.get_node("hero").model_dump()
    review = ReviewService(InMemoryCandidateStore(), graph, draft_store=drafts)
    review.submit([candidate])
    review.accept(candidate.id, reviewer="author")
    assert graph.get_node("hero").model_dump() == before


def test_existing_relation_state_update_is_noop_observation(context):
    graph, _ = context
    graph.seed_canon_relation(relation_id="existing", relation_type="KNOWS_SECRET",
        source_id="hero", target_id="secret", properties={"project_id": "p"})
    graph, drafts, _, candidate = stored_candidate(context, operation="update_relation",
                                                   target="existing", properties={"state": "遗忘"})
    assert candidate.proposed_graph_patch.operation == "none"
    before = graph.get_relationship("existing").model_dump()
    review = ReviewService(InMemoryCandidateStore(), graph, draft_store=drafts)
    review.submit([candidate])
    review.accept(candidate.id, reviewer="author")
    assert graph.get_relationship("existing").model_dump() == before


@pytest.mark.parametrize("field,state", [("life_status", "dead"), ("physical_state", "injured")])
def test_compatible_typed_node_changes_become_reviewed_temporal_assertions(context, field, state):
    graph, drafts, _, candidate = stored_candidate(context, fact_type="CharacterState", relation=field,
        object_id=None, operation="update_node", target="hero", properties={field: state})
    assert candidate.proposed_graph_patch.operation == "append_state"
    assert candidate.proposed_graph_patch.properties["field"] == field
    assert candidate.proposed_graph_patch.properties["value"] == state
    assert not json.loads(candidate.evidence[0].note)["observation_only"]
    review = ReviewService(InMemoryCandidateStore(), graph, draft_store=drafts)
    review.submit([candidate])
    review.accept(candidate.id, reviewer="author")
    assert graph.nodes["state_" + candidate.id].properties["value"] == state
    assert field not in graph.nodes["hero"].properties


def test_natural_location_transition_is_scalar_state_not_overlapping_raw_edge(context):
    graph, draft = context
    graph.seed_canon_node(node_id="port", node_type="Location",
                          properties={"project_id": "p", "name": "港口"})
    draft = draft.model_copy(update={"text": "林烬走进港口。"})
    graph, drafts, _, candidate = stored_candidate((graph, draft), fact_type="CharacterState",
        relation="LOCATED_AT", object_id="port", operation="create_relation",
        target="hero -> LOCATED_AT -> port", properties={})
    assert candidate.proposed_graph_patch.operation == "append_state"
    assert candidate.proposed_graph_patch.properties["field"] == "location_id"
    review = ReviewService(InMemoryCandidateStore(), graph, draft_store=drafts)
    review.submit([candidate])
    review.accept(candidate.id, reviewer="author")
    assert graph.nodes["state_" + candidate.id].properties["value"] == "port"
    assert not any(r.type == "LOCATED_AT" for r in graph.relationships.values())
