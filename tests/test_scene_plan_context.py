"""Approved plan beats reach writing prompts without becoming realized facts."""

import json

import pytest

from storygraph.core.errors import ContractError
from storygraph.services.context_pack_builder import ContextPackBuilder
from storygraph.services.llm_provider import LLMResponse
from storygraph.services.scene_writer import LLMSceneWriter
from storygraph.stores.draft_store import SQLiteDraftStore
from test_knowledge_entry import graph as graph


class Capture:
    def __init__(self):
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return LLMResponse(json.dumps({"text": "林烬将铜印推给守门人，换来进入档案室的许可。",
            "summary": "他取得进入档案室的许可。", "self_check": ["保持审阅边界。"]}, ensure_ascii=False))


def add_plan(graph):
    graph.nodes["s1"].properties.update(summary="早章中主角放弃渡船以保全证人。", outcome="证人留下一条账簿线索。",
                                         longform_scene_id="local_early_plan_id")
    graph.nodes["s3"].properties.update(outcome="主角用铜印换得档案室的钥匙。", emotional_turn="急切转为审慎。",
        target_length=2500, causal_dependencies=["local_early_plan_id"], foreshadowing_payoff_ids=["local_clue_id"])
    graph.seed_canon_node(node_id="clue_stable", node_type="Foreshadowing", properties={
        "project_id": "p", "clue_text": "铜印边缘有一道断齿。", "hidden_meaning": "隐藏含义：铜印对应档案室的锁。"})
    graph.seed_canon_relation(relation_id="direct_early_dependency", relation_type="CAUSES", source_id="s1", target_id="s3",
                              properties={"project_id": "p", "planning_only": True})
    for ref, kind, scene in (("planned_seed", "SEEDED_IN", "s1"), ("planned_payoff", "PAID_OFF_IN", "s3")):
        graph.seed_canon_relation(relation_id=ref, relation_type=kind, source_id="clue_stable", target_id=scene,
                                  properties={"project_id": "p", "planning_only": True})


def graph_state(graph):
    return json.dumps({"nodes": {k: v.model_dump() for k, v in graph.nodes.items()},
        "relations": {k: v.model_dump() for k, v in graph.relationships.items()},
        "events": [e.model_dump() for e in graph.event_log.list()]}, sort_keys=True)


def test_late_scene_prompt_receives_exact_early_precondition_outcome_budget_and_payoff(graph):
    add_plan(graph)
    drafts = SQLiteDraftStore()
    upstream = drafts.create_draft(project_id="p", scene_id="s1", content_language="zh-CN",
        text="UNRELATED_FULL_PROSE_MUST_NOT_BE_SENT", summary="DRAFT_SUMMARY_IS_NOT_APPROVED_OUTCOME")
    before = graph_state(graph)
    pack = ContextPackBuilder(graph, drafts).build(project_id="p", scene_id="s3", target_tokens=12000)
    plan = pack.scene_plan
    assert plan.semantics == "approved_plan_not_realized_facts"
    assert plan.target_length == 2500 and plan.planned_outcome == "主角用铜印换得档案室的钥匙。"
    assert plan.emotional_turn == "急切转为审慎。"
    assert plan.causal_preconditions[0].scene_id == "s1"
    assert plan.causal_preconditions[0].relation_id == "direct_early_dependency"
    assert plan.causal_preconditions[0].planned_outcome == "证人留下一条账簿线索。"
    assert "local_early_plan_id" not in plan.model_dump_json()
    action = plan.foreshadowing_actions[0]
    assert action.id == "clue_stable" and action.action == "payoff" and action.seed_scene_ids == ["s1"]
    assert action.planned_payoff == "隐藏含义：铜印对应档案室的锁。"
    assert pack.must_include == [] and upstream.id not in pack.provenance.draft_refs
    provider = Capture()
    LLMSceneWriter(provider=provider, model="offline").draft(pack)
    sent = provider.requests[0].messages[-1].content
    assert json.loads(sent)["context_pack"]["scene_plan"]["target_length"] == 2500
    assert "证人留下一条账簿线索。" in sent
    assert "UNRELATED_FULL_PROSE_MUST_NOT_BE_SENT" not in sent and "DRAFT_SUMMARY_IS_NOT_APPROVED_OUTCOME" not in sent
    assert "APPROVED PLAN" in provider.requests[0].messages[0].content
    assert graph_state(graph) == before


def test_seed_action_never_sends_hidden_payoff_text(graph):
    add_plan(graph)
    graph.nodes["s1"].properties["foreshadowing_seed_ids"] = ["local_clue_id"]
    pack = ContextPackBuilder(graph).build(project_id="p", scene_id="s1", target_tokens=12000)
    action = pack.scene_plan.foreshadowing_actions[0]
    assert action.action == "seed" and action.do_not_reveal_payoff
    assert action.planned_payoff is None and action.seed_scene_ids == []
    assert "铜印边缘有一道断齿。" in pack.model_dump_json()
    assert "隐藏含义：铜印对应档案室的锁。" not in pack.model_dump_json()


@pytest.mark.parametrize("failure", ["foreign", "missing", "missing_declared", "missing_seed", "empty_precondition"])
def test_missing_or_foreign_plan_context_blocks_generation_before_provider_without_leak(graph, failure):
    add_plan(graph)
    if failure == "foreign":
        graph.nodes["s1"].properties.update(project_id="foreign", summary="FOREIGN_PRIVATE_PLAN_SENTINEL")
    elif failure == "missing":
        del graph.nodes["s1"]
    elif failure == "missing_declared":
        del graph.relationships["direct_early_dependency"]
    elif failure == "missing_seed":
        del graph.relationships["planned_seed"]
    else:
        del graph.nodes["s1"].properties["summary"]
        del graph.nodes["s1"].properties["outcome"]
    pack = ContextPackBuilder(graph).build(project_id="p", scene_id="s3", target_tokens=12000)
    assert any(gap.severity == "critical" and "scene_plan" in gap.kind for gap in pack.missing_context)
    assert "FOREIGN_PRIVATE_PLAN_SENTINEL" not in pack.model_dump_json()
    provider = Capture()
    with pytest.raises(ContractError):
        LLMSceneWriter(provider=provider, model="offline").draft(pack)
    assert provider.requests == []


def test_old_scene_without_plan_data_does_not_get_invented_plan(graph):
    pack = ContextPackBuilder(graph).build(project_id="p", scene_id="s3", target_tokens=12000)
    assert pack.scene_plan is None
    legacy = pack.model_dump(exclude={"scene_plan"})
    assert type(pack).model_validate(legacy).scene_plan is None
    assert not any("scene_plan" in gap.kind for gap in pack.missing_context)


def test_direct_dependency_cap_reports_critical_instead_of_sending_entire_book(graph):
    for i in range(31):
        ref = f"d{i:02}"
        graph.seed_canon_node(node_id=ref, node_type="Scene", properties={"project_id": "p", "summary": "合成前置规划"})
        graph.seed_canon_relation(relation_id=f"cause_{i:02}", relation_type="CAUSES", source_id=ref,
            target_id="s3", properties={"project_id": "p", "planning_only": True})
    pack = ContextPackBuilder(graph).build(project_id="p", scene_id="s3", target_tokens=12000)
    assert len(pack.scene_plan.causal_preconditions) == 30
    assert any(gap.kind == "scene_plan_dependency_limit" and gap.severity == "critical" for gap in pack.missing_context)


def test_plan_semantic_beats_are_protected_under_budget_pressure(graph):
    add_plan(graph)
    large = ContextPackBuilder(graph).build(project_id="p", scene_id="s3", target_tokens=12000)
    small = ContextPackBuilder(graph).build(project_id="p", scene_id="s3", target_tokens=20)
    assert small.scene_plan == large.scene_plan
    assert any(gap.kind == "context_budget_exceeded" and gap.severity == "critical" for gap in small.missing_context)
    assert small.must_include == []
