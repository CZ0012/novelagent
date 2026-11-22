"""First-use model setup is an atomic, scoped write. Titling cannot change payer."""
from fastapi.testclient import TestClient

from apps.api import main
from storygraph.core.config import StoryGraphSettings
from storygraph.services.llm_provider import LLMResponse


def test_targeted_connections_preserve_other_settings_and_are_idempotent(tmp_path):
    api = TestClient(main.create_app(StoryGraphSettings(tmp_path)))
    profile = {"id": "first", "name": "First", "protocol": "responses", "model": "model-a",
               "base_url": "https://example.invalid/v1", "api_key": "fixture-only"}
    body = {"profile": profile, "use_for_main_agent": False}
    assert api.post("/settings/agent/connections", json=body).status_code == 200
    api.put("/settings/agent", json={"task_assignments": {"writing": "first"}, "llm_model":"keep-this"})
    body.update(use_for_main_agent=True)
    second = api.post("/settings/agent/connections", json={**body, "profile": {**profile, "id":"other-id"}})
    assert second.status_code == 200
    assert second.json()["profile_id"] == "first"
    settings = second.json()["settings"]
    assert len(settings["connection_profiles"]) == 1
    assert settings["llm_model"] == "keep-this"
    assert settings["task_assignments"]["writing"] == settings["task_assignments"]["discussion"] == "first"
    assert profile["api_key"] not in second.text
    omitted = {k:v for k,v in profile.items() if k != "api_key"}
    assert api.post("/settings/agent/connections",json={**body,"profile":omitted}).status_code == 200
    assert api.post("/settings/agent/connections",json={**body,"profile":{**omitted,"base_url":"https://other.invalid"}}).status_code == 422


def test_explicit_discovery_then_new_session_titles_on_same_connection(tmp_path, monkeypatch):
    sent = []
    class Provider:
        timeout_seconds = 15

        def __init__(self, runtime):
            self.runtime = runtime

        def list_models(self):
            return [{"id":"gpt-6-luna"}, {"id":"large-model"}]

        def generate(self, request):
            sent.append((self.runtime.llm_model, self.runtime.llm_api_key, request))
            return LLMResponse("车站来信")

    monkeypatch.setattr(main,"create_llm_provider",Provider)
    api = TestClient(main.create_app(StoryGraphSettings(tmp_path)))
    profile={"id":"main","name":"Author","protocol":"responses","model":"large-model",
             "base_url":"https://api.openai.com/v1","api_key":"offline-fixture-a"}
    def connect(p):
        assert api.post("/settings/agent/connections",json={"profile":p,"use_for_main_agent":True}).status_code==200
    connect(profile)
    project=api.post("/projects",json={"title":"车站","language":"zh-CN"}).json()["project_id"]
    base=f"/projects/{project}/authoring-sessions"
    first="我想写一封在车站寄出的信。"
    def new():
        r=api.post(base,json={"title":first,"idea":first,"auto_title":True})
        assert r.status_code==200,r.text
        return r.json()["session"]["id"]
    new()
    assert not sent
    assert api.get("/settings/agent/models?profile_id=main").json()["status"]=="ok"
    session=new()
    assert len(sent)==1 and sent[0][:2]==("gpt-6-luna","offline-fixture-a")
    assert [m.content for m in sent[0][2].messages if m.role=="user"]==[first]
    assert api.get(base+"/"+session).json()["session"]["title"]=="车站来信"
    assert api.put("/settings/agent/title-preferences",json={"enabled":False,"model":None}).status_code==200
    new()
    assert len(sent)==1
    api.put("/settings/agent/title-preferences",json={"enabled":True,"model":None})
    connect({**profile,"id":"other","api_key":"offline-fixture-b"})
    new()
    assert len(sent)==1
