"""Prompt attention improves; it is not a deterministic correction or quality proof."""

import hashlib
import json
from pathlib import Path

import pytest

from storygraph.models.generation_review import GenerationReviewTarget
from storygraph.services.canon_snapshot import canonical_json, content_hash
from storygraph.services.semantic_review import _system_prompt, review_wire_target


def test_scene_reminder_covers_concrete_assertions_without_invented_identity_certainty():
    prompt = _system_prompt("zh-CN", "scene")
    assert "counts, times, durations and quantities" in prompt
    assert "exact written forms from display labels/aliases" in prompt
    assert "quoted, uncertain or hypothetical claims" in prompt
    assert "Do not invent facts to reconcile" in prompt
    assert "preserve uncertainty" in prompt
    assert "姓名栏" not in prompt


def test_plan_prompt_has_only_the_explicitly_approved_plan_proof_revision():
    prompt = _system_prompt("zh-CN", "plan")
    assert content_hash(prompt) == "bb77430c7e2cdb30029737d576d9fff3d2019a8c6ef2d06222d2666bfea12ec4"
    assert "counts, times, durations and quantities" not in prompt
    assert "counts, times, durations and quantities" not in _system_prompt("zh-CN", "unknown")


def test_planning_wire_is_unchanged_by_scene_only_attention_reminder():
    value = GenerationReviewTarget(project_id="p", target_type="proposal", target_id="plan", target_version=1,
        text=canonical_json({"world_rules": [{"id": "rule", "rule": "fixed synthetic planning rule"}],
            "volumes": [{"index": 1, "summary": "same synthetic plan"}]}), output_language="zh-CN", purpose="plan")
    metadata, content = review_wire_target(value)
    assert content_hash(canonical_json({"target": metadata, "plan_content": content})) == "3de6e07d81822d86a05430df47f2fbdee27e00101023bfc1308e27be9d535518"


def test_retained_real_probe_miss_remains_an_unchanged_acceptance_limitation():
    path = Path(__file__).resolve().parents[1] / ".storygraph/sg031-acceptance/style-probe-localized/prose-review-original.json"
    if not path.exists():
        pytest.skip("Private ignored acceptance evidence is not distributed with source tests")
    before = path.read_bytes()
    data = json.loads(before)
    assert data["report"]["status"] == "pass" and data["report"]["issues"] == []
    _system_prompt("zh-CN", "scene")
    assert hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256(before).digest()
