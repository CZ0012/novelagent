"""Proof reminders preserve evidence gates; offline checks do not prove model recall."""

import json

import pytest

from storygraph.models.generation_review import CanonSnapshot, GenerationReviewTarget, REVIEW_DIMENSIONS
from storygraph.services.canon_snapshot import canonical_json, content_hash
from storygraph.services.llm_provider import LLMResponse
from storygraph.services.semantic_review import SemanticReviewService, _system_prompt, blocking_issues


def test_only_plan_prompt_adds_general_resolution_entailment_and_source_identity_checks():
    plan = _system_prompt("zh-CN", "plan")
    for text in ("CENTRAL CLAIMED RESOLUTION", "inferential bridge", "chain of custody",
        "authenticity/integrity", "correlation alone does not establish event truth",
        "Author-dossier truth is not evidence acquired", "flag required_gap, not optional outline brevity",
        "unstated real-world legal requirements", "immutable originals", "derived copies are not independent corroboration",
        "a sealed original cannot silently be overwritten", "report, upload and export timestamps",
        "flashbacks/nonlinear narration", "do not guess chronology"):
        assert text in plan
    assert content_hash(_system_prompt("zh-CN", "scene")) == "b5cfb523fd8a8f04ece43965a683d7dab3d5566cd0a09ac71bba213a0576b0e2"
    assert "CENTRAL CLAIMED RESOLUTION" not in _system_prompt("zh-CN", "unknown")
    assert "13:44" not in plan and "压力曲线" not in plan


def test_existing_plan_prompt_bytes_outside_approved_proof_paragraph_are_unchanged():
    plan = _system_prompt("zh-CN", "plan")
    before, added = plan.split("For every CENTRAL CLAIMED RESOLUTION", 1)
    _, after = added.split("For each CausalLink", 1)
    assert content_hash(before + "For each CausalLink" + after) == "ca95a609bbff49d75e53216dee22531562af42132b7e90119b30409e2e0ad548"


@pytest.mark.parametrize("finding,severity,expected", [("required_gap", "medium", "needs_revision"),
                                                        ("advice", "low", "pass")])
def test_grounded_essential_gap_remains_blocking_and_minor_advice_remains_nonblocking(finding, severity, expected):
    content = ({"claim": "记录校验后即可证明事件的完整因果与发生时刻。",
                "evidence": "现有材料只列出内容一致、签收过程与两组记录的相关。"}
               if finding == "required_gap" else {
                   "claim": "中心结论已由独立见证和时刻校准支持，工作副本仅作形式核验。",
                   "evidence": "文件夹颜色尚未指定，不影响已列证据和本次结论。"})
    value = GenerationReviewTarget(project_id="p", target_type="proposal", target_id="proof", target_version=1,
        text=canonical_json(content), output_language="zh-CN", purpose="plan")
    canon = CanonSnapshot(project_id="p", scope="plan", facts=(), fingerprint="scope", complete=True, total_facts=0)
    class Reviewer:
        def generate(self, request):
            sent = json.loads(request.messages[-1].content)
            aliases = {entry["path"]: key for key, entry in sent["evidence_sources"].items()}
            return LLMResponse(json.dumps({"evidence_registry_id": sent["evidence_registry_id"], "status": "needs_revision" if finding == "required_gap" else "pass",
                "summary": "检查结论与证据之间的联系。", "dimensions_checked": list(REVIEW_DIMENSIONS),
                "issues": [{"id": "i", "dimension": "causality", "finding": finding, "severity": severity,
                    "description": "需要区分证据完整性与结论的充分依据。", "suggestion": "明确必要的因果桥梁，或收窄当前声称的结论。",
                    "evidence": [{"source_id": aliases["$/claim#0"]}, {"source_id": aliases["$/evidence#0"]}]}]}, ensure_ascii=False))
    report = SemanticReviewService(Reviewer(), "offline").review(target=value, canon=canon)
    assert report.status == expected
    assert bool(blocking_issues(report.issues)) == (finding == "required_gap")
    assert all(evidence.quote in value.text for evidence in report.issues[0].evidence)
