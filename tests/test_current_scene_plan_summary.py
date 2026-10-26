"""Current approved summary is protected planning context, never legacy approval or realized state."""

import json
import pytest
from storygraph.core.errors import ContractError
from storygraph.models.context import ApprovedScenePlan
from storygraph.services.context_pack_builder import ContextPackBuilder
from storygraph.services.scene_writer import LLMSceneWriter
from test_knowledge_entry import graph as graph
from test_scene_plan_context import add_plan, Capture, graph_state
from test_longform_planning import setup as _applied_setup
from test_applied_scene_snapshot import applied

applied_setup = _applied_setup

SUMMARY = "13:12两人同行进入；13:21:40同伴完成检查后离场，视角人物独自核对；13:33打开内盖发现异常。"


def test_existing_plan_current_summary_reaches_writer_without_future_or_chapter_summary(graph):
    add_plan(graph)
    graph.nodes["s3"].properties["summary"] = SUMMARY
    graph.nodes["chapter"].properties["summary"] = "WHOLE_CHAPTER_FUTURE_SENTINEL"
    graph.seed_canon_node(
        node_id="future_scene",
        node_type="Scene",
        properties={"project_id": "p", "summary": "FUTURE_SCENE_PRIVATE_SENTINEL"},
    )
    before = graph_state(graph)
    pack = ContextPackBuilder(graph).build(project_id="p", scene_id="s3", target_tokens=12000)
    assert pack.scene_plan.planned_summary == SUMMARY
    assert pack.must_include == []
    provider = Capture()
    LLMSceneWriter(provider=provider, model="offline-fixture").draft(pack)
    sent = json.loads(provider.requests[0].messages[-1].content)
    assert sent["context_pack"]["scene_plan"]["planned_summary"] == SUMMARY
    assert "13:21:40" in provider.requests[0].messages[-1].content
    assert "WHOLE_CHAPTER_FUTURE_SENTINEL" not in provider.requests[0].messages[-1].content
    assert "FUTURE_SCENE_PRIVATE_SENTINEL" not in provider.requests[0].messages[-1].content
    prompt = provider.requests[0].messages[0].content
    for rule in (
        "CURRENT scene's approved intended sequence",
        "arrivals/departures",
        "not already true",
        "unplanned major evidence acquisition",
        "Another character knowing a secret does not authorize",
    ):
        assert rule in prompt
    assert graph_state(graph) == before


@pytest.mark.parametrize("summary", ["只有旧摘要，不能升级为批准规划。", 1, "中" * 4001])
def test_legacy_summary_alone_never_creates_plan_or_new_plan_gap(graph, summary):
    graph.nodes["s3"].properties["summary"] = summary
    pack = ContextPackBuilder(graph).build(project_id="p", scene_id="s3", target_tokens=12000)
    assert pack.scene_plan is None
    assert not any("scene_plan" in g.kind for g in pack.missing_context)


def test_optional_none_and_old_plan_compatibility(graph):
    add_plan(graph)
    pack = ContextPackBuilder(graph).build(project_id="p", scene_id="s3", target_tokens=12000)
    assert pack.scene_plan.planned_summary is None
    old = pack.scene_plan.model_dump(exclude={"planned_summary"})
    assert ApprovedScenePlan.model_validate(old).planned_summary is None


@pytest.mark.parametrize("summary", [1, ["not a summary"], "中" * 4001])
def test_invalid_current_approved_summary_blocks_before_provider(graph, summary):
    add_plan(graph)
    graph.nodes["s3"].properties["summary"] = summary
    pack = ContextPackBuilder(graph).build(project_id="p", scene_id="s3", target_tokens=12000)
    assert any(
        g.kind == "invalid_scene_plan_field" and g.severity == "critical"
        for g in pack.missing_context
    )
    provider = Capture()
    with pytest.raises(ContractError):
        LLMSceneWriter(provider=provider, model="offline-fixture").draft(pack)
    assert not provider.requests


def test_complete_current_summary_stays_p0_under_budget_pressure(graph):
    add_plan(graph)
    graph.nodes["s3"].properties["summary"] = "完整当前规划。" * 500
    before = graph_state(graph)
    normal = ContextPackBuilder(graph).build(project_id="p", scene_id="s3", target_tokens=12000)
    small = ContextPackBuilder(graph).build(project_id="p", scene_id="s3", target_tokens=20)
    assert small.scene_plan == normal.scene_plan
    assert small.scene_plan.planned_summary == graph.nodes["s3"].properties["summary"]
    assert any(
        g.kind == "context_budget_exceeded" and g.severity == "critical"
        for g in small.missing_context
    )
    provider = Capture()
    with pytest.raises(ContractError):
        LLMSceneWriter(provider=provider, model="offline-fixture").draft(small)
    assert not provider.requests and graph_state(graph) == before


def test_real_apply_current_summary_is_projected_without_changing_stored_plan(applied_setup):
    graph = applied_setup[0]
    scene_id = applied(applied_setup)[0]
    before = graph_state(graph)
    pack = ContextPackBuilder(graph).build(
        project_id="project_test", scene_id=scene_id, target_tokens=12000
    )
    assert pack.scene_plan.planned_summary == graph.nodes[scene_id].properties["summary"]
    provider = Capture()
    LLMSceneWriter(provider=provider, model="offline-fixture").draft(pack)
    sent = json.loads(provider.requests[0].messages[-1].content)
    assert (
        sent["context_pack"]["scene_plan"]["planned_summary"]
        == graph.nodes[scene_id].properties["summary"]
    )
    assert graph_state(graph) == before
