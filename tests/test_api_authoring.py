import json

import pytest
from fastapi.testclient import TestClient

from apps.api import main
from storygraph.core.config import StoryGraphSettings
from storygraph.demo import PROJECT_ID, SCENE_ID
from storygraph.models.generation_review import REVIEW_DIMENSIONS
from storygraph.services.llm_provider import LLMResponse


class Provider:
    def __init__(self):
        self.requests = []
        self.response_override = None

    def generate(self, request):
        self.requests.append(request)
        payload = json.loads(request.messages[-1].content)
        output = {"status": "pass", "summary": "检查范围内未发现明确矛盾。",
                  "dimensions_checked": list(REVIEW_DIMENSIONS), "issues": []}
        if "source_draft_id" in payload:
            output = {"facts": []}
        return LLMResponse(json.dumps(self.response_override or output, ensure_ascii=False))


@pytest.fixture
def setup(tmp_path, monkeypatch):
    settings = StoryGraphSettings(tmp_path)
    settings.llm_base_url = "https://fixture.invalid"
    settings.llm_api_key = "synthetic-test-secret"
    settings.llm_model = "fixture-model"
    provider = Provider()
    monkeypatch.setattr(main, "create_llm_provider", lambda _: provider)
    app = main.create_app(settings)
    client = TestClient(app)
    assert client.post("/demo/seed", json={"locale": "zh-CN"}).status_code == 200
    return client, provider, settings


def saved_draft(client):
    response = client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/draft",
                           json={"text": "林烬在钟楼门口停下。他还不知道密信藏在哪里。"})
    assert response.status_code == 200
    return response.json()


def review(client, draft):
    return client.post(f"/projects/{PROJECT_ID}/generation-reviews", json={
        "target_type": "draft", "target_id": draft["id"], "expected_version": draft["version"],
        "scene_id": SCENE_ID,
    })


def test_review_persists_without_mutating_canon_and_restarts(setup):
    client, provider, settings = setup
    draft = saved_draft(client)
    before = client.get(f"/projects/{PROJECT_ID}/graph/preview").json()
    result = review(client, draft)
    assert result.status_code == 200, result.text
    assert result.json()["report"]["status"] == "pass"
    assert result.json()["current"] is True
    assert client.get(f"/projects/{PROJECT_ID}/graph/preview").json() == before
    assert len(provider.requests) == 1
    restarted = TestClient(main.create_app(settings))
    history = restarted.get(f"/projects/{PROJECT_ID}/generation-reviews",
                            params={"target_type": "draft", "target_id": draft["id"]})
    assert history.status_code == 200
    assert history.json()["reports"][0]["current"] is True


def test_review_refuses_stale_version_and_foreign_project_before_model(setup):
    client, provider, _ = setup
    draft = saved_draft(client)
    stale = {**draft, "version": 999}
    assert review(client, stale).status_code == 409
    other = client.post("/projects", json={"title": "另一部小说"}).json()["project_id"]
    response = client.post(f"/projects/{other}/generation-reviews", json={
        "target_type": "draft", "target_id": draft["id"], "expected_version": draft["version"],
    })
    assert response.status_code == 404
    assert not provider.requests


def test_review_freshness_changes_with_canon_and_preset(setup):
    client, _, _ = setup
    draft = saved_draft(client)
    assert review(client, draft).status_code == 200
    client.put("/settings/agent", json={"selected_preset_id": "builtin_balanced"})
    history = client.get(f"/projects/{PROJECT_ID}/generation-reviews",
                         params={"target_type": "draft", "target_id": draft["id"]}).json()
    assert history["reports"][0]["current"] is False


def test_paid_review_is_permission_gated_but_history_is_readable(setup):
    client, provider, _ = setup
    draft = saved_draft(client)
    client.put("/settings/agent", json={"permission_level": "read_only"})
    assert review(client, draft).status_code == 403
    assert client.get(f"/projects/{PROJECT_ID}/generation-reviews",
                      params={"target_type": "draft", "target_id": draft["id"]}).status_code == 200
    assert not provider.requests


def test_invalid_review_output_is_inconclusive_not_pass(setup):
    client, provider, _ = setup
    provider.response_override = {"status": "pass", "summary": "ok"}
    result = review(client, saved_draft(client))
    assert result.status_code == 200
    assert result.json()["report"]["status"] == "inconclusive"
    assert "semantic_review_invalid_output" in result.json()["report"]["coverage"]["limitations"]


def test_natural_state_creates_only_fact_proposal(setup):
    client, _, _ = setup
    draft = saved_draft(client)
    graph_before = client.get(f"/projects/{PROJECT_ID}/graph/preview").json()
    pending_before = client.get(f"/projects/{PROJECT_ID}/facts/pending").json()
    result = client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/extract-natural-state",
                         json={"draft_id": draft["id"], "expected_version": draft["version"]})
    assert result.status_code == 200, result.text
    assert result.json()["proposal"]["artifact_type"] == "fact_draft"
    assert result.json()["candidates"] == []
    assert result.json()["proposal"]["source_refs"][0]["ref"] == draft["id"]
    assert client.get(f"/projects/{PROJECT_ID}/graph/preview").json() == graph_before
    assert client.get(f"/projects/{PROJECT_ID}/facts/pending").json() == pending_before


def test_adoption_rejects_attached_nonpassing_review(setup):
    client, provider, _ = setup
    proposal = client.post(f"/projects/{PROJECT_ID}/proposals", json={
        "artifact_type": "scene_draft", "title": "待审正文", "body": "林烬在门口停下。",
        "target_refs": [{"kind": "scene", "ref": SCENE_ID}], "created_via": "llm",
    }).json()
    proposal = client.post(f"/projects/{PROJECT_ID}/proposals/{proposal['id']}/submit-review",
                           json={"expected_version": proposal["version"]}).json()
    proposal = client.post(f"/projects/{PROJECT_ID}/proposals/{proposal['id']}/accept",
                           json={"expected_version": proposal["version"], "reviewer": "test"}).json()
    assert proposal["status"] == "accepted"
    provider.response_override = {"status": "pass", "summary": "invalid"}
    report = client.post(f"/projects/{PROJECT_ID}/generation-reviews", json={
        "target_type": "proposal", "target_id": proposal["id"],
        "expected_version": proposal["version"],
    }).json()["report"]
    result = client.post(f"/projects/{PROJECT_ID}/proposals/{proposal['id']}/promote/draft", json={
        "scene_id": SCENE_ID, "expected_version": proposal["version"], "review_id": report["id"],
    })
    assert result.status_code == 409


@pytest.mark.parametrize("schema", ["longform_branch_plan_v1", "longform_book_bundle_v1"])
def test_planning_manifests_require_their_pinned_run_review(setup, schema):
    client, provider, _ = setup
    proposal = client.post(f"/projects/{PROJECT_ID}/proposals", json={
        "artifact_type": "outline_draft", "title": "合成内部规划引用",
        "body_format": "structured_json", "body": json.dumps({"schema": schema}),
        "target_refs": [{"kind": "project", "ref": PROJECT_ID}],
    }).json()
    response = client.post(f"/projects/{PROJECT_ID}/generation-reviews", json={
        "target_type": "proposal", "target_id": proposal["id"],
        "expected_version": proposal["version"],
    })
    assert response.status_code == 409
    assert not provider.requests
