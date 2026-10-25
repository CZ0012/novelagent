"""Explicit recovery keeps text, never old acceptance or reviews; all data synthetic."""
import json

import pytest
from pydantic import ValidationError

from test_planning_run import setup as planning_setup, create
from storygraph.core.errors import GraphStoreError
from storygraph.models.planning_run import PlanningRunResume
from storygraph.services.llm_provider import LLMResponse
from storygraph.services.planning_run import branch_from_ref


@pytest.fixture
def setup(tmp_path):
    return planning_setup.__wrapped__(tmp_path)


def finished(setup):
    result = setup[5].execute(create(setup).id)
    assert result.status == "awaiting_review"
    return result


def restart(setup, run, **kwargs):
    return setup[5].resume("book", run.id, PlanningRunResume(expected_version=run.version,
        restart_from_step=0, revision_instruction="修订故事梗概，保留相容的后续创作。", **kwargs))


def target_writer(setup):
    writer = setup[3]
    generate = writer.generate
    def revision(request):
        payload = json.loads(request.messages[-1].content)
        if payload.get("revision_mode") == "targeted":
            writer.calls.append(request)
            return LLMResponse(json.dumps({"changes": [{"path": "/blueprint/synopsis",
                "before": payload["source_plan"]["synopsis"], "after": "信使追查钟塔的记忆债务，最终选择承担代价。"}]}, ensure_ascii=False))
        return generate(request)
    writer.generate = revision


def test_retained_exact_authored_fields_get_new_wrappers_and_fresh_reviews_without_generation(setup):
    graph, proposals, _, writer, reviewer, service, _ = setup
    old = finished(setup)
    original = [branch_from_ref(proposals, s.proposal_ref) for s in old.steps]
    before = dict(graph.nodes), list(graph.event_log.list())
    target_writer(setup)
    queued = restart(setup, old, preserve_later_outputs=True)
    assert all(s.status == "pending" and s.proposal_ref is None and s.review_id is None
               and s.retained_output_ref == old.steps[s.index].proposal_ref for s in queued.steps[1:])
    result = service.execute(queued.id)
    assert result.status == "awaiting_review", result.model_dump()
    assert len(writer.calls) == 6 and len(reviewer.requests) == 12
    assert result.calls_reserved == 18  # old11 + selected repair1 + five reviews + final1
    assert (graph.nodes, graph.event_log.list()) == before
    for step in result.steps[1:]:
        source = old.steps[step.index].proposal_ref
        artifact = proposals.get(step.proposal_ref.id)
        branch = branch_from_ref(proposals, step.proposal_ref)
        assert branch.expansion == original[step.index].expansion
        assert branch.previous_refs == [s.proposal_ref for s in result.steps[:step.index]]
        assert branch.blueprint_ref == result.steps[0].proposal_ref
        assert step.proposal_ref.id != source.id and step.review_id != old.steps[step.index].review_id
        assert step.retained_output_ref == source and artifact.status == "agent_revised"
        assert artifact.provenance.created_via == "workflow"
        assert artifact.provenance.model_ref == proposals.get(source.id).provenance.model_ref
        assert any(r.ref == source.id and r.source_span == {"version": source.version, "sha256": source.body_sha256} for r in artifact.source_refs)
        assert service.review("book", result.id, step.review_id)["current"]
    assert service.review("book", result.id, result.final_review_id)["current"]


@pytest.mark.parametrize("flags", [{"preserve_later_outputs": True}, {"revision_mode": "full"},
    {"restart_from_step": 0, "revision_mode": "full"},
    {"restart_from_step": 0, "revision_instruction": " ", "revision_mode": "full"},
    {"restart_from_step": 0, "preserve_later_outputs": True, "recheck_current_step": True}])
def test_recovery_requires_explicit_compatible_controls(flags):
    with pytest.raises(ValidationError):
        PlanningRunResume(expected_version=1, **flags)


def test_full_selected_revision_uses_full_schema_and_retains_later_exact_fields(setup):
    old = finished(setup)
    original = setup[3].generate
    def full(request):
        payload = json.loads(request.messages[-1].content)
        if payload.get("revision_mode") == "full":
            assert "allowed_paths" not in payload and "current_values" not in payload
            assert payload["source_plan"]["synopsis"]
        response = original(request)
        if payload.get("revision_mode") == "full":
            raw = json.loads(response.content)
            raw["synopsis"] = "信使重新检验钟塔的记忆债务，最终承担明确代价。"
            return LLMResponse(json.dumps(raw, ensure_ascii=False))
        return response
    setup[3].generate = full
    queued = restart(setup, old, preserve_later_outputs=True, revision_mode="full")
    result = setup[5].execute(queued.id)
    assert result.status == "awaiting_review", result.model_dump()
    assert len(setup[3].calls) == 6
    assert branch_from_ref(setup[1], result.steps[0].proposal_ref).blueprint.synopsis.startswith("信使重新")


@pytest.mark.parametrize("damage", ["edit", "reject", "accept"])
def test_retained_source_change_stops_before_any_new_call(setup, damage):
    old = finished(setup)
    queued = restart(setup, old, preserve_later_outputs=True)
    source = setup[1].get(old.steps[2].proposal_ref.id)
    if damage == "edit":
        setup[1].revise(source.id, actor="author", body=source.body+" ", expected_version=source.version)
    else:
        setup[1].review(source.id, decision="accepted" if damage == "accept" else "rejected", reviewer="author", expected_version=source.version)
    result = setup[5].execute(queued.id)
    assert result.status == "paused" and result.pause_reason in {"source_changed", "retained_source_invalid"}
    assert len(setup[3].calls) == 5 and len(setup[4].requests) == 6


def test_incompatible_retained_ids_pause_without_regeneration_or_review(setup):
    old = finished(setup)
    original = setup[3].generate
    def renamed(request):
        response = original(request)
        raw = json.loads(response.content)
        if json.loads(request.messages[-1].content).get("revision_mode") == "full":
            raw["entities"][0]["id"] = "new_courier"
            raw["character_arcs"][0]["character_id"] = "new_courier"
            raw["foreshadowing"][0]["character_ids"] = ["new_courier"]
        return LLMResponse(json.dumps(raw, ensure_ascii=False))
    setup[3].generate = renamed
    result = setup[5].execute(restart(setup, old, preserve_later_outputs=True, revision_mode="full").id)
    assert result.status == "paused" and result.pause_reason == "retained_incompatible", result.model_dump()
    assert len(setup[3].calls) == 6 and len(setup[4].requests) == 7
    assert result.steps[1].proposal_ref is None and result.pending_call is None


def test_accepted_bundle_cannot_be_restarted_with_retention(setup):
    old = finished(setup)
    bundle = setup[1].get(old.bundle_proposal_id)
    setup[1].review(bundle.id, decision="accepted", reviewer="author", expected_version=bundle.version)
    with pytest.raises(GraphStoreError):
        restart(setup, old, preserve_later_outputs=True)


def test_copy_checkpoint_failure_rolls_back_artifact_and_never_calls_provider(setup, monkeypatch):
    old = finished(setup)
    target_writer(setup)
    service, runs, proposals = setup[5], setup[2], setup[1]
    queued = restart(setup, old, preserve_later_outputs=True)
    update = runs.update
    before_failure = {}
    def failing(run, version, **kwargs):
        proposal = kwargs.get("proposal")
        if proposal is not None and proposal.provenance.created_via == "workflow":
            before_failure["count"] = len(proposals.list())
            before_failure["id"] = proposal.id
            # Simulate failure after insertion, before checkpoint CAS; helper must rollback.
            proposals._insert(proposal)
            raise OSError("synthetic checkpoint failure")
        return update(run, version, **kwargs)
    monkeypatch.setattr(runs, "update", failing)
    result = service.execute(queued.id)
    assert result.status == "paused" and result.pause_reason == "execution_failed"
    assert result.steps[1].proposal_ref is None and result.steps[1].retained_output_ref is not None
    assert len(proposals.list()) == before_failure["count"]
    assert not proposals._exists(before_failure["id"])
    assert len(setup[3].calls) == 6 and len(setup[4].requests) == 7


def test_copy_costs_zero_calls_even_when_review_budget_is_exhausted(setup):
    old = finished(setup)
    target_writer(setup)
    queued = restart(setup, old, preserve_later_outputs=True)
    runs, service = setup[2], setup[5]
    queued = runs.update(queued.model_copy(update={"max_calls": old.calls_reserved+2}), queued.version)
    result = service.execute(queued.id)
    assert result.status == "paused" and result.pause_reason == "call_budget"
    assert result.calls_reserved == old.calls_reserved+2
    assert result.steps[1].status == "generated" and result.steps[1].proposal_ref is not None
    assert result.steps[1].review_id is None
    assert len(setup[3].calls) == 6 and len(setup[4].requests) == 7


def test_stop_before_copy_preserves_seed_without_artifact_or_review(setup, monkeypatch):
    old = finished(setup)
    target_writer(setup)
    service, runs, proposals = setup[5], setup[2], setup[1]
    queued = restart(setup, old, preserve_later_outputs=True)
    copy = service._copy_retained_output
    from storygraph.models.planning_run import PlanningRunControl
    def stop_then_copy(run, step):
        service.stop("book", run.id, PlanningRunControl(expected_version=run.version))
        # Copy must re-read current stop flag, not trust caller snapshot.
        return copy(runs.get(run.id), step)
    monkeypatch.setattr(service, "_copy_retained_output", stop_then_copy)
    result = service.execute(queued.id)
    assert result.status == "paused" and result.pause_reason == "stopped"
    assert result.steps[1].proposal_ref is None and len(proposals.list()) == 7
    assert len(setup[3].calls) == 6 and len(setup[4].requests) == 7


def test_retained_source_change_invalidates_fresh_report(setup):
    old = finished(setup)
    target_writer(setup)
    result = setup[5].execute(restart(setup, old, preserve_later_outputs=True).id)
    source = setup[1].get(old.steps[1].proposal_ref.id)
    setup[1].revise(source.id, actor="author", body=source.body+" ", expected_version=source.version)
    assert not setup[5].review("book", result.id, result.final_review_id)["current"]
    assert not setup[5].review("book", result.id, result.steps[1].review_id)["current"]


def test_losing_worker_cannot_copy_retained_output(setup, monkeypatch):
    old = finished(setup)
    target_writer(setup)
    service, runs, proposals = setup[5], setup[2], setup[1]
    queued = restart(setup, old, preserve_later_outputs=True)
    copy = service._copy_retained_output
    def lose_owner(run, step):
        changed = runs.update(run.model_copy(update={"worker_token": "different-worker"}), run.version)
        return copy(changed, step)
    monkeypatch.setattr(service, "_copy_retained_output", lose_owner)
    result = service.execute(queued.id)
    assert result.worker_token == "different-worker" and result.steps[1].proposal_ref is None
    assert len(proposals.list()) == 7
    assert len(setup[3].calls) == 6 and len(setup[4].requests) == 7
