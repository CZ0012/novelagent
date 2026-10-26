"""Lossless plan transport removes duplication without weakening local evidence."""

import json
from types import SimpleNamespace

import pytest

from storygraph.models.generation_review import CanonSnapshot, GenerationReviewTarget, REVIEW_DIMENSIONS
from storygraph.services.canon_snapshot import canonical_json, content_hash
from storygraph.services.generation_budget import completion_budget
from storygraph.services.llm_provider import LLMResponse
from storygraph.services.semantic_review import SemanticReviewService, review_wire_target


def target(text=None, purpose="plan"):
    content = {"blueprint": {"rules": ["能量只可转移，不能无中生有。"],
        "volumes": [{"index": 1, "summary": "主角记录输入输出及损耗。", "optional": None}],
        "nested": {"bool": True, "budget": 2500, "empty": [], "keys/with~markers": {"text": '必须写成"原文"。\n保留换行。'}}}}
    return GenerationReviewTarget(project_id="p", target_type="proposal", target_id="plan", target_version=3,
        text=text if text is not None else json.dumps(content, ensure_ascii=False, indent=2),
        output_language="zh-CN", purpose=purpose)


def canon():
    return CanonSnapshot(project_id="p", scope="plan", complete=True, fingerprint="original-canon", total_facts=0)


class Capture:
    def __init__(self, output=None, mode="provider_default", effort=None):
        self.requests = []
        self.output = output
        self.thinking_mode, self.reasoning_effort = mode, effort

    def generate(self, request):
        self.requests.append(request)
        value = self.output(json.loads(request.messages[-1].content)) if self.output else {
            "status": "pass", "summary": "离线协议检查没有阻断发现，不代表真实模型质量。",
            "dimensions_checked": list(REVIEW_DIMENSIONS), "issues": []}
        return LLMResponse(json.dumps(value, ensure_ascii=False))


def test_complete_structured_plan_appears_once_with_hash_and_all_exact_registry_quotes():
    value = target()
    original = value.text
    provider = Capture()
    result = SemanticReviewService(provider, "offline").review(target=value, canon=canon())
    sent = json.loads(provider.requests[0].messages[-1].content)
    assert "text" not in sent["target"]
    assert sent["target"]["target_text_sha256"] == content_hash(original)
    assert sent["target"]["target_version"] == 3 and sent["plan_content"] == json.loads(original)
    assert value.text == original and result.target_text_sha256 == content_hash(original)
    assert all(entry["quote"] in original for entry in sent["evidence_sources"].values() if entry["kind"] == "target")
    previous = {**sent, "target": value.model_dump()}
    assert len(canonical_json(sent)) < len(canonical_json(previous)) - len(original) * .7
    assert result.status == "pass" and set(result.dimensions_checked) == set(REVIEW_DIMENSIONS)


def test_source_id_still_resolves_encoded_quote_against_original_not_decoded_tree():
    value = target()
    def output(sent):
        registry = sent["evidence_sources"]
        first = next(key for key, entry in registry.items() if entry["path"].endswith("/text#0"))
        second = next(key for key, entry in registry.items() if entry["path"] == "$/blueprint/rules/0#0")
        return {"evidence_registry_id": sent["evidence_registry_id"], "status": "needs_revision", "summary": "两处原文需要作者核对。", "dimensions_checked": list(REVIEW_DIMENSIONS),
            "issues": [{"id": "i", "finding": "required_gap", "dimension": "causality", "severity": "medium",
                "description": "原文表述需要明确联系。", "suggestion": "保留原文证据并由作者补足因果解释。",
                "evidence": [{"source_id": first}, {"source_id": second}]}]}
    report = SemanticReviewService(Capture(output), "offline").review(target=value, canon=canon())
    assert report.status == "needs_revision"
    quote = report.issues[0].evidence[0].quote
    assert '\\"原文\\"' in quote and quote in value.text
    def fabricated(sent):
        result = output(sent)
        result["issues"][0]["evidence"][0] = {"kind": "target", "ref": "plan", "quote": '必须写成"原文"。\n保留换行。'}
        return result
    rejected = SemanticReviewService(Capture(fabricated), "offline").review(target=value, canon=canon())
    assert rejected.status == "inconclusive" and not rejected.issues


@pytest.mark.parametrize("text", ["旧提案尚未结构化。", '{"duplicate":"甲","duplicate":"乙"}',
    '{"n":NaN}', '{"n":1e400}', json.dumps({"text": "非标准转义内容。"}, ensure_ascii=True)])
def test_unparseable_ambiguous_or_alternate_escaped_legacy_plan_keeps_raw_text(text):
    value = target(text)
    metadata, parsed = review_wire_target(value)
    assert metadata["text"] == text and parsed is None
    provider = Capture()
    SemanticReviewService(provider, "offline").review(target=value, canon=canon())
    sent = json.loads(provider.requests[0].messages[-1].content)
    assert sent["target"]["text"] == text and sent["plan_content"] is None


def test_even_parseable_scene_prose_keeps_the_original_raw_wire_shape():
    value = target(purpose="scene")
    metadata, parsed = review_wire_target(value)
    assert metadata == value.model_dump() and parsed is None


@pytest.mark.parametrize("mode,effort,maximum", [("provider_default", None, 8000), ("disabled", None, 8000),
    ("enabled", None, 65536), ("enabled", "low", 65536), ("provider_default", "low", 65536), ("enabled", "max", 65536)])
def test_semantic_thinking_ceiling_is_visible_before_provider_but_default_unchanged(mode, effort, maximum):
    provider = Capture(mode=mode, effort=effort)
    SemanticReviewService(provider, "offline").review(target=target(), canon=canon())
    assert provider.requests[0].max_tokens == maximum


@pytest.mark.parametrize("allowance", [True, 0, -1, 65537, 32768.5])
def test_optional_internal_allowance_is_validated_even_for_provider_defaults(allowance):
    with pytest.raises(ValueError):
        completion_budget(SimpleNamespace(thinking_mode="provider_default", reasoning_effort=None), 8000,
                          thinking_allowance=allowance)
