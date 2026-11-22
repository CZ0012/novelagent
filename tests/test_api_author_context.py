"""No-network HTTP coverage for author notebook and session navigation."""
from storygraph.services.authoring import AuthoringService, _message
from test_api_authoring_sessions import api as api


def test_notebook_rename_search_and_exact_old_message_http(api):
    client,app,provider,project,_ = api
    base = f"/projects/{project}"
    assert client.get(base + "/author-context").json()["version"] == 0
    result = client.put(base + "/author-context",json={"expected_version":0,"instructions":"偏爱克制对白。"})
    assert result.status_code == 200 and result.json()["version"] == 1
    assert client.put(base + "/author-context",json={"expected_version":0,"instructions":"旧覆盖"}).status_code == 409
    session = client.post(base + "/authoring-sessions",json={"title":"最初标题","idea":"我偏爱克制对白。"}).json()["session"]
    assert session["title_metadata"]["state"] == "disabled"
    path = base + "/authoring-sessions/" + session["id"]
    renamed = client.post(path + "/title",json={"expected_version":1,"title":"作者手动标题"})
    assert renamed.status_code == 200 and renamed.json()["title_metadata"]["origin"] == "manual"
    assert client.get(path).json()["session"]["title"] == "作者手动标题"
    assert client.get(path).json()["session"]["version"] == session["version"]
    assert client.post(path + "/title",json={"expected_version":1,"title":"旧覆盖"}).status_code == 409
    service = AuthoringService(store=app.state.authoring_store)
    current = service.get(project,session["id"])
    current.messages.extend(_message("author",f"旧检索{i}") for i in range(60))
    service._save(current)
    result = client.get(base + "/authoring-search",params={"query":"旧检索0","limit":1}).json()
    exact = client.get(path + "/messages/" + result["records"][0]["message_id"])
    assert exact.status_code == 200 and exact.json()["message"]["content"] == "旧检索0"
    context = app.state.author_context_store
    memory = context.record(project,session["id"],text="喜欢克制对白",kind="preference",status="active",source_message_id=session["messages"][0]["id"],evidence="我偏爱克制对白")
    assert client.get(base + "/author-memories").json()["total_matches"] == 1
    edited = client.patch(base + "/author-memories/" + memory["id"],json={"expected_version":1,"text":"撤回这条偏好","status":"withdrawn"})
    assert edited.status_code == 200
    assert client.get(base + "/author-memories").json()["records"] == []
    assert client.get(base + "/authoring-sessions",params={"query":"作者手动"}).json()["total_matches"] == 1
    assert provider.requests == []
