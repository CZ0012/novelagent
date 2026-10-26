"""Critic classification and exact citation aliases never repair invented text."""

import json

import pytest

from test_semantic_review import graph as base_graph, issue, payload, Replay, review, target
from storygraph.core.errors import ContractError
from storygraph.models.generation_review import CanonSnapshot, GenerationReviewTarget
from storygraph.services.canon_snapshot import build_canon_snapshot, canonical_json, content_hash
from storygraph.services.llm_provider import LLMResponse
from storygraph.services.semantic_review import (
    MAX_EVIDENCE_REGISTRY_CHARS, MAX_EVIDENCE_SOURCES, SemanticReviewService,
    _system_prompt, blocking_issues, build_evidence_sources,
)

graph = base_graph


def test_advice_only_can_pass_complete_scope_but_keeps_visible_advisory_count(graph):
    advisory = issue(finding="advice", severity="medium", description="可以进一步写明交接步骤。", suggestion="扩章时补充正式封存节点。")
    result = review(graph, Replay(payload([advisory])))
    assert result.status == "pass" and result.coverage.canon_complete
    assert len(result.issues) == 1 and result.issues[0].finding == "advice"
    assert not blocking_issues(result.issues) and "1" in result.summary and "非阻断建议" in result.summary


@pytest.mark.parametrize("finding", ["contradiction", "required_gap"])
def test_low_severity_true_conflict_or_required_gap_still_blocks(graph, finding):
    result = review(graph, Replay(payload([issue(finding=finding, severity="low")], status="pass")))
    assert result.status == "needs_revision" and blocking_issues(result.issues)


@pytest.mark.parametrize("severity", ["high", "critical"])
def test_severe_advice_is_invalid_not_a_way_to_pass_or_force_rewrite(graph, severity):
    result = review(graph, Replay(payload([issue(finding="advice", severity=severity)])))
    assert result.status == "inconclusive" and not result.issues
    assert "semantic_review_invalid_output" in result.coverage.limitations


@pytest.mark.parametrize("status", ["blocked", "inconclusive"])
def test_advice_does_not_override_explicit_blocked_or_inconclusive(graph, status):
    result = review(graph, Replay(payload([issue(finding="advice", severity="low")], status=status)))
    assert result.status == status


def test_advice_never_overrides_missing_context_or_deterministic_banned_phrase(graph):
    advisory = issue(finding="advice", severity="low")
    assert review(graph, Replay(payload([advisory])), missing_context=["unknown_state"]).status == "inconclusive"
    value = target("林烬缓缓地说，自己就是失落王朝的继承人。")
    result = review(graph, Replay(payload([advisory])), value, banned_phrases=["缓缓地"])
    assert result.status == "needs_revision" and result.issues[0].finding == "contradiction"


class SourceIdReviewer:
    def __init__(self, mutate=None):
        self.mutate = mutate
        self.sent = None
    def generate(self, request):
        self.sent = json.loads(request.messages[-1].content)
        registry = self.sent["evidence_sources"]
        target_id = next(key for key, source in registry.items() if source["kind"] == "target")
        canon_id = next(key for key, source in registry.items() if source["kind"] == "canon" and source["ref"] == "secret" and "继承人" in source["quote"])
        output = payload([issue(evidence=[{"source_id": target_id}, {"source_id": canon_id}])], evidence_registry_id=self.sent["evidence_registry_id"])
        if self.mutate:
            self.mutate(output, target_id)
        return LLMResponse(json.dumps(output, ensure_ascii=False))


def test_source_ids_resolve_to_exact_original_canonical_evidence(graph):
    provider = SourceIdReviewer()
    result = review(graph, provider)
    assert result.status == "needs_revision"
    assert {e.kind for e in result.issues[0].evidence} == {"target", "canon"}
    assert all(set(e.model_dump()) == {"kind", "ref", "quote"} for e in result.issues[0].evidence)
    assert result.issues[0].evidence[0].quote in target().text
    assert provider.sent["target"]["text"] == target().text


@pytest.mark.parametrize("bad", [
    {"source_id": "unknown"}, {"source_id": 1},
    {"source_id": "known", "quote": "override"},
    {"source_id": "known", "kind": "canon", "ref": "foreign"},
])
def test_unknown_or_mixed_override_evidence_alias_fails_closed(graph, bad):
    def mutate(output, known):
        output["issues"][0]["evidence"][0] = {key: known if value == "known" else value for key, value in bad.items()}
    result = review(graph, SourceIdReviewer(mutate))
    assert result.status == "inconclusive" and not result.issues


def test_structured_json_quotes_are_encoded_substrings_not_decoded_fabrications():
    text = json.dumps({"first": '先说“存疑”，再说"确认"。\n保留原文。', "second": "第三卷才量化亏空。"}, ensure_ascii=False)
    value = GenerationReviewTarget(project_id="p", target_type="proposal", target_id="plan", target_version=1,
        output_language="zh-CN", purpose="plan", text=text)
    canon = CanonSnapshot(project_id="p", scope="plan", facts=(), fingerprint="snapshot", complete=True, total_facts=0)
    class Reviewer:
        def generate(self, request):
            registry = json.loads(request.messages[-1].content)["evidence_sources"]
            ids = {source["path"]: key for key, source in registry.items()}
            assert all(source["quote"] in text for source in registry.values() if source["kind"] == "target")
            return LLMResponse(_request_payload(request, payload([issue(dimension="timeline", severity="low", finding="advice",
                description="可以展开证据递进。", suggestion="保持存疑、确认和量化的不同阶段。", evidence=[
                    {"source_id": ids["$/first#0"]}, {"source_id": ids["$/second#0"]}])]), ensure_ascii=False))
    result = SemanticReviewService(Reviewer(), "m").review(target=value, canon=canon)
    assert result.status == "pass" and result.issues[0].evidence[0].quote in text
    assert '\\"确认\\"' in result.issues[0].evidence[0].quote


def test_registry_is_stable_bounded_and_never_truncates_original_review_target(graph):
    value = target(text=json.dumps({f"field_{i}": "合成的原样证据文本。" for i in range(4000)}, ensure_ascii=False))
    canon = build_canon_snapshot(graph, project_id="p", scene_id="s")
    registry, coverage = build_evidence_sources(target=value, canon=canon, style_sources={"rubric:0": "具体表达。"})
    assert len(registry) <= MAX_EVIDENCE_SOURCES and len(canonical_json(registry)) <= MAX_EVIDENCE_REGISTRY_CHARS
    assert not coverage["complete"] and coverage["omitted_segments"] > 0
    assert all(len(source["quote"]) <= 500 and source["quote"] in value.text for source in registry.values() if source["kind"] == "target")
    assert registry == build_evidence_sources(target=value, canon=canon, style_sources={"rubric:0": "具体表达。"})[0]


def test_prompt_distinguishes_actual_live_false_positives_and_legal_state_values():
    prompt = _system_prompt("zh-CN", "plan")
    for phrase in ("Early doubt, later proof", "working copy", "oral command", "PLANNING DOSSIER",
                   "life_status=dead and physical_state=injured can coexist", "healthy/injured/healing",
                   "Do not suggest deceased", "story-entry baseline", "source_id", "required_gap"):
        assert phrase in prompt


def test_legacy_issue_without_finding_remains_blocking(graph):
    result = review(graph, Replay(payload([issue(severity="low")])))
    assert result.status == "needs_revision" and result.issues[0].finding == "contradiction"


def labelled_plan_target():
    content = {"blueprint": {"volumes": [
        {"index": 2, "ending_hook": "第二卷才出现语音记录。"},
        {"index": 5, "ending_hook": "第五卷完成正式对账。"}],
        "character_arcs": [{"character_id": "hero", "turning_points": [
            {"volume_index": 4, "change": "第四卷取得封存报告。"}]}]},
        "expansion": {"volume_index": 3, "chapters": [{"index": 7, "scenes": [{"summary": "第七章现场核验。"}]}]}}
    value = GenerationReviewTarget(project_id="p", target_type="proposal", target_id="labelled", target_version=2,
        text=json.dumps(content, ensure_ascii=False), output_language="zh-CN", purpose="plan")
    canon = CanonSnapshot(project_id="p", scope="plan", facts=(), fingerprint="full-original-canon", complete=True, total_facts=0)
    return content, value, canon


def test_evidence_context_uses_declared_volume_and_chapter_not_zero_based_positions():
    _, value, canon = labelled_plan_target()
    registry, _ = build_evidence_sources(target=value, canon=canon, style_sources={})
    entries = {entry["path"]: entry for entry in registry.values()}
    assert entries["$/blueprint/volumes/0/ending_hook#0"]["context"] == {"volume_index": 2}
    assert entries["$/blueprint/volumes/1/ending_hook#0"]["context"] == {"volume_index": 5}
    assert entries["$/blueprint/character_arcs/0/turning_points/0/change#0"]["context"] == {"character_id": "hero", "volume_index": 4}
    assert entries["$/expansion/chapters/0/scenes/0/summary#0"]["context"] == {"volume_index": 3, "chapter_index": 7}
    assert all(entry["quote"] in value.text for entry in entries.values())


@pytest.mark.parametrize("override", [False, True])
def test_readable_plan_content_preserves_raw_text_hash_and_context_is_not_model_overridable(override):
    content, value, canon = labelled_plan_target()
    original_text = value.text
    class Reviewer:
        def generate(self, request):
            sent = json.loads(request.messages[-1].content)
            assert sent["plan_content"] == content and "text" not in sent["target"]
            assert sent["target"]["target_text_sha256"] == content_hash(original_text)
            assert sent["target"]["target_version"] == 2
            registry = sent["evidence_sources"]
            ids = {entry["path"]: key for key, entry in registry.items()}
            first = {"source_id": ids["$/blueprint/volumes/0/ending_hook#0"]}
            if override:
                first["context"] = {"volume_index": 1}
            return LLMResponse(_request_payload(request, payload([issue(finding="advice", severity="low", dimension="timeline",
                description="可在扩章中明确日历日期。", suggestion="保留第二卷与第五卷的信息递进。", evidence=[first,
                    {"source_id": ids["$/blueprint/volumes/1/ending_hook#0"]}])]), ensure_ascii=False))
    result = SemanticReviewService(Reviewer(), "same-model").review(target=value, canon=canon)
    assert value.text == original_text and result.target_text_sha256 == content_hash(original_text)
    if override:
        assert result.status == "inconclusive" and not result.issues
    else:
        assert result.status == "pass"
        assert all(set(e.model_dump()) == {"kind", "ref", "quote"} for e in result.issues[0].evidence)


def test_prompt_prohibits_reassigning_second_volume_citation_to_first_volume():
    prompt = _system_prompt("zh-CN", "plan")
    assert "NEVER zero-based JSON path array positions" in prompt
    assert "volume_index=2 cannot prove that a statement occurred in Volume 1" in prompt
    assert "plan_content as the decoded structured view of the exact target.text" in prompt


def test_causal_source_context_binds_cause_to_source_and_effect_to_destination_volume():
    content = {"blueprint": {"causal_links": [{"id": "name_does_not_define_timing", "from_volume": 2,
        "to_volume": 3, "cause": "第二卷取得查阅依据。", "effect": "第三卷经正式申请后取得文件，并在高潮公开。"}]}}
    value = GenerationReviewTarget(project_id="p", target_type="proposal", target_id="causal", target_version=1,
        text=json.dumps(content, ensure_ascii=False), output_language="zh-CN", purpose="plan")
    canon = CanonSnapshot(project_id="p", scope="plan", facts=(), fingerprint="unchanged", complete=True, total_facts=0)
    registry, _ = build_evidence_sources(target=value, canon=canon, style_sources={})
    entries = {entry["path"]: entry for entry in registry.values()}
    assert entries["$/blueprint/causal_links/0/cause#0"]["context"] == {"from_volume": 2, "to_volume": 3, "volume_index": 2}
    assert entries["$/blueprint/causal_links/0/effect#0"]["context"] == {"from_volume": 2, "to_volume": 3, "volume_index": 3}
    assert entries["$/blueprint/causal_links/0/id#0"]["context"] == {"from_volume": 2, "to_volume": 3}
    assert all(entry["quote"] in value.text for entry in registry.values())
    prompt = _system_prompt("zh-CN", "plan")
    assert "effect summarizes consequences WITHIN to_volume" in prompt
    assert "not necessarily the immediate next event" in prompt
    assert "a later-volume handover already happened in from_volume" in prompt


def machine_language_target():
    text = json.dumps({"entities": [
        {"id": "char_han_qichang", "kind": "Character", "initial_knowledge": ["secret_killer"],
         "description": "韩启昌在开篇已经掌握重复抵押账目。"},
        {"id": "secret_duplicate_pledge", "kind": "Secret", "description": "同一电量被重复抵押。"}]}, ensure_ascii=False)
    value = GenerationReviewTarget(project_id="p", target_type="proposal", target_id="language_plan", target_version=1,
        text=text, output_language="zh-CN", purpose="plan")
    canon = CanonSnapshot(project_id="p", scope="plan", facts=(), fingerprint="same", complete=True, total_facts=0)
    return value, canon


def test_chinese_review_with_exact_known_machine_ids_passes_language_guard_without_rewriting_text():
    value, canon = machine_language_target()
    suggestion = "将 secret_duplicate_pledge 补入 char_han_qichang 的 initial_knowledge，或在台账旁注明他通过调度长身份掌握该账目。"
    class Reviewer:
        def generate(self, request):
            registry = json.loads(request.messages[-1].content)["evidence_sources"]
            ids = {source["path"]: key for key, source in registry.items()}
            return LLMResponse(_request_payload(request, payload([issue(dimension="knowledge_boundary", finding="required_gap", severity="medium",
                description="开篇已知事实与结构化知识基线不一致。", suggestion=suggestion,
                evidence=[{"source_id": ids["$/entities/0/description#0"]},
                          {"source_id": ids["$/entities/0/initial_knowledge/0#0"]}])]), ensure_ascii=False))
    result = SemanticReviewService(Reviewer(), "m").review(target=value, canon=canon)
    assert result.status == "needs_revision" and result.issues[0].finding == "required_gap"
    assert result.issues[0].suggestion == suggestion
    assert result.target_text_sha256 == content_hash(value.text) and not result.coverage.limitations


@pytest.mark.parametrize("suggestion", ["Add a rule.", "Please add an invented secret to the new character and rewrite the initial state.",
    "secret_duplicate_pledge char_han_qichang initial_knowledge",
    "请将 invented_secret_outside_current_dossier_value 加入 invented_character_outside_current_dossier_value。"])
def test_review_identifier_filter_does_not_waive_english_or_unknown_identifier_prose(suggestion):
    value, canon = machine_language_target()
    class Reviewer:
        def generate(self, request):
            registry = json.loads(request.messages[-1].content)["evidence_sources"]
            ids = {source["path"]: key for key, source in registry.items()}
            return LLMResponse(_request_payload(request, payload([issue(dimension="knowledge_boundary", finding="required_gap", severity="low",
                description="结构化知识基线尚有缺口。", suggestion=suggestion,
                evidence=[{"source_id": ids["$/entities/0/description#0"]},
                          {"source_id": ids["$/entities/0/initial_knowledge/0#0"]}])]), ensure_ascii=False))
    result = SemanticReviewService(Reviewer(), "m").review(target=value, canon=canon)
    assert result.status == "inconclusive" and not result.issues


def test_known_identifier_removal_uses_boundaries_and_does_not_learn_english_words_from_style():
    from storygraph.services.semantic_review import review_language_fields
    value, canon = machine_language_target()
    fields = {"description": "请核对 char_han_qichang_extra 与 char_han_qichang。"}
    filtered = review_language_fields(fields, target=value, canon=canon, style_sources={"rubric:0": "Add a rule."}, registry={})
    assert "char_han_qichang_extra" in filtered["description"]
    assert " char_han_qichang。" not in filtered["description"]
    assert fields["description"] == "请核对 char_han_qichang_extra 与 char_han_qichang。"
    with pytest.raises(ContractError):
        review_language_fields({"suggestion": "Add a rule."}, target=value, canon=canon, style_sources={"rubric:0": "Add a rule."}, registry={})
    prompt = _system_prompt("zh-CN", "plan")
    assert "typed initial_knowledge list omits that Secret, flag a blocking required_gap" in prompt


def test_language_style_finding_has_explicit_policy_source_without_invented_citation(graph):
    value = target("林烬读到 allegedly 这处英文残留。")
    class Reviewer:
        def generate(self, request):
            sent = json.loads(request.messages[-1].content)
            assert sent["style_sources"]["output_language_policy"]
            registry = sent["evidence_sources"]
            target_id = next(key for key, entry in registry.items() if entry["kind"] == "target")
            policy_id = next(key for key, entry in registry.items() if entry["kind"] == "style" and entry["ref"] == "output_language_policy")
            return LLMResponse(_request_payload(request, payload([issue(dimension="style_constraint", finding="advice", severity="low",
                description="句中存在不必要的英语正文残留。", suggestion="将该处改为中文表述。", evidence=[
                    {"source_id": target_id}, {"source_id": policy_id}])]), ensure_ascii=False))
    result = review(graph, Reviewer(), value)
    assert result.status == "pass" and result.issues[0].finding == "advice"
    assert result.issues[0].evidence[1].ref == "output_language_policy"
    assert "cite the exact target span AND the supplied output_language_policy" in _system_prompt("zh-CN", "plan")


@pytest.mark.parametrize("purpose", ["scene", "plan"])
@pytest.mark.parametrize("severity", ["low", "medium"])
def test_ordinary_advice_accepts_one_exact_target_quote_without_claiming_conflict(graph, purpose, severity):
    advisory = issue(finding="advice", dimension="world_rule", severity=severity,
        description="可以补充计算的起点。", suggestion="扩章时说明时间计算从何时开始。",
        evidence=[{"kind": "target", "ref": "d", "quote": "自己就是失落王朝的继承人"}])
    report = review_advice_scope(graph, payload([advisory]), purpose)
    assert report.status == "pass" and len(report.issues) == 1
    assert report.issues[0].finding == "advice" and not blocking_issues(report.issues)
    assert "非阻断建议" in report.summary


@pytest.mark.parametrize("purpose", ["scene", "plan"])
def test_single_quote_advice_does_not_discard_valid_blocking_contradiction(graph, purpose):
    advisory = issue(id="advice", finding="advice", dimension="world_rule", severity="low",
        evidence=[{"kind": "target", "ref": "d", "quote": "自己就是失落王朝的继承人"}])
    report = review_advice_scope(graph, payload([issue(), advisory]), purpose)
    assert report.status == "needs_revision" and len(report.issues) == 2
    assert len(blocking_issues(report.issues)) == 1


@pytest.mark.parametrize("purpose", ["scene", "plan"])
@pytest.mark.parametrize("finding", ["contradiction", "required_gap"])
def test_blocking_claims_still_require_canon_or_internal_pair(graph, purpose, finding):
    claim = issue(finding=finding, severity="low",
        evidence=[{"kind": "target", "ref": "d", "quote": "自己就是失落王朝的继承人"}])
    report = review_advice_scope(graph, payload([claim]), purpose)
    assert report.status == "inconclusive" and not report.issues
    assert "semantic_review_invalid_output" in report.coverage.limitations


@pytest.mark.parametrize("evidence", [
    [{"source_id": "ev_0000000000000000"}],
    [{"kind": "target", "ref": "foreign", "quote": "自己就是失落王朝的继承人"}],
    [{"kind": "target", "ref": "d", "quote": "不存在的目标文字。"}],
])
def test_advice_still_rejects_unknown_alias_scope_and_invented_quote(graph, evidence):
    report = review(graph, Replay(payload([issue(finding="advice", severity="low", evidence=evidence)])))
    assert report.status == "inconclusive" and not report.issues


def test_style_advice_still_requires_applicable_style_source(graph):
    advisory = issue(finding="advice", dimension="style_constraint", severity="low",
        evidence=[{"kind": "target", "ref": "d", "quote": "自己就是失落王朝的继承人"}])
    report = review(graph, Replay(payload([advisory])))
    assert report.status == "inconclusive" and not report.issues


def review_advice_scope(graph, output, purpose):
    if purpose == "scene":
        return review(graph, Replay(output))
    value = target(purpose="plan", target_type="proposal", scene_id=None)
    return SemanticReviewService(Replay(output), "fixture-model").review(target=value,
        canon=build_canon_snapshot(graph, project_id="p", purpose="plan"))


def _request_payload(request, output, **kwargs):
    output["evidence_registry_id"] = json.loads(request.messages[-1].content)["evidence_registry_id"]
    return json.dumps(output, **kwargs)
