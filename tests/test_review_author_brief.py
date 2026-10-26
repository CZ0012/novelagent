"""Trusted author briefs remain explicit style authority, never generated target text."""
import json
import pytest
from storygraph.core.errors import ContractError
from storygraph.models.generation_review import CanonFact, CanonSnapshot, GenerationReviewReport
from storygraph.services.canon_snapshot import canonical_json, content_hash
from storygraph.services.semantic_review import SemanticReviewService, build_evidence_sources, review_is_current, style_fingerprint
from storygraph.services.llm_provider import LLMResponse
from test_semantic_review import target, payload, issue, Replay
from test_planning_run import setup as setup
from test_planning_run import create


def plan_inputs(text="场景摘要超过软性字数建议。"):
    value = target(text, target_type="proposal", purpose="plan", scene_id=None)
    canon = CanonSnapshot(project_id="p", scope="plan", complete=True, fingerprint="f", total_facts=0)
    return value, canon


def test_brief_style_evidence_is_explicit_exact_and_does_not_promote_target_copy():
    brief = "摘要宜在一百字以内。"
    value, canon = plan_inputs(canonical_json({"author_brief": brief, "summary": "偏长的摘要。"}))
    class Critic:
        def generate(self, request):
            sent = json.loads(request.messages[-1].content)
            assert sent["style_sources"]["author_brief"] == brief
            aliases = sent["evidence_sources"]
            target_id = next(k for k, v in aliases.items() if v["kind"] == "target" and v["path"].startswith("$/summary"))
            style_id = next(k for k, v in aliases.items() if v["kind"] == "style" and v["ref"] == "author_brief")
            return LLMResponse(json.dumps(payload([issue(dimension="style_constraint", severity="low", finding="advice",
                evidence=[{"source_id": target_id}, {"source_id": style_id}])],
                evidence_registry_id=sent["evidence_registry_id"]), ensure_ascii=False))
    report = SemanticReviewService(Critic(), "fixture").review(target=value, canon=canon, author_brief=brief)
    assert report.status == "pass" and report.issues[0].evidence[1].kind == "style"
    assert review_is_current(report, target=value, canon=canon, author_brief=brief)
    assert not review_is_current(report, target=value, canon=canon, author_brief=brief+"已修订。")
    assert not review_is_current(report, target=value, canon=canon)
    copy = Replay(payload([issue(dimension="style_constraint", severity="low", finding="advice", evidence=[
        {"kind": "target", "ref": value.target_id, "quote": brief}])]))
    invalid = SemanticReviewService(copy, "fixture").review(target=value, canon=canon)
    assert invalid.status == "inconclusive"
    assert "author_brief" not in json.loads(copy.requests[0].messages[-1].content)["style_sources"]


def test_default_fingerprint_and_old_report_compatibility_are_unchanged():
    expected = content_hash(canonical_json({"style_rubric": [], "banned_phrases": [], "preset_text": ""}))
    assert style_fingerprint() == style_fingerprint(author_brief=None) == expected
    value, canon = plan_inputs()
    old = SemanticReviewService(Replay(payload()), "fixture").review(target=value, canon=canon)
    assert review_is_current(old, target=value, canon=canon)
    assert not review_is_current(old, target=value, canon=canon, author_brief="可信简报。")


@pytest.mark.parametrize("brief", ["", " ", "中"*12001, 1], ids=["empty", "blank", "oversize", "not_string"])
def test_invalid_explicit_brief_rejected_before_provider(brief):
    value, canon = plan_inputs()
    provider = Replay(payload())
    with pytest.raises(ContractError):
        SemanticReviewService(provider, "fixture").review(target=value, canon=canon, author_brief=brief)
    assert not provider.requests


def test_brief_maximum_and_scene_rejection():
    value, canon = plan_inputs()
    provider = Replay(payload())
    assert SemanticReviewService(provider, "fixture").review(target=value, canon=canon, author_brief="中"*12000).status == "pass"
    with pytest.raises(ContractError):
        SemanticReviewService(provider, "fixture").review(target=target(), canon=canon, author_brief="简报。")


def test_registry_prioritizes_authorities_without_truncating_target():
    value, canon = plan_inputs("中"*200000)
    canon = canon.model_copy(update={"facts": (CanonFact(id="rule", kind="node", text="不可复活。"),)})
    registry, coverage = build_evidence_sources(target=value, canon=canon, style_sources={"author_brief": "摘要宜简洁。"})
    assert list(registry.values())[0]["kind"] == "style"
    assert list(registry.values())[1]["kind"] == "canon"
    assert not coverage["complete"] and value.text == "中"*200000


def test_real_planning_run_freezes_author_brief_for_all_review_and_currentness_paths(setup):
    run = create(setup)
    service, critic = setup[5], setup[4]
    finished = service.execute(run.id)
    assert finished.status == "awaiting_review"
    assert all(json.loads(r.messages[-1].content)["style_sources"]["author_brief"] == run.request.instruction for r in critic.requests)
    for report_id in [s.review_id for s in finished.steps]+[finished.final_review_id]:
        assert service.review("book", run.id, report_id)["current"]
    assert service._review_inputs(finished)[1]["author_brief"] == run.request.instruction

def test_manual_blueprint_route_uses_original_validated_instruction(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from apps.api import main
    from storygraph.core.config import StoryGraphSettings
    from test_longform_planning import Provider
    planning = Provider()
    planning.chapters_per_volume = planning.scenes_per_chapter = 1
    captured = []
    class Combined:
        def generate(self, request):
            sent = json.loads(request.messages[-1].content)
            if "required_dimensions" in sent:
                captured.append(sent)
                return LLMResponse(json.dumps(payload(), ensure_ascii=False))
            return planning.generate(request)
    settings = StoryGraphSettings(tmp_path)
    settings.llm_base_url, settings.llm_api_key, settings.llm_model = "https://synthetic.invalid", "synthetic-only", "fixture"
    monkeypatch.setattr(main, "create_llm_provider", lambda _: Combined())
    app = main.create_app(settings)
    with TestClient(app) as client:
        project = client.post("/projects", json={"title": "合成简报作用域"}).json()["project_id"]
        brief = "保持简洁；摘要宜少于一百字。"
        result = client.post(f"/projects/{project}/longform/blueprints", json={"instruction": brief,
            "volume_count": 1, "chapters_per_volume": 1, "scenes_per_chapter": 1, "target_length": 10000})
        assert result.status_code == 200, result.text
        proposal = result.json()["proposal"]
        reviewed = client.post(f"/projects/{project}/generation-reviews", json={"target_type": "proposal",
            "target_id": proposal["id"], "expected_version": proposal["version"]})
        assert reviewed.status_code == 200, reviewed.text
        assert captured[-1]["style_sources"]["author_brief"] == brief
        assert reviewed.json()["current"]
        ready = client.post(f"/projects/{project}/proposals/{proposal['id']}/submit-review",
            json={"expected_version": proposal["version"]}).json()
        accepted = client.post(f"/projects/{project}/proposals/{proposal['id']}/accept",
            json={"expected_version": ready["version"], "reviewer": "author"}).json()
        review_accepted = client.post(f"/projects/{project}/generation-reviews", json={"target_type": "proposal",
            "target_id": accepted["id"], "expected_version": accepted["version"]})
        assert review_accepted.status_code == 200 and review_accepted.json()["report"]["status"] == "pass"
        sources = captured[-1]["style_sources"]
        legacy = GenerationReviewReport.model_validate(review_accepted.json()["report"]).model_copy(update={
            "id": "synthetic_legacy_brief_report", "style_fingerprint": style_fingerprint(
                style_rubric=[v for k, v in sources.items() if k.startswith("rubric:")],
                banned_phrases=[v for k, v in sources.items() if k.startswith("banned:")],
                preset_text=sources.get("preset", ""))})
        app.state.generation_review_store.save(legacy)
        historical = client.get(f"/projects/{project}/generation-reviews", params={"target_type": "proposal", "target_id": proposal["id"]}).json()["reports"]
        assert next(r for r in historical if r["report"]["id"] == legacy.id)["current"] is False
        rejected = client.post(f"/projects/{project}/proposals/{proposal['id']}/apply/longform", json={
            "expected_version": accepted["version"], "reviewer": "author", "review_id": legacy.id})
        assert rejected.status_code == 409
        applied = client.post(f"/projects/{project}/proposals/{proposal['id']}/apply/longform", json={
            "expected_version": accepted["version"], "reviewer": "author",
            "review_id": review_accepted.json()["report"]["id"]})
        assert applied.status_code == 200, applied.text
        parent = applied.json()["proposal"]
        expanded = client.post(f"/projects/{project}/longform/expansions", json={
            "parent_proposal_id": parent["id"], "parent_version": parent["version"],
            "volume_index": 1, "chapter_start": 1, "chapter_count": 1, "instruction": "只细化本章。"})
        assert expanded.status_code == 200, expanded.text
        child = expanded.json()["proposal"]
        review_child = client.post(f"/projects/{project}/generation-reviews", json={"target_type": "proposal",
            "target_id": child["id"], "expected_version": child["version"]})
        assert review_child.status_code == 200, review_child.text
        assert captured[-1]["style_sources"]["author_brief"] == brief
        assert captured[-1]["style_sources"]["author_brief"] != "只细化本章。"
        current = client.get(f"/projects/{project}/generation-reviews", params={"target_type": "proposal", "target_id": child["id"]})
        assert current.status_code == 200



@pytest.mark.parametrize("stale_scope", ["step", "step_before_final", "final", "step_nonpass"])
def test_stale_cached_report_cannot_create_ready_bundle_or_schedule_paid_refresh(setup, stale_scope):
    from storygraph.models.planning_run import PlanningRunResume
    run = create(setup)
    service, store, proposals = setup[5], setup[2], setup[1]
    done = service.execute(run.id)
    report_id = done.steps[0].review_id if stale_scope.startswith("step") else done.final_review_id
    old = store.report(run.id, report_id)
    _, style = service._review_inputs(done)
    legacy_style = {key: value for key, value in style.items() if key != "author_brief"}
    legacy = old.model_copy(update={"id": old.id+"_legacy", "style_fingerprint": old.style_fingerprint if stale_scope == "step_nonpass" else style_fingerprint(**legacy_style),
        "status": "inconclusive" if stale_scope == "step_nonpass" else old.status})
    steps = [step.model_copy(deep=True) for step in done.steps]
    if stale_scope.startswith("step"):
        steps[0].review_id = legacy.id
    updates = {"status": "paused", "pause_reason": "stopped", "bundle_proposal_id": None, "steps": steps,
        "final_review_id": legacy.id if stale_scope == "final" else None if stale_scope == "step_before_final" else done.final_review_id}
    paused = store.update(done.model_copy(update=updates), done.version, report=legacy)
    count = len(proposals.list(project_id="book"))
    reserved = paused.calls_reserved
    counts = len(setup[3].calls), len(setup[4].requests)
    original = legacy.model_dump_json()
    queued = service.resume("book", run.id, PlanningRunResume(expected_version=paused.version))
    result = service.execute(queued.id)
    assert result.status == "paused" and result.pause_reason == "review_failed"
    assert result.bundle_proposal_id is None and len(proposals.list(project_id="book")) == count
    assert result.calls_reserved == reserved and (len(setup[3].calls), len(setup[4].requests)) == counts
    assert store.report(run.id, legacy.id).model_dump_json() == original
    assert result.restart_history == paused.restart_history
