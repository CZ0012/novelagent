"""Timeline/source-state transport is exact, bounded and never a generated summary."""

from types import SimpleNamespace

import pytest

from storygraph.core.errors import GraphStoreError
from storygraph.models.generation_review import CanonSnapshot, GenerationReviewTarget
from storygraph.services.canon_snapshot import canonical_json
from storygraph.services.expansion_output import (
    MAX_PRIOR_OUTCOME_CHARS, MAX_PRIOR_OUTCOME_SCENES,
    prior_planned_scene_outcome_ledger, recent_planned_scene_outcomes,
)
from storygraph.services.planning_run import PLANNING_REVIEW_MAX_CHARS
from storygraph.services.semantic_review import SemanticReviewService
from test_planning_run import Reviewer, create, setup as base_setup

setup = base_setup


def scenes(count):
    return {f"v01_c{i:03d}_s01": SimpleNamespace(properties={
        "timeline_position": f"事件第{i}日22:30；报告次日09:20上传。", "summary": "本场景只推进核验。",
        "outcome": "原始记录已封存，编号S-1。" if i == 1 else "获得后续工作副本。",
        "pov_character_id": "actor", "location_id": "room"}) for i in range(1, count+1)}


def test_all_prior_outcomes_keep_early_sealed_source_after_recent_window_and_preserve_flashback():
    source = scenes(30)
    source["v01_c020_s01"].properties["timeline_position"] = "明确回溯：事件第3日；报告在第20日补交。"
    recent = recent_planned_scene_outcomes(source)
    ledger = prior_planned_scene_outcome_ledger(source)
    assert len(recent) == 12 and recent[0]["id"] == "v01_c019_s01"
    assert ledger["scenes"][0]["outcome"] == "原始记录已封存，编号S-1。"
    assert ledger["scenes"][19]["timeline_position"] == source["v01_c020_s01"].properties["timeline_position"]
    assert ledger["entity_reference_scope"] == "blueprint_local_ids"
    assert ledger["semantics"] == "proposed_scene_outcomes_not_realized_facts"


def test_prior_ledger_limits_and_unknown_identity_fail_without_truncation():
    with pytest.raises(GraphStoreError, match="bounded scope"):
        prior_planned_scene_outcome_ledger(scenes(MAX_PRIOR_OUTCOME_SCENES+1))
    value = scenes(1)
    value["v01_c001_s01"].properties["outcome"] = "长"*MAX_PRIOR_OUTCOME_CHARS
    with pytest.raises(GraphStoreError, match="bounded size"):
        prior_planned_scene_outcome_ledger(value)
    with pytest.raises(GraphStoreError, match="outside the pinned blueprint"):
        prior_planned_scene_outcome_ledger(scenes(1), identity_maps={"pov_character_id": {}, "location_id": {}})


def test_planning_run_has_explicit_200k_limit_but_scene_default_remains_100k(setup, monkeypatch):
    run = create(setup)
    service = setup[5]
    overhead = len(canonical_json({"proof": ""}))
    value = {"proof": "中"*(PLANNING_REVIEW_MAX_CHARS-overhead)}
    monkeypatch.setattr("storygraph.services.planning_run.book_projection", lambda *args, **kwargs: value)
    target = service._review_target(run)
    assert len(target.text) == PLANNING_REVIEW_MAX_CHARS == 200000
    canon = CanonSnapshot(project_id="book", scope="plan", facts=(), fingerprint="same", complete=True, total_facts=0)
    provider = Reviewer()
    report = SemanticReviewService(provider, "fake", max_target_chars=PLANNING_REVIEW_MAX_CHARS).review(target=target, canon=canon)
    assert report.status == "pass" and len(provider.requests) == 1
    value["proof"] += "中"
    with pytest.raises(GraphStoreError) as rejected:
        service._review_target(run)
    assert rejected.value.category == "planning_context_budget"
    scene = GenerationReviewTarget(project_id="book", target_type="draft", target_id="draft", target_version=1,
        scene_id="scene", text="中"*100001, output_language="zh-CN")
    untouched = Reviewer()
    blocked = SemanticReviewService(untouched, "fake").review(target=scene,
        canon=canon.model_copy(update={"scope": "scene", "scene_id": "scene"}))
    assert blocked.status == "blocked" and not untouched.requests
