"""Explicit author scopes are persisted request boundaries, not model advice."""
import json

import pytest
from pydantic import ValidationError

from test_planning_run import setup as planning_setup, create
from test_planning_run_retention import finished
from storygraph.core.errors import GraphStoreError
from storygraph.models.generation_review import REVIEW_DIMENSIONS
from storygraph.models.longform import Blueprint, TargetedRevisionOutput
from storygraph.models.planning_run import PlanningRun, PlanningRunControl, PlanningRunResume, PlanningStep
from storygraph.services.llm_provider import LLMResponse
from storygraph.services.longform_planning import LongformPlanError, _apply_targeted_changes
from storygraph.services.planning_run import PlanningRunService, branch_from_ref
from storygraph.stores.planning_run_store import SQLitePlanningRunStore
from storygraph.stores.proposal_store import SQLiteProposalStore


SYNOPSIS = "/blueprint/synopsis"
OUTSIDE = "/blueprint/volumes/0/summary"


@pytest.fixture
def setup(tmp_path):
    return planning_setup.__wrapped__(tmp_path)


def scoped_restart(setup, old, **kwargs):
    return setup[5].resume("book", old.id, PlanningRunResume(expected_version=old.version,
        restart_from_step=0, revision_instruction="只修梗概，其他字段原样保留。",
        preserve_later_outputs=True, revision_paths=[SYNOPSIS], **kwargs))


@pytest.mark.parametrize("extra", [
    {"revision_paths": []}, {"revision_paths": [SYNOPSIS, SYNOPSIS]},
    {"revision_paths": [""]}, {"revision_paths": ["x" * 501]},
    {"revision_paths": [f"/blueprint/field/{index}" for index in range(41)]},
    {"revision_paths": [SYNOPSIS], "revision_instruction": None},
    {"revision_paths": [SYNOPSIS], "restart_from_step": None},
    {"revision_paths": [SYNOPSIS], "revision_mode": "full"},
    {"revision_paths": [SYNOPSIS], "recheck_current_step": True},
])
def test_scope_requires_bounded_unique_paths_and_explicit_targeted_restart(extra):
    values = dict(expected_version=1, restart_from_step=0, revision_instruction="只修梗概。")
    values.update(extra)
    with pytest.raises(ValidationError):
        PlanningRunResume(**values)


@pytest.mark.parametrize("path", ["/blueprint/unknown", "/blueprint/entities/0/id",
    "/blueprint/entities/0/initial_state", "/expansion/chapters/0/summary"])
def test_unknown_forbidden_or_foreign_phase_scope_rejects_before_any_reservation(setup, path):
    old = finished(setup)
    before = setup[2].get(old.id).model_dump(), len(setup[1].list()), len(setup[3].calls)
    with pytest.raises(GraphStoreError) as error:
        setup[5].resume("book", old.id, PlanningRunResume(expected_version=old.version,
            restart_from_step=0, revision_instruction="只修改指定字段。", revision_paths=[path]))
    assert error.value.category == "planning_revision_paths_invalid"
    assert (setup[2].get(old.id).model_dump(), len(setup[1].list()), len(setup[3].calls)) == before


@pytest.mark.parametrize("response_format", ["replacements", "changes"])
def test_provider_cannot_publish_outside_author_scope_in_either_format(setup, response_format):
    graph, proposals, _, writer, reviewer, service, _ = setup
    old = finished(setup)
    before = len(proposals.list()), dict(graph.nodes), list(graph.event_log.list())
    previous_ref = old.steps[0].proposal_ref
    original_generate = writer.generate

    def outside(request):
        payload = json.loads(request.messages[-1].content)
        if payload.get("revision_mode") != "targeted":
            return original_generate(request)
        writer.calls.append(request)
        assert payload["allowed_paths"] == [SYNOPSIS]
        assert list(payload["current_values"]) == [SYNOPSIS]
        change = {"path": OUTSIDE, "after": "模型擅自改变了未授权的卷摘要。"}
        if response_format == "changes":
            change["before"] = payload["source_plan"]["volumes"][0]["summary"]
        return LLMResponse(json.dumps({response_format: [change]}, ensure_ascii=False))

    writer.generate = outside
    queued = scoped_restart(setup, old)
    result = service.execute(queued.id)
    assert result.status == "paused" and result.pause_reason == "schema_invalid"
    assert result.calls_reserved == old.calls_reserved + 1 and result.pending_call is None
    assert result.steps[0].proposal_ref == previous_ref
    assert result.steps[0].revision_paths == [SYNOPSIS]
    assert (len(proposals.list()), graph.nodes, graph.event_log.list()) == before
    assert len(reviewer.requests) == 6  # Rejected edits never reach the critic.


def test_apply_helper_independently_rejects_unscoped_path_and_preserves_legacy_none(setup):
    old = finished(setup)
    authored = branch_from_ref(setup[1], old.steps[0].proposal_ref).blueprint
    edits = TargetedRevisionOutput(changes=[dict(path=OUTSIDE,
        before=authored.volumes[0].summary, after="信使必须为新证据承担具体代价。")])
    with pytest.raises(LongformPlanError):
        _apply_targeted_changes(authored, "blueprint", edits, allowed_paths=[SYNOPSIS])
    changed = _apply_targeted_changes(authored, "blueprint", edits)
    assert changed.volumes[0].summary == edits.changes[0].after
    assert authored.volumes[0].summary != changed.volumes[0].summary


@pytest.mark.parametrize("automatic_escape", [False, True])
def test_scope_persists_through_reopen_plain_resume_and_automatic_repair(setup, automatic_escape):
    graph, proposals, runs, writer, reviewer, service, path = setup
    old = finished(setup)
    before_graph = dict(graph.nodes), list(graph.event_log.list())
    queued = scoped_restart(setup, old, max_calls=old.calls_reserved + 1)
    original_generate = writer.generate
    repair_payloads = []

    def within_scope(request):
        payload = json.loads(request.messages[-1].content)
        if payload.get("revision_mode") != "targeted":
            return original_generate(request)
        writer.calls.append(request)
        repair_payloads.append(payload)
        assert payload["allowed_paths"] == [SYNOPSIS]
        assert set(payload["current_values"]) == {SYNOPSIS}
        if automatic_escape and len(repair_payloads) == 2:
            return LLMResponse(json.dumps({"changes": [{"path": OUTSIDE,
                "before": payload["source_plan"]["volumes"][0]["summary"],
                "after": "审查建议不能扩大作者限定的修订范围。"}]}, ensure_ascii=False))
        text = "信使保留原始证据，拒绝让另一座钟塔替自己偿还记忆。" + "他选择承担。" * len(repair_payloads)
        return LLMResponse(json.dumps({"replacements": [{"path": SYNOPSIS, "after": text}]}, ensure_ascii=False))

    writer.generate = within_scope
    first = service.execute(queued.id)
    assert first.pause_reason == "call_budget" and first.steps[0].status == "generated"
    assert first.steps[0].revision_paths == [SYNOPSIS]
    # A real reopened SQLite store/service, without recovery, verifies persistence.
    reopened_proposals = SQLiteProposalStore(path / "proposals.sqlite")
    reopened_runs = SQLitePlanningRunStore(reopened_proposals)
    reopened = PlanningRunService(graph=graph, proposals=reopened_proposals, runs=reopened_runs,
        provider_factory=service.provider_factory)
    saved = reopened.get("book", first.id)
    assert PlanningRun.model_validate_json(saved.model_dump_json()).steps[0].revision_paths == [SYNOPSIS]
    assert saved.restart_history[-1]["revision_paths"] == [SYNOPSIS]
    original_review = reviewer.generate
    needs_revision_once = True

    def critic_requests_outside_scope(request):
        nonlocal needs_revision_once
        if not needs_revision_once:
            return original_review(request)
        needs_revision_once = False
        reviewer.requests.append(request)
        payload = json.loads(request.messages[-1].content)
        pairs = []
        for key, evidence in payload["evidence_sources"].items():
            if evidence["kind"] == "target" and evidence["quote"] not in [quote for _, quote in pairs]:
                pairs.append((key, evidence["quote"]))
            if len(pairs) == 2:
                break
        return LLMResponse(json.dumps({"evidence_registry_id": payload["evidence_registry_id"],
            "status": "needs_revision", "summary": "需要核对卷摘要中的因果。",
            "dimensions_checked": list(REVIEW_DIMENSIONS), "issues": [{"id": "outside_scope",
                "dimension": "causality", "finding": "required_gap", "severity": "medium",
                "description": "卷摘要缺少独立的因果前提。", "suggestion": "修改未授权的卷摘要。",
                "evidence": [{"source_id": key} for key, _ in pairs]}]}, ensure_ascii=False))

    reviewer.generate = critic_requests_outside_scope
    resumed = reopened.resume("book", saved.id, PlanningRunResume(expected_version=saved.version,
        max_calls=old.calls_reserved + 4))
    assert resumed.steps[0].revision_paths == [SYNOPSIS]
    final = reopened.execute(resumed.id)
    assert len(repair_payloads) == 2  # Includes one automatic repair after the critic.
    assert final.steps[0].revision_paths == [SYNOPSIS]
    if automatic_escape:
        assert final.pause_reason == "schema_invalid" and final.pending_call is None
        assert final.steps[0].proposal_ref == saved.steps[0].proposal_ref
        assert final.calls_reserved == old.calls_reserved + 3
    else:
        assert final.steps[0].status == "passed"
    current = branch_from_ref(reopened_proposals, final.steps[0].proposal_ref).blueprint
    original = branch_from_ref(proposals, old.steps[0].proposal_ref).blueprint
    assert current.model_dump(exclude={"synopsis"}) == original.model_dump(exclude={"synopsis"})
    assert (graph.nodes, graph.event_log.list()) == before_graph


def test_scope_cannot_be_attached_to_generation_without_an_existing_source(setup):
    run = create(setup)
    paused = setup[5].stop("book", run.id, PlanningRunControl(expected_version=run.version))
    with pytest.raises(GraphStoreError) as error:
        setup[5].resume("book", run.id, PlanningRunResume(expected_version=paused.version,
            restart_from_step=0, revision_instruction="只修梗概。", revision_paths=[SYNOPSIS]))
    assert error.value.category == "planning_revision_source_missing"
    assert setup[2].get(run.id).version == paused.version
    assert not setup[3].calls and setup[2].get(run.id).calls_reserved == 0


def test_new_explicit_restart_resets_scope_while_plain_resume_cannot_clear_it(setup):
    old = finished(setup)
    queued = scoped_restart(setup, old)
    paused = setup[5].stop("book", queued.id, PlanningRunControl(expected_version=queued.version))
    plain = setup[5].resume("book", paused.id, PlanningRunResume(expected_version=paused.version, revision_paths=None))
    assert plain.steps[0].revision_paths == [SYNOPSIS]
    paused = setup[5].stop("book", plain.id, PlanningRunControl(expected_version=plain.version))
    unscoped = setup[5].resume("book", paused.id, PlanningRunResume(expected_version=paused.version,
        restart_from_step=0, revision_instruction="明确重新选择范围。"))
    assert unscoped.steps[0].revision_paths is None
    assert unscoped.restart_history[-1]["revision_paths"] is None
    assert unscoped.restart_history[-2]["revision_paths"] == [SYNOPSIS]


def test_legacy_serialized_step_defaults_to_none_and_full_cannot_store_scope():
    assert PlanningStep.model_validate({"index": 0, "phase": "blueprint"}).revision_paths is None
    with pytest.raises(ValidationError):
        PlanningStep(index=0, phase="blueprint", revision_mode="full", revision_paths=[SYNOPSIS])


def test_existing_initial_knowledge_exception_can_be_scoped_without_new_typed_fields(setup):
    old = finished(setup)
    payload = branch_from_ref(setup[1], old.steps[0].proposal_ref).blueprint.model_dump()
    payload["entities"].append(dict(id="secret_clock", kind="Secret", name="时钟来源", description="时钟借走人的记忆。"))
    authored = Blueprint.model_validate(payload)
    path = "/blueprint/entities/0/initial_knowledge"
    edit = TargetedRevisionOutput(changes=[dict(path=path, before=None, after=["secret_clock"])])
    revised = _apply_targeted_changes(authored, "blueprint", edit, allowed_paths=[path])
    assert revised.entities[0].initial_knowledge == ["secret_clock"]
    assert authored.entities[0].initial_knowledge is None
    with pytest.raises(LongformPlanError):
        _apply_targeted_changes(authored, "blueprint", edit, allowed_paths=[SYNOPSIS])
