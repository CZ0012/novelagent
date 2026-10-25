"""Manual review pins the applied parent and whole-volume progress, without writes."""

import json

import pytest
from fastapi.testclient import TestClient

from apps.api import main
from storygraph.core.config import StoryGraphSettings
from storygraph.models.generation_review import REVIEW_DIMENSIONS
from storygraph.models.longform import BlueprintRequest, ExpansionRequest, LongformApplyRequest
from storygraph.services.canon_snapshot import canonical_json, content_hash
from storygraph.services.llm_provider import LLMResponse
from storygraph.services.longform_planning import generate_blueprint, generate_expansion, apply_longform, graph_plan_id
from storygraph.stores.json_graph import save_json_graph
from storygraph.stores.proposal_store import SQLiteProposalStore
from test_longform_planning import Provider


@pytest.fixture
def setup(tmp_path, monkeypatch):
    settings = StoryGraphSettings(tmp_path)
    settings.graph_backend, settings.graph_backend_explicit = "json", True
    settings.llm_base_url, settings.llm_api_key, settings.llm_model = "https://fixture.invalid", "synthetic-test-key", "fixture-model"
    captured = {}
    factory = main.open_configured_graph_store
    def graph_factory(*args, **kwargs):
        value = factory(*args, **kwargs)
        captured["graph"] = value.graph
        return value
    monkeypatch.setattr(main, "open_configured_graph_store", graph_factory)
    class Reviewer:
        def __init__(self):
            self.requests = []
        def generate(self, request):
            self.requests.append(request)
            return LLMResponse(json.dumps({"status": "pass", "summary": "已检查所列规划范围。",
                "dimensions_checked": list(REVIEW_DIMENSIONS), "issues": []}, ensure_ascii=False))
    reviewer = Reviewer()
    monkeypatch.setattr(main, "create_llm_provider", lambda _: reviewer)
    client = TestClient(main.create_app(settings))
    project_id = client.post("/projects", json={"title": "人工扩章审阅测试", "language": "zh-CN"}).json()["project_id"]
    proposals = SQLiteProposalStore(settings.proposal_store_path)
    writer = Provider()
    writer.chapters_per_volume, writer.scenes_per_chapter = 20, 2
    parent = generate_blueprint(graph=captured["graph"], store=proposals, project_id=project_id,
        request=BlueprintRequest(instruction="设计完整五卷框架。"), provider=writer, model="fixture-model")["proposal"]
    parent = proposals.review(parent["id"], decision="accepted", reviewer="author", expected_version=parent["version"])
    return client, reviewer, settings, captured["graph"], proposals, writer, project_id, parent


def apply_parent(setup):
    _, _, settings, graph, proposals, _, project_id, parent = setup
    result = apply_longform(graph=graph, store=proposals, project_id=project_id, proposal_id=parent.id,
        request=LongformApplyRequest(expected_version=parent.version, reviewer="author"),
        persist_snapshot=lambda staged: save_json_graph(staged, settings.graph_path))
    return proposals.get(result["proposal"]["id"])


def expansion(setup, parent):
    _, _, _, graph, proposals, writer, project_id, _ = setup
    result = generate_expansion(graph=graph, store=proposals, project_id=project_id,
        request=ExpansionRequest(parent_proposal_id=parent.id, parent_version=parent.version, volume_index=1, chapter_count=5),
        provider=writer, model="fixture-model")
    return proposals.get(result["proposal"]["id"])


def review(setup, proposal):
    return setup[0].post(f"/projects/{setup[6]}/generation-reviews", json={"target_type": "proposal",
        "target_id": proposal.id, "expected_version": proposal.version})


def test_manual_expansion_review_supplies_exact_parent_and_twenty_chapter_progress(setup):
    parent = apply_parent(setup)
    proposal = expansion(setup, parent)
    graph, proposals = setup[3], setup[4]
    before = dict(graph.nodes), list(graph.event_log.list()), len(proposals.history(parent.id)), len(proposals.history(proposal.id))
    response = review(setup, proposal)
    assert response.status_code == 200, response.text
    assert response.json()["current"] and response.json()["report"]["status"] == "pass"
    sent = json.loads(setup[1].requests[-1].messages[-1].content)
    context = sent["plan_content"]
    assert "text" not in sent["target"]
    assert context["current_plan"] == json.loads(proposal.body)
    assert context["parent_blueprint"] == json.loads(parent.body)["blueprint"]
    assert context["parent_ref"] == {"id": parent.id, "version": parent.version, "body_sha256": content_hash(parent.body)}
    assert context["author_brief"] == json.loads(parent.body)["request"]["instruction"]
    assert context["volume_progress"]["chapters_per_volume"] == 20
    assert context["volume_progress"]["batch_chapter_indices"] == [1, 2, 3, 4, 5]
    assert context["volume_progress"]["remaining_chapter_indices"] == list(range(6, 21))
    assert not context["volume_progress"]["is_final_batch"]
    assert response.json()["report"]["target_text_sha256"] == content_hash(canonical_json(context))
    assert sent["target"]["target_text_sha256"] == content_hash(canonical_json(context))
    assert (graph.nodes, graph.event_log.list(), len(proposals.history(parent.id)), len(proposals.history(proposal.id))) == before


@pytest.mark.parametrize("damage", ["unapplied", "version", "foreign"])
def test_invalid_parent_scope_or_application_rejected_before_manual_review_call(setup, damage):
    parent = apply_parent(setup)
    proposal = expansion(setup, parent)
    proposals = setup[4]
    raw = json.loads(proposal.body)
    if damage == "unapplied":
        draft_parent = proposals.get(parent.id, version=1).model_copy(update={"id": "unapplied_parent", "version": 1,
            "status": "agent_revised", "derived_refs": []})
        proposals.create(draft_parent)
        selected = proposals.review(draft_parent.id, decision="accepted", reviewer="author", expected_version=1)
        raw["parent_proposal_id"] = raw["request"]["parent_proposal_id"] = selected.id
        raw["parent_version"] = raw["request"]["parent_version"] = selected.version
    elif damage == "version":
        raw["parent_version"] = raw["request"]["parent_version"] = parent.version-1
    else:
        other = setup[0].post("/projects", json={"title": "另一项目"}).json()["project_id"]
        foreign = proposals.get(parent.id, version=1).model_copy(update={"id": "foreign_parent", "project_id": other})
        foreign_body = json.loads(foreign.body)
        foreign_body["project_id"] = other
        foreign = foreign.model_copy(update={"body": json.dumps(foreign_body, ensure_ascii=False)})
        proposals.create(foreign)
        selected = proposals.review(foreign.id, decision="accepted", reviewer="author", expected_version=1)
        raw["parent_proposal_id"] = raw["request"]["parent_proposal_id"] = selected.id
        raw["parent_version"] = raw["request"]["parent_version"] = selected.version
    invalid = proposal.model_copy(update={"id": "invalid_expansion", "body": json.dumps(raw, ensure_ascii=False)})
    proposals.create(invalid)
    response = review(setup, invalid)
    assert response.status_code in {404, 409}, response.text
    assert not setup[1].requests


def test_parent_body_hash_change_invalidates_saved_manual_report_without_another_call(setup):
    parent = apply_parent(setup)
    proposal = expansion(setup, parent)
    assert review(setup, proposal).json()["current"]
    proposals = setup[4]
    body = json.loads(parent.body)
    body["blueprint"]["synopsis"] += "新增一条需要重新审阅的因果说明。"
    changed = parent.model_copy(update={"body": json.dumps(body, ensure_ascii=False)})
    # Synthetic same-version storage corruption specifically proves freshness
    # binds actual parent content, not merely its ID and declared version.
    with proposals._lock:
        proposals._connection.execute("UPDATE proposal_artifacts SET payload_json=? WHERE id=? AND version=?",
            (changed.model_dump_json(), parent.id, parent.version))
        proposals._connection.commit()
    response = setup[0].get(f"/projects/{setup[6]}/generation-reviews", params={"target_type": "proposal", "target_id": proposal.id})
    assert response.status_code == 200, response.text
    assert response.json()["reports"][0]["current"] is False and len(setup[1].requests) == 1


def test_manual_review_keeps_all_prior_planned_outcomes_after_recent_twelve_window(setup):
    parent = apply_parent(setup)
    _, _, settings, graph, proposals, writer, project_id, _ = setup
    for start in (1, 6):
        generated = generate_expansion(graph=graph, store=proposals, project_id=project_id,
            request=ExpansionRequest(parent_proposal_id=parent.id, parent_version=parent.version,
                volume_index=1, chapter_start=start, chapter_count=5), provider=writer, model="fixture-model")["proposal"]
        accepted = proposals.review(generated["id"], decision="accepted", reviewer="author", expected_version=generated["version"])
        apply_longform(graph=graph, store=proposals, project_id=project_id, proposal_id=accepted.id,
            request=LongformApplyRequest(expected_version=accepted.version, reviewer="author"),
            persist_snapshot=lambda staged: save_json_graph(staged, settings.graph_path))
    old_id = graph_plan_id(parent.id, "scene", "v01_c001_s01")
    sealed = "本地原始日志已登记封存；后续取得的是工作副本。"
    timeline = "事件第1日22:30，记录次日09:20上传。"
    graph.update_node(old_id, {"outcome": sealed, "timeline_position": timeline},
        reviewer="author", rationale="Synthetic prior-plan anchor.", source_ref="test:anchor")
    current = generate_expansion(graph=graph, store=proposals, project_id=project_id,
        request=ExpansionRequest(parent_proposal_id=parent.id, parent_version=parent.version,
            volume_index=1, chapter_start=11, chapter_count=5), provider=writer, model="fixture-model")["proposal"]
    assert review(setup, proposals.get(current["id"])).status_code == 200
    sent = json.loads(setup[1].requests[-1].messages[-1].content)
    context = sent.get("plan_content") or json.loads(sent["target"]["text"])
    assert len(context["recent_scene_outcomes"]) == 12
    assert all(scene["id"] != "v01_c001_s01" for scene in context["recent_scene_outcomes"])
    ledger = context["prior_scene_outcome_ledger"]
    assert len(ledger["scenes"]) == 20
    assert ledger["scenes"][0]["outcome"] == sealed and ledger["scenes"][0]["timeline_position"] == timeline
    assert ledger["scenes"][0]["pov_character_id"] == "courier" and ledger["scenes"][0]["location_id"] == "harbor"
