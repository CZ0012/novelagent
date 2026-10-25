"""Independent adversarial checks of autonomous planning and final adoption."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
import json
import sqlite3

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from apps.api.planning_run_routes import register_planning_run_routes
from storygraph.core.agent_config import AgentPermissionLevel, has_permission
from storygraph.core.config import StoryGraphSettings
from storygraph.core.errors import GraphStoreError
from storygraph.models.longform import Blueprint, LongformApplyRequest
from storygraph.models.planning_run import PlanningCall, PlanningRunControl, PlanningRunResume
from storygraph.services.book_bundle import apply_book_bundle
from storygraph.services.planning_run import PlanningExecution
from storygraph.services.planning_run import PlanningRunService
from storygraph.stores.planning_run_store import SQLitePlanningRunStore
from storygraph.stores.proposal_store import SQLiteProposalStore
from storygraph.stores.json_graph import load_json_graph, save_json_graph
from test_planning_run import setup as setup
from test_planning_run import create


def finished_bundle(setup):
    graph, proposals, runs, _, _, service, _ = setup
    finished = service.execute(create(setup).id)
    assert finished.status == "awaiting_review"
    bundle = proposals.get(finished.bundle_proposal_id)
    accepted = proposals.review(bundle.id, decision="accepted", reviewer="audit-author", expected_version=bundle.version)
    args = dict(graph=graph, proposals=proposals, runs=runs, project_id="book", proposal_id=accepted.id,
        request=LongformApplyRequest(expected_version=accepted.version, reviewer="audit-author"),
        persist_snapshot=lambda _: None)
    return finished, args


def stop_after_first_generation(setup):
    service, writer = setup[5], setup[3]
    run = create(setup)
    original = writer.generate
    def stop(request):
        current = service.get("book", run.id)
        assert current.pending_call is not None and current.calls_reserved == 1
        assert current.pending_call.task == "planning"
        service.stop("book", run.id, PlanningRunControl(expected_version=current.version))
        return original(request)
    writer.generate = stop
    paused = service.execute(run.id)
    writer.generate = original
    assert paused.pause_reason == "stopped" and paused.steps[0].proposal_ref
    return paused


def test_budget_is_durably_reserved_before_provider_and_no_child_is_human_accepted(setup):
    paused = stop_after_first_generation(setup)
    graph, proposals, _, writer, reviewer, _, _ = setup
    assert paused.calls_reserved == 1 and paused.pending_call is None
    assert len(writer.calls) == 1 and not reviewer.requests
    proposal = proposals.get(paused.steps[0].proposal_ref.id)
    assert proposal.status == "agent_revised" and proposal.review_decision.status == "none"
    assert len(graph.nodes) == 1 and not graph.relationships


def test_failed_checkpoint_transaction_rolls_back_inserted_artifact(setup):
    graph, proposals, runs, writer, _, service, _ = setup
    run = create(setup)
    step = run.steps[0]
    payload, _ = service._payload(run, step)
    from storygraph.services.llm_provider import LLMMessage, LLMRequest
    result = writer.generate(LLMRequest(model="fixture-model", messages=[LLMMessage("user", json.dumps(payload))]))
    authored = Blueprint.model_validate_json(result.content)
    artifact = service._new_proposal(run, step, authored, PlanningExecution(writer, "fixture-model"))
    runs._connection.execute("CREATE TRIGGER audit_fail_checkpoint BEFORE UPDATE ON planning_runs BEGIN SELECT RAISE(ABORT,'synthetic checkpoint failure'); END")
    runs._connection.commit()
    with pytest.raises(sqlite3.IntegrityError):
        runs.update(run.model_copy(update={"status": "paused"}), run.version, proposal=artifact)
    assert not proposals._exists(artifact.id)
    assert runs.get(run.id).version == run.version
    assert len(graph.nodes) == 1


def test_changed_exact_child_version_pauses_before_next_provider(setup):
    paused = stop_after_first_generation(setup)
    _, proposals, _, writer, reviewer, service, _ = setup
    ref = paused.steps[0].proposal_ref
    source = proposals.get(ref.id)
    proposals.revise(source.id, actor="author", title="作者改过的蓝图", expected_version=source.version)
    queued = service.resume("book", paused.id, PlanningRunResume(expected_version=paused.version))
    result = service.execute(queued.id)
    assert result.status == "paused" and result.pause_reason == "source_changed"
    assert len(writer.calls) == 1 and not reviewer.requests


def test_changed_planning_connection_is_not_silently_substituted(setup):
    paused = stop_after_first_generation(setup)
    _, _, _, writer, reviewer, service, _ = setup
    service.provider_factory = lambda task: PlanningExecution(writer if task == "planning" else reviewer,
        "changed-model" if task == "planning" else "fixture-model")
    result = service.execute(service.resume("book", paused.id,
        PlanningRunResume(expected_version=paused.version)).id)
    assert result.status == "paused" and result.pause_reason == "connection_changed"
    assert len(writer.calls) == 1


def test_same_process_duplicate_worker_does_not_duplicate_reserved_call(setup):
    _, _, runs, writer, _, service, _ = setup
    run = create(setup)
    entered, release = Event(), Event()
    original = writer.generate
    def block(request):
        entered.set()
        assert release.wait(timeout=4)
        current = runs.get(run.id)
        service.stop("book", run.id, PlanningRunControl(expected_version=current.version))
        return original(request)
    writer.generate = block
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(service.execute, run.id)
        assert entered.wait(timeout=4)
        duplicate = pool.submit(service.execute, run.id).result(timeout=4)
        assert duplicate.calls_reserved == 1 and duplicate.pending_call is not None
        release.set()
        result = first.result(timeout=4)
    assert result.pause_reason == "stopped" and len(writer.calls) == 1


def test_losing_cross_process_claim_cannot_pause_or_clear_winner_call(setup, monkeypatch):
    _, _, runs, writer, reviewer, service, _ = setup
    queued = create(setup)
    winner = runs.update(queued.model_copy(update={"status": "running", "owner_pid": 424242,
        "pending_call": PlanningCall(id="winning_reserved_call", task="planning", operation="generate", step_index=0),
        "calls_reserved": 1}), queued.version)
    original_get, first = runs.get, [True]
    def stale_read(run_id):
        # Process A read queued; process B claimed it before A's SQLite CAS.
        if first[0]:
            first[0] = False
            return queued
        return original_get(run_id)
    monkeypatch.setattr(runs, "get", stale_read)
    service.execute(queued.id)
    current = original_get(queued.id)
    assert current.status == winner.status == "running"
    assert current.pending_call == winner.pending_call
    assert current.calls_reserved == 1 and not writer.calls and not reviewer.requests


@pytest.mark.parametrize("tamper", ["marker_reviewer", "marker_rationale", "node_payload_id", "relation_payload_type"])
def test_completed_retry_rejects_corrupted_receipt_provenance_or_identity(setup, tamper):
    _, args = finished_bundle(setup)
    graph = setup[0]
    apply_book_bundle(**args)
    events = graph.event_log._events
    if tamper.startswith("marker"):
        index = next(i for i, event in enumerate(events) if event.event_id.startswith("evt_book_"))
        field = "reviewer" if tamper == "marker_reviewer" else "rationale"
        events[index] = events[index].model_copy(update={field: ""})
    else:
        operation = "create_node" if tamper == "node_payload_id" else "create_relation"
        index = next(i for i, event in enumerate(events) if event.operation == operation and "longform-book:" in event.source_ref)
        key = "id" if tamper == "node_payload_id" else "type"
        events[index] = events[index].model_copy(update={"payload": {**events[index].payload, key: "FORGED_RECEIPT_IDENTITY"}})
    before = (len(graph.nodes), len(graph.event_log.list()))
    with pytest.raises(GraphStoreError):
        apply_book_bundle(**args)
    assert before == (len(graph.nodes), len(graph.event_log.list()))


def test_stale_canon_and_unaccepted_bundle_never_apply(setup):
    finished, args = finished_bundle(setup)
    graph, proposals, _, _, _, _, _ = setup
    graph.update_node("book", {"genre": "作者的新决定"}, reviewer="author", rationale="明确修改", source_ref="manual")
    before = (len(graph.nodes), len(graph.event_log.list()))
    with pytest.raises(GraphStoreError):
        apply_book_bundle(**args)
    assert before == (len(graph.nodes), len(graph.event_log.list()))
    # Neither a report nor an accepted wrapper may silently accept child plans.
    assert all(proposals.get(s.proposal_ref.id).status == "agent_revised" for s in finished.steps)


def test_api_permissions_and_cross_project_reads_precede_any_provider(setup):
    graph, proposals, _, writer, reviewer, service, path = setup
    run = create(setup)
    settings, app = StoryGraphSettings(path), FastAPI()
    permission = [AgentPermissionLevel.READ_ONLY]
    def require(required):
        if not has_permission(permission[0], required):
            raise HTTPException(403, "Synthetic permission denied")
    register_planning_run_routes(app, graph=graph, settings=settings, proposals=proposals,
        require_permission=require, require_llm=lambda _: None,
        provider_factory=lambda runtime: writer if runtime.resolved_task == "planning" else reviewer,
        persist_snapshot=lambda _: None)
    with TestClient(app) as client:
        assert client.get(f"/projects/book/planning-runs/{run.id}").status_code == 200
        assert client.get(f"/projects/foreign/planning-runs/{run.id}").status_code == 404
        assert client.post("/projects/book/planning-runs", json={"instruction": "完整规划"}).status_code == 403
        assert client.post(f"/projects/book/planning-runs/{run.id}/stop", json={"expected_version": run.version}).status_code == 403
        permission[0] = AgentPermissionLevel.READ_GENERATE
        assert client.post("/projects/book/proposals/fake/apply/longform-book",
            json={"expected_version": 1, "reviewer": "author"}).status_code == 403
    assert not writer.calls and not reviewer.requests


def test_uncertain_call_persists_across_sqlite_restart_without_automatic_retry(setup):
    graph, _, _, writer, _, service, path = setup
    run = create(setup)
    def fail(_):
        raise RuntimeError("PRIVATE_PROVIDER_CONTENT must remain outside checkpoint")
    writer.generate = fail
    paused = service.execute(run.id)
    assert paused.pending_call is not None and paused.pause_reason == "uncertain_call"
    reopened_proposals = SQLiteProposalStore(path / "proposals.sqlite")
    reopened_runs = SQLitePlanningRunStore(reopened_proposals)
    reconstructed = PlanningRunService(graph=graph, proposals=reopened_proposals, runs=reopened_runs,
        provider_factory=lambda _: pytest.fail("restart/recovery must not invoke a provider"))
    reconstructed.recover_interrupted()
    persisted = reconstructed.get("book", run.id)
    assert persisted.pending_call == paused.pending_call and persisted.calls_reserved == 1
    assert "PRIVATE_PROVIDER_CONTENT" not in persisted.model_dump_json()
    with pytest.raises(GraphStoreError, match="explicitly resume"):
        reconstructed.resume("book", run.id, PlanningRunResume(expected_version=persisted.version))


def test_recovery_never_steals_a_live_foreign_owner(setup, monkeypatch):
    import storygraph.services.planning_run as module
    _, _, runs, _, _, service, _ = setup
    queued = create(setup)
    runs.update(queued.model_copy(update={"status": "running", "owner_pid": 9999999,
        "worker_token": "foreign-live-owner", "calls_reserved": 1,
        "pending_call": PlanningCall(id="call_foreign", task="planning", operation="generate", step_index=0)}), queued.version)
    monkeypatch.setattr(module, "_pid_alive", lambda _: True)
    assert service.recover_interrupted() == []
    assert runs.get(queued.id).status == "running"
    monkeypatch.setattr(module, "_pid_alive", lambda _: False)
    recovered = service.recover_interrupted()
    assert recovered[0].status == "paused" and recovered[0].pending_call is not None
    assert recovered[0].pause_reason == "uncertain_call"


def test_changed_child_invalidates_reviews_and_bundle_before_graph_write(setup):
    finished, args = finished_bundle(setup)
    graph, proposals, _, _, _, service, _ = setup
    child = proposals.get(finished.steps[1].proposal_ref.id)
    proposals.revise(child.id, actor="author", title="作者变更后的章节计划", expected_version=child.version)
    assert not service.review("book", finished.id, finished.final_review_id)["current"]
    before = (len(graph.nodes), len(graph.event_log.list()))
    with pytest.raises(GraphStoreError):
        apply_book_bundle(**args)
    assert before == (len(graph.nodes), len(graph.event_log.list()))


def test_failed_graph_persistence_publishes_no_book_or_derived_refs(setup):
    finished, args = finished_bundle(setup)
    graph, proposals, runs, _, _, _, _ = setup
    before = (len(graph.nodes), len(graph.event_log.list()))
    def fail(_):
        raise OSError("synthetic persistence failure")
    with pytest.raises(OSError):
        apply_book_bundle(**{**args, "persist_snapshot": fail})
    assert before == (len(graph.nodes), len(graph.event_log.list()))
    assert proposals.get(finished.bundle_proposal_id).derived_refs == []
    assert runs.get(finished.id).status == "awaiting_review"


def test_lost_derived_ref_checkpoint_recovers_from_durable_exact_graph_receipt(setup, monkeypatch):
    finished, args = finished_bundle(setup)
    graph, proposals, runs, _, _, _, path = setup
    original = proposals.record_derived_refs
    writes = []
    def persist(staged):
        writes.append(staged)
        save_json_graph(staged, path / "book-recovery.json")
    def fail(*_args, **_kwargs):
        raise RuntimeError("synthetic derived-ref checkpoint failure")
    monkeypatch.setattr(proposals, "record_derived_refs", fail)
    with pytest.raises(RuntimeError):
        apply_book_bundle(**{**args, "persist_snapshot": persist})
    assert len(writes) == 1 and len(graph.nodes) > 1
    monkeypatch.setattr(proposals, "record_derived_refs", original)
    restored = load_json_graph(path / "book-recovery.json")
    before = len(restored.event_log.list())
    result = apply_book_bundle(**{**args, "graph": restored, "persist_snapshot": persist})
    assert result["already_applied"] and len(writes) == 1
    assert len(restored.event_log.list()) == before and runs.get(finished.id).status == "completed"
