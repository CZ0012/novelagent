"""Explicit author correction revises historical truth without deleting evidence."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from storygraph.core.errors import ContractError, GraphStoreError
from storygraph.models.temporal_state import TemporalStateCorrectionRequest
from storygraph.services.canon_snapshot import content_hash
from storygraph.services.review_service import ReviewService
from storygraph.services.temporal_state import (
    get_state_assertions, propose_state_correction, temporal_slot_fingerprint, temporal_state_history,
)
from storygraph.stores.candidate_store import InMemoryCandidateStore
from tests.test_temporal_state import setup as setup
from tests.test_temporal_state import accept, candidate, value


def requested_correction(setup, prior, corrected="alive"):
    graph, drafts, _ = setup
    draft = drafts.get_draft(prior.source_draft_id)
    text = "原记录有误：他负伤倒下，但没有死去。" if corrected == "alive" else "重新核对记录：他的确已经死去。"
    draft = drafts.update_draft(draft.id, text=text)
    request = TemporalStateCorrectionRequest(assertion_id="state_" + prior.id,
        source_draft_id=draft.id, expected_draft_version=draft.version,
        expected_source_sha256=content_hash(draft.text),
        source_span={"start_offset": 0, "end_offset": len(text), "quote": text}, value=corrected,
        expected_slot_fingerprint=temporal_slot_fingerprint(graph, project_id="p", subject_id="hero", field="life_status"),
        rationale="作者明确纠正先前记录，保留旧证据供审计。")
    return request


def test_correction_is_pending_until_author_accept_and_old_receipt_unchanged(setup):
    graph, drafts, candidates = setup
    original = accept(setup, candidate(setup))
    old_node = graph.nodes["state_" + original.id].model_dump()
    old_event = graph.event_log.get("evt_state_" + original.id).model_dump()
    request = requested_correction(setup, original)
    before = (len(graph.nodes), len(graph.event_log.list()))
    preview = propose_state_correction(graph=graph, draft_store=drafts, project_id="p", request=request)
    assert preview.review.status == "pending" and preview.status == "DRAFT_FACT"
    assert preview.proposed_graph_patch.properties["action"] == "correct"
    assert preview.proposed_graph_patch.properties["supersedes_assertion_id"] == "state_" + original.id
    assert before == (len(graph.nodes), len(graph.event_log.list()))
    assert value(graph, "s3").value == "dead"
    review = ReviewService(candidates, graph, draft_store=drafts)
    review.submit([preview])
    reviewed = review.accept(preview.id, reviewer="author")
    assert value(graph, "s1").value == "alive" and value(graph, "s3").value == "alive"
    assert graph.nodes["state_" + original.id].model_dump() == old_node
    assert graph.event_log.get("evt_state_" + original.id).model_dump() == old_event
    assert "action" not in old_node["properties"] and "supersedes_assertion_id" not in old_node["properties"]
    receipt_count = len(graph.event_log.list())
    graph.commit_candidate_fact(reviewed, reviewer="author", rationale=reviewed.rationale)
    assert len(graph.event_log.list()) == receipt_count


def test_multiple_corrections_form_one_active_leaf_and_history_keeps_every_record(setup):
    graph, drafts, _ = setup
    original = accept(setup, candidate(setup))
    first = propose_state_correction(graph=graph, draft_store=drafts, project_id="p",
                                    request=requested_correction(setup, original))
    first = accept(setup, first)
    second = propose_state_correction(graph=graph, draft_store=drafts, project_id="p",
                                     request=requested_correction(setup, first, "dead"))
    accept(setup, second)
    active = get_state_assertions(graph, project_id="p", subject_id="hero", active_only=True)
    assert {node.id for node in active} == {"state_" + second.id}
    assert value(graph, "s3").value == "dead"
    history = temporal_state_history(graph, project_id="p", subject_id="hero", fields=["life_status"])
    rows = history["slots"][0]["assertions"]
    assert len(rows) == 3 and sum(row["active"] for row in rows) == 1
    assert {row["assertion"]["properties"]["value"] for row in rows} == {"alive", "dead"}


@pytest.mark.parametrize("override", [
    {"expected_source_sha256": "0" * 64}, {"expected_slot_fingerprint": "0" * 64},
    {"source_draft_id": "missing"}, {"expected_draft_version": 999},
    {"source_span": {"start_offset": 0, "end_offset": 3, "quote": "不存在"}},
    {"value": "zombie"}, {"value": "dead"},
])
def test_stale_invalid_or_noop_correction_is_write_free(setup, override):
    graph, drafts, _ = setup
    original = accept(setup, candidate(setup))
    request = requested_correction(setup, original)
    request = TemporalStateCorrectionRequest.model_validate({**request.model_dump(), **override})
    before = (len(graph.nodes), len(graph.event_log.list()))
    with pytest.raises((ValueError, ContractError, GraphStoreError)):
        propose_state_correction(graph=graph, draft_store=drafts, project_id="p", request=request)
    assert before == (len(graph.nodes), len(graph.event_log.list()))


def test_foreign_project_and_other_scene_source_cannot_correct(setup):
    graph, drafts, _ = setup
    original = accept(setup, candidate(setup))
    request = requested_correction(setup, original)
    graph.seed_canon_node(node_id="q", node_type="Project", properties={"language": "zh-CN"})
    with pytest.raises(GraphStoreError):
        propose_state_correction(graph=graph, draft_store=drafts, project_id="q", request=request)
    other = drafts.create_draft(project_id="p", scene_id="s3", content_language="zh-CN", text=request.source_span.quote)
    wrong = request.model_copy(update={"source_draft_id": other.id,
        "expected_draft_version": other.version, "expected_source_sha256": content_hash(other.text)})
    with pytest.raises(GraphStoreError):
        propose_state_correction(graph=graph, draft_store=drafts, project_id="p", request=wrong)


def test_review_edit_cannot_redirect_correction_to_other_state_slot(setup):
    graph, drafts, candidates = setup
    original = accept(setup, candidate(setup))
    other = accept(setup, candidate(setup, ref="fact_natural_other_field", field="physical_state", value="injured"))
    preview = propose_state_correction(graph=graph, draft_store=drafts, project_id="p",
                                      request=requested_correction(setup, original))
    review = ReviewService(candidates, graph, draft_store=drafts)
    review.submit([preview])
    with pytest.raises((ContractError, GraphStoreError)):
        review.edit_and_accept(preview.id, reviewer="author", patch_properties={"supersedes_assertion_id": "state_" + other.id})
    assert candidates.get(preview.id).review.status == "pending"
    assert value(graph, "s3").value == "dead"


def test_superseded_target_cannot_be_recorrected_from_stale_request(setup):
    graph, drafts, _ = setup
    original = accept(setup, candidate(setup))
    request = requested_correction(setup, original)
    preview = propose_state_correction(graph=graph, draft_store=drafts, project_id="p", request=request)
    accept(setup, preview)
    fresh_hash_old_target = request.model_copy(update={"expected_slot_fingerprint": temporal_slot_fingerprint(
        graph, project_id="p", subject_id="hero", field="life_status")})
    with pytest.raises(GraphStoreError):
        propose_state_correction(graph=graph, draft_store=drafts, project_id="p", request=fresh_hash_old_target)


def test_cyclic_correction_chain_is_ambiguous_and_active_read_fails_closed(setup):
    graph, drafts, _ = setup
    original = accept(setup, candidate(setup))
    correction = propose_state_correction(graph=graph, draft_store=drafts, project_id="p",
                                         request=requested_correction(setup, original))
    accept(setup, correction)
    # Simulate corrupted imported storage, not a supported author write.
    graph.nodes["state_" + original.id].properties.update(action="correct", supersedes_assertion_id="state_" + correction.id)
    assert value(graph, "s3").status == "ambiguous"
    with pytest.raises(GraphStoreError):
        get_state_assertions(graph, project_id="p", subject_id="hero", active_only=True)


def test_concurrent_corrections_have_one_canonical_winner(setup):
    graph, drafts, _ = setup
    original = accept(setup, candidate(setup))
    request = requested_correction(setup, original)
    previews = [propose_state_correction(graph=graph, draft_store=drafts, project_id="p", request=request)
                for _ in range(2)]
    barrier = Barrier(2)
    class RacingCandidates(InMemoryCandidateStore):
        def update_if_pending(self, candidate):
            result = super().update_if_pending(candidate)
            barrier.wait(timeout=3)
            return result
    candidates = RacingCandidates()
    review = ReviewService(candidates, graph, draft_store=drafts)
    review.submit(previews)
    def decide(preview):
        try:
            review.accept(preview.id, reviewer="author")
            return "accepted"
        except (ContractError, GraphStoreError):
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(decide, previews))
    assert sorted(results) == ["accepted", "conflict"]
    assert len(get_state_assertions(graph, project_id="p", subject_id="hero", active_only=True)) == 1
    assert sorted(candidates.get(p.id).review.status for p in previews) == ["accepted", "pending"]
