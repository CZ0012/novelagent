"""Independent real-HTTP author-session concurrency checks; no real provider."""
from test_api_authoring_sessions import api as api
from storygraph.services.llm_provider import LLMResponse


def test_inflight_project_language_change_blocks_author_result(api):
    client, app, provider, project, _ = api
    base = f"/projects/{project}/authoring-sessions"
    session = client.post(base, json={"title":"想法", "idea":"车站上失踪的姐姐。"}).json()["session"]
    path = base + "/" + session["id"]
    def generate(request):
        changed = client.patch(f"/projects/{project}", json={"language":"en-US", "expected_language":"zh-CN", "language_change_policy":"future_outputs_only", "reviewer":"author", "rationale":"Change future output language."})
        assert changed.status_code == 200, changed.text
        return LLMResponse('{"tool":"finish","args":{"message":"我们继续讨论姐姐的动机。"}}')
    provider.generate = generate
    response = client.post(path + "/turn", json={"expected_version":session["version"], "message":"继续讨论。", "max_steps":1})
    assert response.status_code == 409, response.text
    latest = client.get(path).json()["session"]
    assert all(m["content"] != "我们继续讨论姐姐的动机。" for m in latest["messages"])
