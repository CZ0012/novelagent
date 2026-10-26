"""Bounded autonomous planning never writes canon before bundle acceptance."""

import json

import pytest

from test_longform_planning import Provider, creative_expansion
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


@pytest.mark.parametrize("response_format", ["legacy", "creative"])
def test_default_500k_whole_framework_is_generated_without_any_intermediate_human_apply(setup, response_format):
    graph, _, _, writer, _, service, _ = setup
    writer.chapters_per_volume = 20
    sealed = "原始日志已由两位审计员登记封存，后续复制仅作工作副本。"
    def retain_early_fact(output):
        if "chapters" in output:
            for chapter in output["chapters"]:
                for scene in chapter["scenes"]:
                    if scene["id"] == "v01_c001_s01":
                        scene["outcome"] = sealed
    writer.mutate = retain_early_fact
    if response_format == "creative":
        original = writer.generate
        def creative(request):
            response = original(request)
            if json.loads(request.messages[-1].content)["phase"] == "expansion":
                return LLMResponse(json.dumps(creative_expansion(json.loads(response.content)), ensure_ascii=False))
            return response
        writer.generate = creative
    run = service.create("book", PlanningRunRequest(instruction="独立规划五十万字完整框架。"))
    final = service.execute(run.id)
    assert final.status == "awaiting_review" and len(final.steps) == 21
    assert final.calls_reserved == 43 and len(graph.nodes) == 1
    from storygraph.services.book_bundle import bundle_specs
    nodes, _, _ = bundle_specs(graph, setup[1], final)
    assert len([n for n in nodes.values() if n[0] == "Chapter"]) == 100
    assert len([n for n in nodes.values() if n[0] == "Scene"]) == 200
    assert sum(props["target_length"] for kind, props in nodes.values() if kind == "Scene") == 500000
    from storygraph.services.planning_run import book_projection, branch_from_ref
    ledger = book_projection(setup[1], final)
    text = json.dumps(ledger, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert len(text) < 200000
    exact = {scene.id: scene for step in final.steps[1:] for chapter in branch_from_ref(setup[1], step.proposal_ref).expansion.chapters for scene in chapter.scenes}
    for volume in ledger["volumes"]:
        for chapter in volume["chapters"]:
            for scene in chapter["scenes"]:
                assert scene["timeline_position"] == exact[scene["id"]].timeline_position
                assert scene["required_characters"] == exact[scene["id"]].required_characters
                assert scene["pov_character_id"] == exact[scene["id"]].pov_character_id
                assert scene["location_id"] == exact[scene["id"]].location_id
    last = json.loads(writer.calls[-1].messages[-1].content)["proposed_planning_context"]
    assert len(last["recent_scene_outcomes"]) == 12
    assert all(scene["id"] != "v01_c001_s01" for scene in last["recent_scene_outcomes"])
    assert len(last["prior_scene_outcome_ledger"]["scenes"]) == 190
    assert last["prior_scene_outcome_ledger"]["scenes"][0]["outcome"] == sealed


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


def test_advisory_only_critic_does_not_trigger_paid_repair(setup):
    run = create(setup)
    reviewer, service = setup[4], setup[5]
    original = reviewer.generate
    first = True
    def advisory(request):
        nonlocal first
        if first:
            first = False
            reviewer.requests.append(request)
            payload = json.loads(request.messages[-1].content)
            target_sources = [(key, value) for key, value in payload["evidence_sources"].items() if value["kind"] == "target"]
            selected, quotes = [], set()
            for key, value in target_sources:
                if value["quote"] not in quotes:
                    selected.append({"source_id": key})
                    quotes.add(value["quote"])
                if len(selected) == 2:
                    break
            return LLMResponse(json.dumps({"evidence_registry_id": payload["evidence_registry_id"], "status": "needs_revision", "summary": "可在扩章时细化交接。",
                "dimensions_checked": list(REVIEW_DIMENSIONS), "issues": [{"id": "advice", "dimension": "timeline",
                "finding": "advice", "severity": "low", "description": "可在扩章时补充交接步骤。", "suggestion": "补充具体时间即可。",
                "evidence": selected}]}, ensure_ascii=False))
        return original(request)
    reviewer.generate = advisory
    final = service.execute(run.id)
    assert final.status == "awaiting_review" and final.steps[0].repairs == 0
    assert final.calls_reserved == 11 and len(setup[3].calls) == 5
    report = setup[2].report(run.id, final.steps[0].review_id)
    assert report.status == "pass" and report.issues[0].finding == "advice"


def test_explicit_recheck_preserves_refs_and_exhausted_repair_count_without_regeneration(setup):
    run = create(setup, max_calls=1)
    _, _, runs, writer, reviewer, service, _ = setup
    paused = service.execute(run.id)
    steps = [step.model_copy(deep=True) for step in paused.steps]
    steps[0].status, steps[0].repairs = "needs_revision", 2
    paused = runs.update(paused.model_copy(update={"steps": steps, "pause_reason": "repair_limit"}), paused.version)
    refs_before = [step.proposal_ref for step in paused.steps]
    original = reviewer.generate
    first = True
    def advisory(request):
        nonlocal first
        if not first:
            return original(request)
        first = False
        reviewer.requests.append(request)
        payload = json.loads(request.messages[-1].content)
        entries = [(key, entry) for key, entry in payload["evidence_sources"].items() if entry["kind"] == "target"]
        first_key, first_entry = entries[0]
        second_key = next(key for key, entry in entries if entry["quote"] != first_entry["quote"])
        return LLMResponse(json.dumps({"evidence_registry_id": payload["evidence_registry_id"], "status": "needs_revision", "summary": "可以在扩章中补充可选细节。",
            "dimensions_checked": list(REVIEW_DIMENSIONS), "issues": [{"id": "optional", "dimension": "timeline",
            "finding": "advice", "severity": "low", "description": "可补充具体交接时刻。", "suggestion": "扩章时写明即可。",
            "evidence": [{"source_id": first_key}, {"source_id": second_key}]}]}, ensure_ascii=False))
    reviewer.generate = advisory
    queued = service.resume("book", run.id, PlanningRunResume(expected_version=paused.version,
        max_calls=20, recheck_current_step=True))
    assert [step.proposal_ref for step in queued.steps] == refs_before
    assert queued.steps[0].status == "generated" and queued.steps[0].review_id is None and queued.steps[0].repairs == 2
    final = service.execute(run.id)
    assert final.status == "awaiting_review" and final.steps[0].proposal_ref == refs_before[0]
    assert final.steps[0].repairs == 2 and len(writer.calls) == 5


def test_recheck_rejects_changed_source_before_any_new_call(setup):
    run = create(setup, max_calls=1)
    _, proposals, runs, writer, reviewer, service, _ = setup
    paused = service.execute(run.id)
    source = proposals.get(paused.steps[0].proposal_ref.id)
    proposals.revise(source.id, actor="author", body="{}", expected_version=source.version)
    with pytest.raises(GraphStoreError):
        service.resume("book", run.id, PlanningRunResume(expected_version=paused.version, recheck_current_step=True))
    assert runs.get(run.id).status == "paused" and len(writer.calls) == 1 and not reviewer.requests


def test_book_bundle_applies_explicit_character_secret_knowledge_without_child_acceptance(setup):
    graph, proposals, runs, writer, _, service, _ = setup
    original = writer.generate
    def generation(request):
        response = original(request)
        payload = json.loads(request.messages[-1].content)
        if payload["phase"] == "blueprint":
            output = json.loads(response.content)
            output["entities"].append({"id": "secret_origin", "kind": "Secret", "name": "时钟来历",
                "description": "时钟利用真实记忆运转。"})
            output["entities"][0]["initial_knowledge"] = ["secret_origin"]
            return LLMResponse(json.dumps(output, ensure_ascii=False))
        return response
    writer.generate = generation
    run = service.execute(create(setup).id)
    assert run.status == "awaiting_review" and len(graph.nodes) == 1
    bundle = proposals.get(run.bundle_proposal_id)
    accepted = proposals.review(bundle.id, decision="accepted", reviewer="author", expected_version=bundle.version)
    result = apply_book_bundle(graph=graph, proposals=proposals, runs=runs, project_id="book", proposal_id=bundle.id,
        request=LongformApplyRequest(expected_version=accepted.version, reviewer="author"), persist_snapshot=lambda _: None)
    knowledge = [edge for edge in result["relationships"] if edge["type"] == "KNOWS_SECRET"]
    assert len(knowledge) == 1 and knowledge[0]["properties"]["initial_knowledge"] is True
    assert knowledge[0]["target_id"] in graph.get_character_knowledge(knowledge[0]["source_id"]).knows
    assert all(proposals.get(step.proposal_ref.id).status == "agent_revised" for step in run.steps)


def test_copy_passed_branch_blueprint_makes_no_calls_or_canon_changes_and_new_seed_rechecks(setup):
    from storygraph.services.longform_planning import parse_longform
    graph, proposals, runs, writer, reviewer, service, _ = setup
    paused = service.execute(create(setup, max_calls=2).id)
    assert paused.status == "paused" and paused.steps[0].status == "passed"
    run_before = paused.model_dump()
    source = proposals.get(paused.steps[0].proposal_ref.id)
    before = len(writer.calls), len(reviewer.requests), dict(graph.nodes), list(graph.event_log.list())
    copied = service.copy_blueprint("book", paused.id, PlanningRunControl(expected_version=paused.version))
    assert copied.id != source.id and copied.status == "agent_revised" and copied.version == 1
    assert copied.provenance.created_via == "workflow" and "未调用模型" in copied.provenance.note
    assert copied.provenance.model_ref == source.provenance.model_ref
    assert copied.provenance.model_execution == source.provenance.model_execution
    assert parse_longform(copied.body).blueprint.model_dump() == json.loads(source.body)["blueprint"]
    assert any(ref.kind == "proposal_artifact" and ref.ref == source.id and ref.source_span == {
        "version": source.version, "sha256": paused.steps[0].proposal_ref.body_sha256} for ref in copied.source_refs)
    assert runs.get(paused.id).model_dump() == run_before and proposals.get(source.id) == source
    assert (len(writer.calls), len(reviewer.requests), graph.nodes, graph.event_log.list()) == before
    config = parse_longform(copied.body).request
    seeded = service.create("book", PlanningRunRequest(**config.model_dump(), batch_size=1, max_calls=1,
        seed_blueprint_id=copied.id, seed_blueprint_version=copied.version))
    rechecked = service.execute(seeded.id)
    assert rechecked.steps[0].status == "passed" and rechecked.calls_reserved == 1
    assert len(writer.calls) == before[0] and len(reviewer.requests) == before[1]+1


@pytest.mark.parametrize("damage", ["version", "pending", "source_edit", "source_reject", "canon", "unpassed", "completed"])
def test_copy_blueprint_rejects_stale_unknown_or_unreviewed_sources_before_any_call(setup, damage):
    from storygraph.models.planning_run import PlanningCall
    graph, proposals, runs, writer, reviewer, service, _ = setup
    paused = service.execute(create(setup, max_calls=2).id)
    expected = paused.version
    source = proposals.get(paused.steps[0].proposal_ref.id)
    if damage == "version":
        expected += 1
    elif damage == "pending":
        paused = runs.update(paused.model_copy(update={"pending_call": PlanningCall(id="uncertain", task="planning",
            operation="generate", step_index=1), "pause_reason": "uncertain_call"}), paused.version)
        expected = paused.version
    elif damage == "source_edit":
        proposals.revise(source.id, actor="author", body="{}", expected_version=source.version)
    elif damage == "source_reject":
        proposals.review(source.id, decision="rejected", reviewer="author", expected_version=source.version)
    elif damage == "canon":
        graph.update_node("book", {"genre": "新设定"}, reviewer="author", rationale="合成修改。", source_ref="test:edit")
    elif damage == "unpassed":
        steps = [step.model_copy(deep=True) for step in paused.steps]
        steps[0].status = "generated"
        paused = runs.update(paused.model_copy(update={"steps": steps}), paused.version)
        expected = paused.version
    else:
        paused = runs.update(paused.model_copy(update={"status": "completed"}), paused.version)
        expected = paused.version
    before = len(writer.calls), len(reviewer.requests), len(proposals.list()), dict(graph.nodes), list(graph.event_log.list())
    with pytest.raises(GraphStoreError):
        service.copy_blueprint("book", paused.id, PlanningRunControl(expected_version=expected))
    assert (len(writer.calls), len(reviewer.requests), len(proposals.list()), graph.nodes, graph.event_log.list()) == before


def test_autonomous_required_knowledge_gap_is_repaired_with_only_typed_list_change(setup):
    graph, proposals, _, writer, reviewer, service, _ = setup
    generate = writer.generate
    def knowledge_generation(request):
        payload = json.loads(request.messages[-1].content)
        if payload.get("revision_mode") == "targeted":
            writer.calls.append(request)
            assert payload["current_values"]["/blueprint/entities/0/initial_knowledge"] == []
            return LLMResponse(json.dumps({"changes": [{"path": "/blueprint/entities/0/initial_knowledge",
                "before": [], "after": ["secret_clock_origin"]}]}))
        response = generate(request)
        if payload["phase"] == "blueprint":
            output = json.loads(response.content)
            output["entities"][0].update(description="林舟在故事开始前已经知道时钟来历。", initial_knowledge=[])
            output["entities"].append({"id": "secret_clock_origin", "kind": "Secret", "name": "时钟来历", "description": "时钟以真实记忆为代价运转。"})
            return LLMResponse(json.dumps(output, ensure_ascii=False))
        return response
    writer.generate = knowledge_generation
    review = reviewer.generate
    first = True
    def knowledge_review(request):
        nonlocal first
        if not first:
            return review(request)
        first = False
        reviewer.requests.append(request)
        payload = json.loads(request.messages[-1].content)
        ref = payload["target"]["target_id"]
        return LLMResponse(json.dumps({"status": "needs_revision", "summary": "开篇知识基线与明确设定不一致。",
            "dimensions_checked": list(REVIEW_DIMENSIONS), "issues": [{"id": "initial_knowledge", "dimension": "knowledge_boundary",
            "finding": "required_gap", "severity": "medium", "description": "明确的开篇知情状态未进入结构化知识基线。",
            "suggestion": "将 secret_clock_origin 补入 courier 的 initial_knowledge。", "evidence": [
                {"kind": "target", "ref": ref, "quote": "林舟在故事开始前已经知道时钟来历。"},
                {"kind": "target", "ref": ref, "quote": '"initial_knowledge":[]'}]}]}, ensure_ascii=False))
    reviewer.generate = knowledge_review
    final = service.execute(create(setup).id)
    assert final.status == "awaiting_review" and final.steps[0].repairs == 1
    selected = proposals.get(final.steps[0].proposal_ref.id)
    assert json.loads(selected.body)["blueprint"]["entities"][0]["initial_knowledge"] == ["secret_clock_origin"]
    assert len(graph.nodes) == 1 and not graph.relationships


def test_expansion_generation_and_review_share_explicit_whole_volume_batch_progress(setup):
    from storygraph.services.expansion_output import expansion_volume_progress
    from storygraph.models.longform import BlueprintRequest, ExpansionRequest
    _, _, _, writer, _, service, _ = setup
    run = service.execute(create(setup).id)
    assert run.status == "awaiting_review"
    expansion_requests = [json.loads(request.messages[-1].content) for request in writer.calls
                          if json.loads(request.messages[-1].content)["phase"] == "expansion"]
    assert expansion_requests[0]["volume_progress"]["batch_role"] == "opening"
    assert expansion_requests[0]["volume_progress"]["remaining_chapter_indices"] == [2]
    assert expansion_requests[1]["volume_progress"]["batch_role"] == "finale"
    assert expansion_requests[1]["volume_progress"]["remaining_chapter_indices"] == []
    reviewed = json.loads(service._review_target(run, run.steps[1]).text)
    assert reviewed["volume_progress"] == expansion_requests[0]["volume_progress"]
    assert reviewed["author_brief"] == run.request.instruction == expansion_requests[0]["author_brief"]
    second = expansion_requests[1]["proposed_planning_context"]["recent_scene_outcomes"]
    assert second[-1]["timeline_position"] == "第1卷第1日"
    later_review = json.loads(service._review_target(run, run.steps[2]).text)
    assert later_review["proposed_planning_context"]["recent_scene_outcomes"] == second
    assert later_review["proposed_planning_context"]["prior_scene_outcome_ledger"] == expansion_requests[1]["proposed_planning_context"]["prior_scene_outcome_ledger"]
    progress = expansion_volume_progress(BlueprintRequest(instruction="完整二十章卷纲。"),
        ExpansionRequest(parent_proposal_id="frozen", parent_version=1, volume_index=1, chapter_start=1, chapter_count=5))
    assert progress["chapters_per_volume"] == 20 and progress["remaining_chapter_indices"] == list(range(6, 21))
    assert progress["reserve_main_resolution_for_final_batch"] and progress["planning_only"]


def test_creative_repair_does_not_switch_selected_ref_after_source_edited_during_call(setup):
    _, proposals, _, writer, _, service, _ = setup
    paused = service.execute(create(setup, max_calls=1).id)
    original_ref = paused.steps[0].proposal_ref
    source = proposals.get(original_ref.id)
    generate = writer.generate
    def raced(request):
        payload = json.loads(request.messages[-1].content)
        if payload.get("revision_mode") == "targeted":
            writer.calls.append(request)
            proposals.revise(source.id, actor="author", title="调用期间的新编辑", expected_version=source.version)
            return LLMResponse(json.dumps({"replacements": [{"path": "/blueprint/synopsis",
                "after": payload["current_values"]["/blueprint/synopsis"]+"补充一条明确的因果路径。"}]}, ensure_ascii=False))
        return generate(request)
    writer.generate = raced
    queued = service.resume("book", paused.id, PlanningRunResume(expected_version=paused.version, max_calls=20,
        restart_from_step=0, revision_instruction="只补足摘要的因果路径。"))
    failed = service.execute(queued.id)
    assert failed.status == "paused" and failed.pause_reason == "source_changed"
    assert failed.steps[0].proposal_ref == original_ref and proposals.get(source.id).version == source.version+1
    assert len(proposals.list()) == 1


def test_explicit_call_cap_boundary_and_large_grid_keep_default_budget():
    from pydantic import ValidationError
    from storygraph.models.planning_run import MAX_PLANNING_RUN_CALLS
    assert MAX_PLANNING_RUN_CALLS == 512
    # FastAPI uses these shared models for create/resume request schemas.
    assert PlanningRunRequest.model_json_schema()["properties"]["max_calls"] == {"default": 80, "maximum": 512, "minimum": 1, "title": "Max Calls", "type": "integer"}
    assert {"maximum": 512, "minimum": 1, "type": "integer"} in PlanningRunResume.model_json_schema()["properties"]["max_calls"]["anyOf"]
    assert PlanningRunRequest(instruction="synthetic").max_calls == 80
    assert PlanningRunResume(expected_version=1).max_calls is None
    assert PlanningRunRequest(instruction="synthetic", max_calls=512).max_calls == 512
    assert PlanningRunResume(expected_version=1, max_calls=512).max_calls == 512
    for cls, values in ((PlanningRunRequest, {"instruction": "synthetic"}),
                        (PlanningRunResume, {"expected_version": 1})):
        with pytest.raises(ValidationError):
            cls(**values, max_calls=513)
    # 144 expansion batches need 291 minimum calls, above the old 128 cap.
    large = PlanningRunRequest(instruction="synthetic", volume_count=12,
        chapters_per_volume=60, batch_size=5)
    assert large.max_calls == 80
    with pytest.raises(ValidationError, match="512-call minimum"):
        PlanningRunRequest(instruction="synthetic", volume_count=12,
            chapters_per_volume=60, batch_size=1, max_calls=512)


def test_explicit_512_resume_preserves_reservations_history_and_outputs(setup):
    run = create(setup, max_calls=2)
    service, runs = setup[5], setup[2]
    paused = service.execute(run.id)
    saved = paused.model_dump()
    provider_counts = len(setup[3].calls), len(setup[4].requests)
    with pytest.raises(GraphStoreError):
        service.resume("book", run.id, PlanningRunResume(expected_version=paused.version,
            max_calls=paused.calls_reserved-1))
    assert runs.get(run.id).model_dump() == saved
    queued = service.resume("book", run.id, PlanningRunResume(expected_version=paused.version, max_calls=512))
    assert queued.max_calls == 512 and queued.request.max_calls == 2
    assert queued.calls_reserved == paused.calls_reserved
    assert queued.steps == paused.steps and queued.restart_history == paused.restart_history
    assert (len(setup[3].calls), len(setup[4].requests)) == provider_counts
    assert queued.status == "queued"  # Explicit execution remains a separate operation.
