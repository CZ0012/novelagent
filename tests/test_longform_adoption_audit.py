"""Independent regression checks for the long-form opt-in adoption boundary."""

import json

import pytest
from fastapi.testclient import TestClient

from apps.api import main
from storygraph.core.config import StoryGraphSettings
from storygraph.demo import PROJECT_ID, SCENE_ID, build_fantasy_demo_graph
from storygraph.models.generation_review import REVIEW_DIMENSIONS
from storygraph.services.llm_provider import LLMResponse
from storygraph.stores.json_graph import save_json_graph


SEED = {"source_ref": "test:adoption-audit", "reviewer": "author", "rationale": "合成审计夹具。"}


@pytest.fixture
def audit_setup(tmp_path, monkeypatch):
    graph = build_fantasy_demo_graph("zh-CN")
    graph.seed_canon_node(node_id="style_audit", node_type="StyleProfile", properties={
        "project_id": PROJECT_ID, "name": "项目文风", "pov": "第三人称有限视角", "tone": "克制",
        "rubric": ["以行动呈现情绪。"], "banned_patterns": ["突然之间"],
    }, **SEED)
    graph.update_node(PROJECT_ID, {"style_profile_id": "style_audit", "require_semantic_review": True}, **SEED)
    graph.update_node(SCENE_ID, {"style_constraints": {"tone": "轻快", "rubric": ["本场景允许诙谐对话。"],
                                                     "banned_patterns": ["故作高深"]}}, **SEED)
    settings = StoryGraphSettings(tmp_path)
    settings.llm_base_url = "https://fixture.invalid"
    settings.llm_api_key = "synthetic-test-secret"
    settings.llm_model = "fixture-model"
    settings.graph_backend = "json"
    settings.graph_backend_explicit = True
    save_json_graph(graph, settings.graph_path)
    class Provider:
        def __init__(self):
            self.requests = []
        def generate(self, request):
            self.requests.append(request)
            return LLMResponse(json.dumps({"status": "pass", "summary": "当前范围内未发现矛盾。",
                "dimensions_checked": list(REVIEW_DIMENSIONS), "issues": []}, ensure_ascii=False))
    provider = Provider()
    monkeypatch.setattr(main, "create_llm_provider", lambda _: provider)
    return TestClient(main.create_app(settings)), provider


def accepted_proposal(client, via="llm"):
    response = client.post(f"/projects/{PROJECT_ID}/proposals", json={
        "artifact_type": "scene_draft", "title": "合成正文提案", "body": "林烬站在门边，没有打开密信。",
        "created_via": via, "target_refs": [{"kind": "scene", "ref": SCENE_ID}],
    })
    assert response.status_code == 200, response.text
    proposal = response.json()
    ready = client.post(f"/projects/{PROJECT_ID}/proposals/{proposal['id']}/submit-review",
                        json={"expected_version": proposal["version"]}).json()
    accepted = client.post(f"/projects/{PROJECT_ID}/proposals/{proposal['id']}/accept",
                           json={"expected_version": ready["version"], "reviewer": "author"})
    assert accepted.status_code == 200, accepted.text
    return accepted.json()


def test_acceptance_provenance_cannot_bypass_required_semantic_review(audit_setup):
    client, provider = audit_setup
    proposal = accepted_proposal(client)
    # Review is a human operation; detection cannot rely on current created_via.
    assert proposal["provenance"]["created_via"] == "manual"
    response = client.post(f"/projects/{PROJECT_ID}/proposals/{proposal['id']}/promote/draft", json={
        "scene_id": SCENE_ID, "expected_version": proposal["version"],
    })
    assert response.status_code == 409, response.text
    assert not provider.requests
    assert client.get(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/draft").json()["draft"] is None


def test_manual_draft_save_remains_available_in_guarded_project(audit_setup):
    client, provider = audit_setup
    response = client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/draft",
                           json={"text": "作者亲自保存的合成文字。"})
    assert response.status_code == 200, response.text
    assert not provider.requests


def test_scene_style_overrides_are_used_by_semantic_review(audit_setup):
    client, provider = audit_setup
    draft = client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/draft",
                        json={"text": "林烬站在门边，打量门上的锁。"}).json()
    pack = client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/context-pack", json={}).json()
    saved = client.put(f"/projects/{PROJECT_ID}/writer-visibility", json={"expected_version":0, "spec":{
        "access_mode":"surface", "surface_plan":{"kind":"literal", "text":"林烬观察门上的锁。"},
        "writer_style":{}, "characters":[{"character_id":pack["pov_character_id"], "public_name":"林烬"}],
        "visible_claims":[{"text":text,"presentation":"observation","phase":"during_scene"} for text in pack["must_include"]],
    }})
    assert saved.status_code == 200, saved.text
    response = client.post(f"/projects/{PROJECT_ID}/generation-reviews", json={
        "target_type": "draft", "target_id": draft["id"], "expected_version": draft["version"], "scene_id": SCENE_ID,
    })
    assert response.status_code == 200, response.text
    payload = json.loads(provider.requests[-1].messages[-1].content)
    sources = payload["style_sources"]
    assert any("本场景允许诙谐对话。" in value for value in sources.values())
    assert any("轻快" in value for value in sources.values())
    assert "故作高深" in sources.values()
    assert "突然之间" not in sources.values()
