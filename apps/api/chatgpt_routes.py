"""Local user controls for the ChatGPT connection. OAuth material stays in the backend."""
from ipaddress import ip_address
from typing import Literal
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from storygraph.core.agent_config import AgentPermissionLevel
from storygraph.services.chatgpt_login import ChatGPTLoginError, get_default_chatgpt_login_service
from storygraph.services.chatgpt_plan_provider import ChatGPTPlanProvider
from storygraph.services.llm_provider import ProviderError


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Start(_Body):
    account_id: str | None = Field(default=None, min_length=1, max_length=200)


class Account(_Body):
    account_id: str = Field(min_length=1, max_length=200)


class Cancel(_Body):
    attempt_id: str = Field(min_length=1, max_length=200)


class AccountView(BaseModel):
    account_id: str
    label: str
    email: str | None = None
    connected: bool
    plan_enabled: bool
    welcome_pending: bool


class Status(BaseModel):
    supported: bool
    active_account_id: str | None
    accounts: list[AccountView]
    error: str | None = None


class SignedOut(Status):
    remote_revocation_confirmed: bool


class Attempt(BaseModel):
    attempt_id: str
    status: Literal["pending", "completed", "failed", "cancelled", "expired"]
    error: str | None = None
    account_id: str | None = None


def login_service(settings):
    injected = getattr(settings, "chatgpt_login", None)
    return injected if injected is not None else get_default_chatgpt_login_service()


def _local_host(name):
    if name == "localhost":
        return True
    try:
        return ip_address(name).is_loopback
    except (ValueError, TypeError):
        return False


def is_local_plan_request(request: Request, origins) -> bool:
    # Check the actual peer, the addressed Host and the browser origin separately.
    # A configurable CORS allowlist alone must not expose a user's plan over LAN.
    if not request.client or not _local_host(request.client.host):
        return False
    try:
        address = urlsplit("//" + request.headers.get("host", ""))
        if (not _local_host(address.hostname) or address.path or address.query or address.fragment
                or address.username is not None or address.password is not None):
            return False
        origin = request.headers.get("origin")
        if origin is None:
            return request.headers.get("sec-fetch-site", "") != "cross-site"
        if origin in {"tauri://localhost", "http://tauri.localhost", "https://tauri.localhost"}:
            return True
        parsed = urlsplit(origin)
        if parsed.scheme not in {"http", "https"} or not _local_host(parsed.hostname):
            return False
        if parsed.path or parsed.query or parsed.fragment or parsed.username is not None or parsed.password is not None:
            return False
        same_origin = parsed.scheme == request.url.scheme and parsed.netloc == address.netloc
        return same_origin or origin in origins
    except ValueError:
        return False


def require_local_plan(request, origins):
    if not is_local_plan_request(request, origins):
        raise HTTPException(403, detail={"category": "chatgpt_local_only",
                            "message": "请从本机的 StoryGraph 桌面版或本地工作台管理和使用 ChatGPT 套餐。"})


def register_chatgpt_routes(app, settings, require_permission, origins, *, record_models=None):
    prefix = "/settings/chatgpt"

    def local_control(request: Request):
        require_local_plan(request, origins)
        if request.method == "POST" and request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
            raise HTTPException(415, detail={"category": "chatgpt_json_required"})

    guards = [Depends(local_control)]

    def account_call(method, *args):
        try:
            return getattr(login_service(settings), method)(*args)
        except ChatGPTLoginError as exc:
            raise HTTPException(409, detail={"category": exc.category, "message": "ChatGPT connection unavailable."}) from None

    @app.get(prefix, dependencies=guards, response_model=Status)
    def status():
        return account_call("status")

    @app.post(prefix + "/login", dependencies=guards, response_model=Attempt)
    def start(body: Start):
        return account_call("begin_login", body.account_id)

    @app.get(prefix + "/login/{attempt_id}", dependencies=guards, response_model=Attempt)
    def login_status(attempt_id: str):
        return account_call("login_status", attempt_id)

    @app.post(prefix + "/cancel", dependencies=guards, response_model=Attempt)
    def cancel(body: Cancel):
        return account_call("cancel_login", body.attempt_id)

    @app.post(prefix + "/select", dependencies=guards, response_model=Status)
    def select(body: Account):
        return account_call("select_account", body.account_id)

    @app.post(prefix + "/welcome", dependencies=guards, response_model=Status)
    def welcome(body: Account):
        return account_call("acknowledge_welcome", body.account_id)

    @app.post(prefix + "/logout", dependencies=guards, response_model=SignedOut)
    def logout(body: Account):
        result = account_call("unlink", body.account_id)
        return {**account_call("status"), "remote_revocation_confirmed": result["remote_revocation_confirmed"]}

    @app.get(prefix + "/models", dependencies=guards)
    def models(account_id: str):
        require_permission(AgentPermissionLevel.READ_GENERATE)
        if not account_call("account_ready", account_id):
            return {"models": [], "status": "unavailable", "error": "plan_permission_required"}
        provider = ChatGPTPlanProvider(model="", account_id=account_id, timeout_seconds=15,
                                      login_service=login_service(settings))
        try:
            rows = provider.list_models()
            if record_models is not None:
                record_models(account_id, rows)
            return {"models": rows, "status": "ok", "error": None}
        except ProviderError as exc:
            return {"models": [], "status": "unavailable", "error": exc.category}
