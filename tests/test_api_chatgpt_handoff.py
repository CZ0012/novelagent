"""The public login, connection assignment and prose handoff share the production router."""
import json

from fastapi.testclient import TestClient

from apps.api import main
from storygraph.services.llm_provider import LLMResponse
from tests.test_api_agent_discussion import _create_project_with_scene, _llm_settings


class LocalLogin:
    ready = True

    def status(self):
        return {"supported": True, "active_account_id": "local-registration", "accounts": [{
            "account_id": "local-registration", "label": "Test account", "email": None,
            "connected": self.ready, "plan_enabled": self.ready, "welcome_pending": False,
            "client_id": "private-fixture-registration", "refresh_token": "private-fixture-token",
        }]}

    def account_ready(self, account_id):
        return self.ready and account_id == "local-registration"

    def begin_login(self, account_id):
        return {"attempt_id": "local-attempt", "status": "pending", "nonce": "private-fixture-value"}


def local_client(app):
    # Older Starlette test clients have no client-address argument.
    async def loopback(scope, receive, send):
        await app({**scope, "client": ("127.0.0.1", 43980)}, receive, send)
    return TestClient(loopback, base_url="http://localhost")


def test_chatgpt_controls_return_only_public_fields_even_with_a_richer_service(tmp_path):
    settings = _llm_settings(tmp_path)
    settings.chatgpt_login = LocalLogin()
    app = main.create_app(settings)
    client = local_client(app)
    status = client.get("/settings/chatgpt")
    assert status.status_code == 200 and "private-fixture" not in status.text
    login = client.post("/settings/chatgpt/login", json={})
    assert login.status_code == 200 and "nonce" not in login.text
    assert client.post("/settings/chatgpt/login", json={}, headers={"Origin": "https://other.invalid"}).status_code == 403
    assert client.get("/settings/chatgpt", headers={"Host": "other.invalid"}).status_code == 403
    assert client.post("/settings/chatgpt/login", content="{}").status_code == 415
    assert TestClient(app).get("/settings/chatgpt").status_code == 403


def test_main_picks_ready_plan_and_exactly_that_writer_creates_the_proposal(tmp_path, monkeypatch):
    settings = _llm_settings(tmp_path)
    login = settings.chatgpt_login = LocalLogin()
    app = main.create_app(settings)
    client = local_client(app)
    project = _create_project_with_scene(client)
    profile = {"id": "plan", "name": "Selected writer", "protocol": "responses", "model": "test-model",
               "auth_mode": "chatgpt_plan", "chatgpt_account_id": "local-registration"}
    updated = client.put("/settings/agent", json={"connection_profiles": [profile]})
    assert updated.status_code == 200, updated.text
    assert updated.json()["connection_profiles"][0]["account_ready"]
    executions = []
    actions = iter([
        {"tool": "list_writers", "args": {}},
        {"tool": "pick_writer", "args": {"profile_id": "plan", "reason": "适合写这段克制的对话。"}},
        {"tool": "finish", "args": {"message": "这次场景已有选好的正文模型。"}},
        {"reply": "已准备本场草稿。", "proposal_title": "初稿", "proposal_body": "她站在门口，轻轻敲了一下。"},
    ])

    class Provider:
        def __init__(self, runtime):
            self.runtime = runtime

        def generate(self, request):
            executions.append((self.runtime.model_execution["profile_id"], self.runtime.llm_auth_mode))
            return LLMResponse(json.dumps(next(actions), ensure_ascii=False))

    monkeypatch.setattr(main, "create_llm_provider", Provider)
    sessions = f"/projects/{project}/authoring-sessions"
    session = client.post(sessions, json={"title": "选正文模型", "idea": "姐妹在门口相遇。"}).json()["session"]
    result = client.post(sessions + "/" + session["id"] + "/turn",
                         json={"expected_version": session["version"], "message": "请选本次的正文模型。"})
    assert result.status_code == 200, result.text
    choice = result.json()["session"]["writer_choice"]
    assert choice["auth_mode"] == "chatgpt_plan" and choice["profile_id"] == "plan"
    assert "fingerprint" in choice and executions == [("default", "api_key")] * 3
    ref = {k: choice[k] for k in ("profile_id", "fingerprint")}
    endpoint = f"/projects/{project}/scenes/scene_opening/agent-discussion"
    body = {"mode": "create_scene", "instruction": "写门口的相遇。", "writer_choice": ref}
    generated = client.post(endpoint, json=body)
    assert generated.status_code == 200, generated.text
    assert executions[-1] == ("plan", "chatgpt_plan")
    assert generated.json()["proposal"]["provenance"]["model_ref"] == "test-model"
    assert not client.get("/settings/agent").json()["task_assignments"]["writing"]
    login.ready = False
    assert client.post(endpoint, json=body).status_code == 409
    assert len(executions) == 4
    assert client.post(endpoint, json={**body, "mode": "discuss"}).status_code == 422
    assert client.get("/settings/agent").json()["connection_profiles"][0]["account_ready"] is False
    assert TestClient(app).get("/settings/agent/models", params={"profile_id": "plan"}).status_code == 403
