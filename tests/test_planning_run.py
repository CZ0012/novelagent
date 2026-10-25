"""Bounded autonomous planning never writes canon before bundle acceptance."""

import json

import pytest

from test_longform_planning import Provider
from storygraph.core.errors import GraphStoreError
from storygraph.models.generation_review import REVIEW_DIMENSIONS
from storygraph.models.longform import LongformApplyRequest
from storygraph.models.planning_run import PlanningRunRequest, PlanningRunControl, PlanningRunResume
from storygraph.services.book_bundle import apply_book_bundle
from storygraph.services.llm_provider import LLMResponse
from storygraph.services.planning_run import PlanningExecution, PlanningRunService
from storygraph.stores.json_graph import save_json_graph, load_json_graph
from storygraph.stores.memory_graph import InMemoryGraphStore
from storygraph.stores.proposal_store import SQLiteProposalStore
from storygraph.stores.planning_run_store import SQLitePlanningRunStore


class Reviewer:
    def __init__(self):
        self.requests = []
    def generate(self, request):
        self.requests.append(request)
        return LLMResponse(json.dumps({"status": "pass", "summary": "所列规划范围内没有发现明确矛盾。",
            "dimensions_checked": list(REVIEW_DIMENSIONS), "issues": []}, ensure_ascii=False))


@pytest.fixture
def setup(tmp_path):
    graph = InMemoryGraphStore()
    graph.seed_canon_node(node_id="book", node_type="Project", properties={"title": "测试作品", "language": "zh-CN"},
        source_ref="test:planning", reviewer="author", rationale="合成设定。")
    proposals = SQLiteProposalStore(tmp_path/"proposals.sqlite")
    runs = SQLitePlanningRunStore(proposals)
    writer, reviewer = Provider(), Reviewer()
    writer.chapters_per_volume, writer.scenes_per_chapter = 2, 2
    service = PlanningRunService(graph=graph, proposals=proposals, runs=runs,
        provider_factory=lambda task: PlanningExecution(writer if task == "planning" else reviewer, "fixture-model"))
    return graph, proposals, runs, writer, reviewer, service, tmp_path


def create(setup, **kwargs):
    return setup[5].create("book", PlanningRunRequest(instruction="设计完整的合成小说框架。", volume_count=2,
        chapters_per_volume=2, scenes_per_chapter=2, batch_size=1, **kwargs))


def test_entire_book_branch_then_single_atomic_human_application(setup):
    graph, proposals, runs, writer, reviewer, service, path = setup
    run = create(setup)
    before = dict(graph.nodes), list(graph.event_log.list())
    finished = service.execute(run.id)
    assert finished.status == "awaiting_review", finished.model_dump()
    assert finished.stage == "done" and all(s.status == "passed" for s in finished.steps)
    assert finished.calls_reserved == 11 and len(writer.calls) == 5 and len(reviewer.requests) == 6
    assert (graph.nodes, graph.event_log.list()) == before
    assert all(proposals.get(s.proposal_ref.id).status == "agent_revised" for s in finished.steps)
    assert service.review("book", run.id, finished.final_review_id)["current"]
    bundle = proposals.get(finished.bundle_proposal_id)
    accepted = proposals.review(bundle.id, decision="accepted", reviewer="author", expected_version=bundle.version)
    args = dict(graph=graph, proposals=proposals, runs=runs, project_id="book", proposal_id=accepted.id,
        request=LongformApplyRequest(expected_version=accepted.version, reviewer="author"),
        persist_snapshot=lambda staged: save_json_graph(staged, path/"graph.json"))
    applied = apply_book_bundle(**args)
    assert not applied["already_applied"] and runs.get(run.id).status == "completed"
    assert len([n for n in graph.nodes.values() if n.type == "Scene"]) == 8
    assert sum(n.properties["target_length"] for n in graph.nodes.values() if n.type == "Scene") == 500000
    reloaded = load_json_graph(path/"graph.json")
    count = len(reloaded.event_log.list())
    assert apply_book_bundle(**{**args, "graph": reloaded})["already_applied"]
    assert len(reloaded.event_log.list()) == count
    assert all(proposals.get(s.proposal_ref.id).status == "agent_revised" for s in finished.steps)


def test_call_budget_pauses_and_explicit_increase_resumes_without_replaying_outputs(setup):
    run = create(setup, max_calls=2)
    service = setup[5]
    paused = service.execute(run.id)
    assert paused.status == "paused" and paused.pause_reason == "call_budget"
    first_ref = paused.steps[0].proposal_ref
    queued = service.resume("book", run.id, PlanningRunResume(expected_version=paused.version, max_calls=20))
    finished = service.execute(queued.id)
    assert finished.status == "awaiting_review" and finished.steps[0].proposal_ref == first_ref
    assert len(setup[3].calls) == 5


def test_stop_during_provider_call_saves_result_and_makes_no_next_paid_call(setup):
    run = create(setup)
    service = setup[5]
    original = setup[3].generate
    def stop(request):
        current = service.get("book", run.id)
        service.stop("book", run.id, PlanningRunControl(expected_version=current.version))
        return original(request)
    setup[3].generate = stop
    paused = service.execute(run.id)
    assert paused.status == "paused" and paused.pause_reason == "stopped"
    assert paused.steps[0].proposal_ref is not None and not setup[4].requests
    assert len(setup[3].calls) == 1


def test_uncertain_provider_failure_needs_explicit_paid_retry_authorization(setup):
    run = create(setup)
    service = setup[5]
    def fail(_):
        raise RuntimeError("private provider text must never enter checkpoint")
    setup[3].generate = fail
    paused = service.execute(run.id)
    assert paused.pause_reason == "uncertain_call" and paused.pending_call is not None
    assert "private" not in paused.model_dump_json()
    with pytest.raises(GraphStoreError):
        service.resume("book", run.id, PlanningRunResume(expected_version=paused.version))
    resumed = service.resume("book", run.id, PlanningRunResume(expected_version=paused.version, retry_uncertain_call=True))
    assert resumed.status == "queued" and resumed.calls_reserved == 1


def test_canon_change_does_not_relabel_frozen_snapshot_or_write_any_plan_canon(setup):
    run = create(setup)
    graph, _, _, writer, _, service, _ = setup
    graph.update_node("book", {"genre": "作者修改"}, reviewer="author", rationale="合成修改。", source_ref="test:edit")
    paused = service.execute(run.id)
    assert paused.pause_reason == "canon_changed" and paused.canon_fingerprint == run.canon_fingerprint
    assert not writer.calls and len(graph.nodes) == 1


def test_running_checkpoint_recovery_marks_uncertain_without_spending(setup):
    from storygraph.models.planning_run import PlanningCall
    run = create(setup)
    runs, service = setup[2], setup[5]
    runs.update(run.model_copy(update={"status": "running", "pending_call": PlanningCall(id="call_crashed",
        task="planning", operation="generate", step_index=0), "calls_reserved": 1}), run.version)
    recovered = service.recover_interrupted()
    assert recovered[0].pause_reason == "uncertain_call" and not setup[3].calls


def test_default_500k_whole_framework_is_generated_without_any_intermediate_human_apply(setup):
    graph, _, _, writer, _, service, _ = setup
    writer.chapters_per_volume = 20
    run = service.create("book", PlanningRunRequest(instruction="独立规划五十万字完整框架。"))
    final = service.execute(run.id)
    assert final.status == "awaiting_review" and len(final.steps) == 21
    assert final.calls_reserved == 43 and len(graph.nodes) == 1
    from storygraph.services.book_bundle import bundle_specs
    nodes, _, _ = bundle_specs(graph, setup[1], final)
    assert len([n for n in nodes.values() if n[0] == "Chapter"]) == 100
    assert len([n for n in nodes.values() if n[0] == "Scene"]) == 200
    assert sum(props["target_length"] for kind, props in nodes.values() if kind == "Scene") == 500000


def test_inconclusive_review_explicit_resume_rechecks_without_blind_paid_repair(setup):
    run = create(setup)
    reviewer, service = setup[4], setup[5]
    original = reviewer.generate
    first = True
    def once(request):
        nonlocal first
        if first:
            first = False
            reviewer.requests.append(request)
            return LLMResponse("{}")
        return original(request)
    reviewer.generate = once
    paused = service.execute(run.id)
    assert paused.pause_reason == "review_failed" and len(setup[3].calls) == 1
    queued = service.resume("book", run.id, PlanningRunResume(expected_version=paused.version))
    assert queued.steps[0].status == "generated"
    finished = service.execute(run.id)
    assert finished.status == "awaiting_review" and finished.steps[0].repairs == 0
    assert len(setup[3].calls) == 5 and finished.calls_reserved == 12


def test_failed_final_review_can_be_explicitly_rechecked_without_regenerating_book(setup):
    run = create(setup)
    reviewer, service = setup[4], setup[5]
    original = reviewer.generate
    first = True
    def once(request):
        nonlocal first
        payload = json.loads(request.messages[-1].content)
        if first and payload["target"]["target_id"].startswith("book_review_"):
            first = False
            reviewer.requests.append(request)
            return LLMResponse("{}")
        return original(request)
    reviewer.generate = once
    paused = service.execute(run.id)
    assert paused.stage == "book_review" and paused.pause_reason == "review_failed"
    old_refs = [s.proposal_ref for s in paused.steps]
    queued = service.resume("book", run.id, PlanningRunResume(expected_version=paused.version))
    assert queued.final_review_id is None
    finished = service.execute(run.id)
    assert finished.status == "awaiting_review" and [s.proposal_ref for s in finished.steps] == old_refs
    assert len(setup[3].calls) == 5 and finished.calls_reserved == 12


def test_author_restart_targets_one_step_and_invalidates_downstream_without_deleting_artifacts(setup):
    run = create(setup)
    _, proposals, _, writer, _, service, _ = setup
    first = service.execute(run.id)
    old_refs = [step.proposal_ref for step in first.steps]
    old_bundle = proposals.get(first.bundle_proposal_id)
    original = writer.generate
    def targeted(request):
        payload = json.loads(request.messages[-1].content)
        if payload.get("revision_mode") == "targeted":
            writer.calls.append(request)
            before = payload["current_values"]["/blueprint/synopsis"]
            return LLMResponse(json.dumps({"changes": [{"path": "/blueprint/synopsis", "before": before,
                "after": before+"所有案件依靠保管链与具名证据闭环。"}]}, ensure_ascii=False))
        return original(request)
    writer.generate = targeted
    queued = service.resume("book", run.id, PlanningRunResume(expected_version=first.version,
        restart_from_step=0, revision_instruction="只补足案件证据闭环。"))
    assert queued.steps[0].status == "needs_revision" and queued.steps[0].proposal_ref == old_refs[0]
    assert all(s.status == "pending" and s.proposal_ref is None for s in queued.steps[1:])
    assert queued.final_review_id is None and queued.bundle_proposal_id is None
    final = service.execute(run.id)
    assert final.status == "awaiting_review" and final.steps[0].repairs == 1
    assert final.bundle_proposal_id != old_bundle.id
    assert all(proposals.get(ref.id).version == ref.version for ref in old_refs)
    assert proposals.get(old_bundle.id).status == "agent_revised"
    assert final.restart_history[0]["source_ref"]["id"] == old_refs[0].id


def test_exact_unapplied_seed_copies_provenance_without_generation_call_and_still_requires_review(setup):
    from storygraph.models.longform import BlueprintRequest
    from storygraph.services.longform_planning import generate_blueprint
    graph, proposals, _, writer, reviewer, service, _ = setup
    config = BlueprintRequest(instruction="设计完整的合成小说框架。", volume_count=2, chapters_per_volume=2, scenes_per_chapter=2)
    source = generate_blueprint(graph=graph, store=proposals, project_id="book", request=config,
        provider=writer, model="fixture-model")["proposal"]
    calls = len(writer.calls)
    run = service.create("book", PlanningRunRequest(**config.model_dump(), batch_size=1,
        seed_blueprint_id=source["id"], seed_blueprint_version=source["version"]))
    assert len(writer.calls) == calls and run.calls_reserved == 0 and run.steps[0].status == "generated"
    copied = proposals.get(run.steps[0].proposal_ref.id)
    assert copied.provenance.created_via == "workflow" and "未调用模型" in copied.provenance.note
    assert copied.provenance.model_ref == source["provenance"]["model_ref"]
    assert proposals.get(source["id"]).model_dump() == source and not reviewer.requests
    result = service.execute(run.id)
    assert result.status == "awaiting_review" and result.calls_reserved == 10
    assert len(writer.calls)-calls == 4 and len(reviewer.requests) == 6
    assert len(graph.nodes) == 1


def test_seed_wrong_version_request_or_later_edit_never_substitutes_latest(setup):
    from storygraph.models.longform import BlueprintRequest
    from storygraph.services.longform_planning import generate_blueprint
    graph, proposals, _, writer, _, service, _ = setup
    config = BlueprintRequest(instruction="设计完整的合成小说框架。", volume_count=2, chapters_per_volume=2, scenes_per_chapter=2)
    source = generate_blueprint(graph=graph, store=proposals, project_id="book", request=config,
        provider=writer, model="fixture-model")["proposal"]
    for values in ({"seed_blueprint_version": 99}, {"instruction": "换一个指令"}):
        fields = {**config.model_dump(), "seed_blueprint_id": source["id"], "seed_blueprint_version": source["version"], **values}
        with pytest.raises(GraphStoreError):
            service.create("book", PlanningRunRequest(**fields))
    run = service.create("book", PlanningRunRequest(**config.model_dump(), batch_size=1,
        seed_blueprint_id=source["id"], seed_blueprint_version=source["version"]))
    proposals.revise(source["id"], actor="author", title="作者修改的蓝图", expected_version=source["version"])
    result = service.execute(run.id)
    assert result.pause_reason == "source_changed" and result.calls_reserved == 0
