"""Offline contract tests: replayed judgments are not evidence of model quality."""

import json

import pytest
from pydantic import ValidationError

from storygraph.core.errors import ContractError
from storygraph.models.generation_review import REVIEW_DIMENSIONS, GenerationReviewTarget
from storygraph.services.canon_snapshot import build_canon_snapshot
from storygraph.services.llm_provider import LLMResponse
from storygraph.services.semantic_review import SemanticReviewService, review_is_current
from storygraph.stores.memory_graph import InMemoryGraphStore


@pytest.fixture
def graph():
    graph = InMemoryGraphStore()
    for node_id, label, properties in [
        ("p", "Project", {"title": "潮汐王朝", "language": "zh-CN"}),
        ("hero", "Character", {"project_id": "p", "name": "林烬", "aliases": ["阿烬"]}),
        ("secret", "Secret", {"project_id": "p", "description": "林烬是失落王朝的继承人"}),
        ("rule", "WorldRule", {"project_id": "p", "description": "死人不能复生"}),
        ("seed", "Foreshadowing", {"project_id": "p", "description": "断裂玉佩", "payoff_scene": "s9"}),
        ("s", "Scene", {"project_id": "p", "title": "钟楼", "pov_character_id": "hero", "timeline_position": "第一日"}),
    ]:
        graph.seed_canon_node(node_id=node_id, node_type=label, properties=properties)
    graph.seed_canon_relation(
        relation_id="knowledge", relation_type="KNOWS_SECRET", source_id="hero",
        target_id="secret", properties={"project_id": "p", "valid_from": "第九日", "known": False},
    )
    return graph


def target(text="林烬确信，自己就是失落王朝的继承人。", **overrides):
    return GenerationReviewTarget(**{
        "project_id": "p", "target_type": "draft", "target_id": "d", "target_version": 1,
        "text": text, "output_language": "zh-CN", "scene_id": "s", **overrides,
    })


def payload(issues=(), **overrides):
    return {"status": "needs_revision" if issues else "pass", "summary": "离线审阅结果。",
            "dimensions_checked": list(REVIEW_DIMENSIONS), "issues": list(issues), **overrides}


def issue(**overrides):
    return {
        "id": "i", "dimension": "knowledge_boundary", "severity": "high",
        "description": "林烬在获知之前已经确认身世。", "suggestion": "将确认改为疑问。",
        "evidence": [
            {"kind": "target", "ref": "d", "quote": "自己就是失落王朝的继承人"},
            {"kind": "canon", "ref": "knowledge", "quote": "第九日"},
            {"kind": "canon", "ref": "secret", "quote": "林烬是失落王朝的继承人"},
        ], **overrides,
    }


class Replay:
    def __init__(self, output):
        self.output = output
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        if isinstance(self.output, Exception):
            raise self.output
        return LLMResponse(content=self.output if isinstance(self.output, str)
                           else json.dumps(self.output, ensure_ascii=False))


def review(graph, provider, value=None, **options):
    return SemanticReviewService(provider, "exact-model").review(
        target=value or target(), canon=build_canon_snapshot(graph, project_id="p", scene_id="s"),
        **options,
    )


def test_natural_chinese_evidence_and_temporal_canon_are_sent_without_writes(graph):
    before = (len(graph.nodes), len(graph.relationships), len(graph.event_log.list()))
    provider = Replay(payload([issue()]))
    report = review(graph, provider)
    assert report.status == "needs_revision"
    sent = json.loads(provider.requests[0].messages[1].content)
    assert "林烬" in provider.requests[0].messages[1].content
    assert "第九日" in provider.requests[0].messages[1].content
    assert "死人不能复生" in provider.requests[0].messages[1].content
    assert sent["target"]["text"] == target().text
    assert provider.requests[0].model == "exact-model"
    assert before == (len(graph.nodes), len(graph.relationships), len(graph.event_log.list()))


def test_natural_chinese_negation_replay_can_pass_without_literal_secret_id(graph):
    report = review(graph, Replay(payload()), target("林烬不知道自己是谁，更不敢断言自己的身世。"))
    assert report.status == "pass"
    assert report.coverage.method == "semantic_model"
    assert report.coverage.canon_complete


@pytest.mark.parametrize("evidence", [
    [{"kind": "target", "ref": "d", "quote": "不存在的原文"},
     {"kind": "canon", "ref": "secret", "quote": "继承人"}],
    [{"kind": "target", "ref": "d", "quote": "林烬"},
     {"kind": "canon", "ref": "foreign_secret", "quote": "继承人"}],
    [{"kind": "target", "ref": "other_draft", "quote": "林烬"},
     {"kind": "canon", "ref": "secret", "quote": "继承人"}],
    [{"kind": "target", "ref": "d", "quote": "林烬"}],
    [{"kind": "target", "ref": "d", "quote": "林烬"},
     {"kind": "canon", "ref": "secret", "quote": "林烬是现代间谍"}],
])
def test_unknown_ids_hallucinated_quotes_missing_grounding_fail_closed(graph, evidence):
    report = review(graph, Replay(payload([issue(evidence=evidence)])))
    assert report.status == "inconclusive"
    assert report.issues == ()
    assert report.coverage.limitations == ("semantic_review_invalid_output",)


@pytest.mark.parametrize("invalid", ["not json", "```json\n{}\n```", "{}",
                                        payload(status="needs_revision"),
                                        payload(dimensions_checked=["invented_dimension"])])
def test_invalid_provider_output_never_passes_or_echoes_body(graph, invalid):
    report = review(graph, Replay(invalid))
    assert report.status == "inconclusive"
    assert "semantic_review_invalid_output" in report.coverage.limitations


def test_provider_error_is_sanitized_no_automatic_retry(graph):
    provider = Replay(RuntimeError("sk-sensitive https://user:password@private draft prose"))
    report = review(graph, provider)
    assert len(provider.requests) == 1
    assert report.status == "inconclusive"
    assert "semantic_review_provider_failed" in report.coverage.limitations
    serialized = report.model_dump_json()
    assert "sk-sensitive" not in serialized and "password" not in serialized


def test_bounded_snapshot_coverage_never_grants_false_pass(graph):
    canon = build_canon_snapshot(graph, project_id="p", scene_id="s", max_facts=2)
    provider = Replay(payload())
    report = SemanticReviewService(provider, "m").review(target=target(), canon=canon)
    assert not canon.complete and canon.total_facts > len(canon.facts)
    assert report.status == "inconclusive"
    assert not report.coverage.canon_complete
    assert "canon_evidence_truncated" in report.coverage.missing_context


def test_missing_dimensions_or_explicit_context_gap_cannot_pass(graph):
    assert review(graph, Replay(payload(dimensions_checked=["timeline"]))).status == "inconclusive"
    assert review(graph, Replay(payload()), missing_context=["missing_pov"]).status == "inconclusive"


def test_oversized_text_blocks_before_provider_and_does_not_truncate(graph):
    provider = Replay(payload())
    report = SemanticReviewService(provider, "m", max_target_chars=3).review(
        target=target(), canon=build_canon_snapshot(graph, project_id="p", scene_id="s"))
    assert report.status == "blocked" and not report.coverage.target_complete
    assert provider.requests == []


def test_banned_phrases_are_hard_checks_and_model_style_requires_rubric(graph):
    report = review(graph, Replay(payload()), target("林烬缓缓地走进钟楼。"), banned_phrases=["缓缓地"])
    assert report.status == "needs_revision"
    assert report.issues[0].dimension == "style_constraint"
    assert report.issues[0].evidence[0].quote == "缓缓地"
    ungrounded = issue(dimension="style_constraint", evidence=[
        {"kind": "target", "ref": "d", "quote": "林烬"},
        {"kind": "style", "ref": "rubric:0", "quote": "少用状语"},
    ])
    assert review(graph, Replay(payload([ungrounded]))).status == "inconclusive"
    report = review(graph, Replay(payload([ungrounded])), style_rubric=["少用状语"])
    assert report.status == "needs_revision"


def test_unavailable_provider_is_explicit_and_still_records_banned_phrase(graph):
    report = SemanticReviewService().review(
        target=target("林烬缓缓地走。"),
        canon=build_canon_snapshot(graph, project_id="p", scene_id="s"),
        banned_phrases=["缓缓地"],
    )
    assert report.status == "inconclusive"
    assert report.coverage.method == "deterministic_only"
    assert len(report.issues) == 1


def test_report_freshness_binds_exact_target_canon_and_style(graph):
    value = target()
    canon = build_canon_snapshot(graph, project_id="p", scene_id="s")
    report = review(graph, Replay(payload()), style_rubric=["克制"], preset_text="简练")
    args = {"target": value, "canon": canon, "style_rubric": ["克制"], "preset_text": "简练"}
    assert review_is_current(report, **args)
    for field, changed in [("text", "新正文"), ("target_version", 2),
                           ("target_id", "another"), ("target_type", "proposal"),
                           ("output_language", "en-US")]:
        assert not review_is_current(report, **{**args, "target": value.model_copy(update={field: changed})})
    assert not review_is_current(report, **{**args, "preset_text": "华丽"})
    graph.nodes["secret"].properties["description"] = "秘密已改变"
    changed = build_canon_snapshot(graph, project_id="p", scene_id="s")
    assert not review_is_current(report, **{**args, "canon": changed})


def test_fingerprint_excludes_timestamps_and_foreign_projects_but_not_temporal_properties(graph):
    before = build_canon_snapshot(graph, project_id="p")
    graph.nodes["hero"].updated_at = "changed"
    graph.seed_canon_node(node_id="q", node_type="Project", properties={"language": "en-US"})
    graph.seed_canon_node(node_id="foreign", node_type="Secret",
                          properties={"project_id": "q", "description": "PRIVATE_FOREIGN"})
    after = build_canon_snapshot(graph, project_id="p")
    assert before.fingerprint == after.fingerprint
    assert "PRIVATE_FOREIGN" not in after.model_dump_json()
    graph.relationships["knowledge"].properties["valid_from"] = "第二日"
    assert after.fingerprint != build_canon_snapshot(graph, project_id="p").fingerprint


def test_cross_project_scene_and_target_are_rejected_before_provider(graph):
    graph.seed_canon_node(node_id="q", node_type="Project", properties={"language": "en-US"})
    with pytest.raises(ContractError, match="outside"):
        build_canon_snapshot(graph, project_id="q", scene_id="s")
    provider = Replay(payload())
    with pytest.raises(ContractError, match="scope"):
        SemanticReviewService(provider, "m").review(
            target=target(project_id="q"), canon=build_canon_snapshot(graph, project_id="p", scene_id="s"))
    assert provider.requests == []


def test_snapshot_is_immutable_and_fingerprint_stable_under_prompt_budget(graph):
    full = build_canon_snapshot(graph, project_id="p", scene_id="s")
    small = build_canon_snapshot(graph, project_id="p", scene_id="s", max_chars=100)
    assert full.fingerprint == small.fingerprint
    graph.nodes["hero"].properties["name"] = "另一个名字"
    assert "另一个名字" not in full.model_dump_json()
    with pytest.raises(ValidationError):
        full.facts = ()


def test_proposal_target_version_is_preserved(graph):
    value = target(target_type="proposal", target_id="proposal_1", target_version=4)
    report = review(graph, Replay(payload()), value)
    assert (report.target_type, report.target_id, report.target_version) == ("proposal", "proposal_1", 4)


def test_late_scene_retrieves_distant_seed_without_loading_all_chapters(graph):
    for index in range(100):
        chapter = f"chapter_{index}"
        scene = f"scene_{index}"
        graph.seed_canon_node(node_id=chapter, node_type="Chapter",
                              properties={"project_id": "p", "chapter_index": index + 1})
        graph.seed_canon_node(node_id=scene, node_type="Scene",
                              properties={"project_id": "p", "chapter_id": chapter})
        graph.seed_canon_relation(relation_id=f"has_chapter_{index}",
            relation_type="HAS_CHAPTER", source_id="p", target_id=chapter,
            properties={"project_id": "p"})
        graph.seed_canon_relation(relation_id=f"has_scene_{index}",
            relation_type="HAS_SCENE", source_id=chapter, target_id=scene,
            properties={"project_id": "p"})
    graph.seed_canon_relation(relation_id="late_payoff", relation_type="PAID_OFF_IN",
        source_id="seed", target_id="scene_99", properties={"project_id": "p"})
    graph.seed_canon_relation(relation_id="early_setup", relation_type="SEEDED_IN",
        source_id="seed", target_id="scene_1", properties={"project_id": "p"})
    canon = build_canon_snapshot(graph, project_id="p", scene_id="scene_99")
    refs = {f.id for f in canon.facts}
    assert {"seed", "late_payoff", "early_setup", "scene_1", "scene_99", "rule", "secret"} <= refs
    assert "scene_50" not in refs
    assert canon.complete and canon.scope == "scene"
    assert canon.omitted_unrelated_facts > 300
    assert len(canon.facts) < 30
    report = SemanticReviewService(Replay(payload()), "m").review(
        target=target(scene_id="scene_99"), canon=canon)
    assert report.status == "pass"
    assert report.coverage.scope == "scene" and report.coverage.omitted_unrelated_facts > 300
    assert not build_canon_snapshot(graph, project_id="p").complete


def test_natural_name_alias_in_target_retrieves_unlisted_character(graph):
    graph.seed_canon_node(node_id="witness", node_type="Character",
        properties={"project_id": "p", "name": "谢闻", "aliases": ["老谢"]})
    canon = build_canon_snapshot(graph, project_id="p", scene_id="s", target_text="老谢递来玉佩。")
    assert "witness" in {f.id for f in canon.facts}


def test_empty_story_canon_cannot_pass(graph):
    graph.seed_canon_node(node_id="empty", node_type="Project", properties={"language": "zh-CN"})
    canon = build_canon_snapshot(graph, project_id="empty")
    value = target(project_id="empty", scene_id=None)
    report = SemanticReviewService(Replay(payload()), "m").review(target=value, canon=canon)
    assert report.status == "inconclusive"
    assert "insufficient_story_canon" in report.coverage.missing_context


def test_changed_evidence_scope_invalidates_report_even_with_same_full_canon(graph):
    canon = build_canon_snapshot(graph, project_id="p", scene_id="s")
    report = review(graph, Replay(payload()))
    reduced = build_canon_snapshot(graph, project_id="p", scene_id="s", max_facts=2)
    assert canon.fingerprint == reduced.fingerprint
    assert not review_is_current(report, target=target(), canon=reduced)


@pytest.mark.parametrize("properties", [
    {"required_characters": ["missing_character"]},
    {"pov_character_id": "rule"}, {"location_id": "foreign_location"},
])
def test_missing_or_wrong_type_scene_refs_cannot_receive_false_pass(graph, properties):
    graph.nodes["s"].properties.update(properties)
    canon = build_canon_snapshot(graph, project_id="p", scene_id="s")
    assert not canon.complete
    assert review(graph, Replay(payload())).status == "inconclusive"


@pytest.fixture
def empty_plan_graph():
    graph = InMemoryGraphStore()
    graph.seed_canon_node(node_id="p", node_type="Project",
                          properties={"language": "zh-CN", "title": "潮汐计划"})
    return graph


def plan_target(**overrides):
    text = json.dumps({
        "world_rules": [{"rule": "潮能不能存储。"}],
        "volumes": [{"summary": "主角将潮能封进石罐，十年后取用。"}],
        "character_arcs": [{"turn": "第三卷才把王印交给林烬。"}],
        "causal_links": [{"effect": "第二卷林烬凭已经收到的王印开门。"}],
    }, ensure_ascii=False)
    return target(text, target_type="proposal", target_id="blueprint", scene_id=None,
                  purpose="plan", **overrides)


def test_empty_project_plan_review_can_pass_internal_consistency(empty_plan_graph):
    graph = empty_plan_graph
    value = plan_target().model_copy(update={"text": json.dumps({
        "world_rules": [{"rule": "潮能不能存储。"}],
        "volumes": [{"summary": "主角当场用尽潮能，不能留待下次使用。"}],
    }, ensure_ascii=False)})
    canon = build_canon_snapshot(graph, project_id="p", purpose="plan", target_text=value.text)
    assert canon.complete and canon.scope == "plan"
    assert "insufficient_story_canon" not in canon.missing_context
    provider = Replay(payload())
    report = SemanticReviewService(provider, "exact-model").review(target=value, canon=canon)
    assert report.status == "pass" and report.purpose == "plan"
    assert report.coverage.scope == "plan"
    assert "PURPOSE=PLAN" in provider.requests[0].messages[0].content
    assert "energy creation/storage/transfer" in provider.requests[0].messages[0].content
    assert "mystery's resolution" in provider.requests[0].messages[0].content
    assert review_is_current(report, target=value, canon=canon)
    assert not review_is_current(report, target=value.model_copy(update={"purpose": "scene"}), canon=canon)


@pytest.mark.parametrize("dimension,quotes", [
    ("world_rule", ("潮能不能存储。", "主角将潮能封进石罐，十年后取用。")),
    ("timeline", ("第三卷才把王印交给林烬。", "第二卷林烬凭已经收到的王印开门。")),
])
def test_plan_internal_contradictions_use_distinct_exact_target_quotes(empty_plan_graph, dimension, quotes):
    value = plan_target()
    grounded = issue(dimension=dimension, description="规划的两处设定互相矛盾。",
                     evidence=[{"kind": "target", "ref": "blueprint", "quote": quote} for quote in quotes])
    report = SemanticReviewService(Replay(payload([grounded])), "m").review(
        target=value, canon=build_canon_snapshot(empty_plan_graph, project_id="p", purpose="plan"))
    assert report.status == "needs_revision"
    assert report.issues[0].evidence[0].ref == report.issues[0].evidence[1].ref == "blueprint"
    assert report.coverage.canon_complete


@pytest.mark.parametrize("quotes", [
    ["潮能不能存储。"], ["潮能不能存储。", "潮能不能存储。"],
    ["潮能不能存储。", "模型捏造的第二条规则"],
])
def test_plan_internal_single_duplicate_or_invented_quote_is_rejected(empty_plan_graph, quotes):
    value = plan_target()
    ungrounded = issue(evidence=[{"kind": "target", "ref": "blueprint", "quote": q} for q in quotes])
    report = SemanticReviewService(Replay(payload([ungrounded])), "m").review(
        target=value, canon=build_canon_snapshot(empty_plan_graph, project_id="p", purpose="plan"))
    assert report.status == "inconclusive"
    assert report.issues == ()
    assert "semantic_review_invalid_output" in report.coverage.limitations


def test_two_target_quotes_do_not_weaken_scene_canon_evidence_requirement(graph):
    value = target("林烬已经知道身世。林烬并不知道身世。")
    internal = issue(evidence=[{"kind": "target", "ref": "d", "quote": q}
                              for q in ("林烬已经知道身世。", "林烬并不知道身世。")])
    assert review(graph, Replay(payload([internal])), value).status == "inconclusive"


def test_plan_scope_omits_unrelated_grid_but_budget_truncation_is_inconclusive(graph):
    for i in range(200):
        graph.seed_canon_node(node_id=f"grid_chapter_{i}", node_type="Chapter",
            properties={"project_id": "p", "chapter_index": i + 1, "summary": f"第{i + 1}章的结果"})
        graph.seed_canon_node(node_id=f"grid_scene_{i}", node_type="Scene",
            properties={"project_id": "p", "chapter_id": f"grid_chapter_{i}",
                        "outcome": f"第{i + 1}场的结果"})
        graph.seed_canon_relation(relation_id=f"grid_contains_{i}", relation_type="HAS_SCENE",
            source_id=f"grid_chapter_{i}", target_id=f"grid_scene_{i}", properties={"project_id": "p"})
    value = plan_target()
    canon = build_canon_snapshot(graph, project_id="p", purpose="plan", target_text=value.text)
    refs = {f.id for f in canon.facts}
    assert canon.complete and canon.scope == "plan" and canon.omitted_unrelated_facts > 500
    assert {"hero", "secret", "rule", "seed"} <= refs
    assert "grid_scene_199" in refs and "grid_scene_0" not in refs
    assert len(canon.facts) < 30
    truncated = build_canon_snapshot(graph, project_id="p", purpose="plan", max_facts=2)
    assert not truncated.complete and truncated.fingerprint == canon.fingerprint
    report = SemanticReviewService(Replay(payload()), "m").review(target=value, canon=truncated)
    assert report.status == "inconclusive"
    assert "canon_evidence_truncated" in report.coverage.missing_context


def test_plan_purpose_requires_explicit_matching_snapshot_before_provider(empty_plan_graph):
    provider = Replay(payload())
    with pytest.raises(ContractError, match="Plan review"):
        SemanticReviewService(provider, "m").review(target=plan_target(),
            canon=build_canon_snapshot(empty_plan_graph, project_id="p"))
    with pytest.raises(ContractError, match="Plan review"):
        SemanticReviewService(provider, "m").review(
            target=plan_target().model_copy(update={"target_type": "draft"}),
            canon=build_canon_snapshot(empty_plan_graph, project_id="p", purpose="plan"))
    assert provider.requests == []


def test_plan_banned_phrase_definitions_are_not_prose_violations(empty_plan_graph):
    value = plan_target().model_copy(update={"text": json.dumps({
        "style_brief": {"banned_patterns": ["缓缓地", "不由自主地"],
                        "rubric": ["避免使用缓缓地等套话。"],
                        "negative_example": "不要写：他不由自主地缓缓地推门。"},
        "synopsis": "主角发现潮汐账簿中有人动过手脚。",
    }, ensure_ascii=False)})
    canon = build_canon_snapshot(empty_plan_graph, project_id="p", purpose="plan")
    provider = Replay(payload())
    report = SemanticReviewService(provider, "m").review(
        target=value, canon=canon, banned_phrases=["缓缓地", "不由自主地"],
        style_rubric=["避免使用套话。"],
    )
    assert report.status == "pass" and report.issues == ()
    assert "negative examples" in provider.requests[0].messages[0].content
    offline = SemanticReviewService().review(target=value, canon=canon, banned_phrases=["缓缓地"])
    assert offline.status == "inconclusive" and offline.issues == ()
    assert offline.dimensions_checked == ()
