"""Offline official-plan wire, isolation, outcomes, and legacy-profile regression tests."""
import io
import json
from urllib import error

import pytest
from pydantic import ValidationError

from storygraph.core.agent_config import (AgentRuntimeConfig, AgentRuntimeConfigUpdate,
    ConnectionProfile, apply_agent_config, settings_for_task, update_agent_config)
from storygraph.core.config import StoryGraphSettings
from storygraph.services.chatgpt_plan_provider import ChatGPTPlanProvider, MAX_EVENT_BYTES
from storygraph.services.llm_provider import LLMMessage, LLMRequest, ProviderError
from storygraph.services.scene_writer_factory import create_llm_provider, provider_ready


class Login:
    def access_token(self, account_id):
        assert account_id == "account-1"
        return "synthetic-oauth-secret"
    def account_ready(self, account_id):
        return account_id == "account-1"


class Response(io.BytesIO):
    pass


def event(kind, **fields):
    return ("data: " + json.dumps({"type": kind, **fields}) + "\n\n").encode()


def completed(text='{"ok":true}'):
    return event("response.completed", response={"status": "completed", "output": [
        {"type": "message", "role": "assistant", "status": "completed",
         "content": [{"type": "output_text", "text": text}]}]})


def fixture_provider(body, captured=None):
    def open_response(req, **kwargs):
        if captured is not None:
            captured.append(req)
        return Response(body)
    provider = ChatGPTPlanProvider(model="account-model", account_id="account-1",
        login_service=Login(), opener=open_response)
    # Explicit credential injection keeps these transport tests independent of OAuth implementation.
    provider._token = lambda: Login().access_token("account-1")
    return provider


def payload():
    return LLMRequest(model="account-model", messages=[LLMMessage("system", "contract"),
        LLMMessage("user", "JSON please")], max_tokens=600, temperature=0.9)


def test_official_sse_preview_payload_and_no_diagnostic_escape():
    calls = []
    result = fixture_provider(event("response.output_text.delta", delta='{"ok":true}') + completed(), calls).generate(payload())
    assert result.content == '{"ok":true}' and result.raw == {}
    assert len(calls) == 1
    req = calls[0]
    assert req.full_url == "https://api.openai.com/v1/responses"
    assert req.get_header("Authorization") == "Bearer synthetic-oauth-secret"
    body = json.loads(req.data)
    assert body == {"model": "account-model", "instructions": "contract",
        "input": [{"role": "user", "content": "JSON please"}], "store": False,
        "stream": True, "text": {"format": {"type": "json_object"}}}


@pytest.mark.parametrize("body,category,known", [
    (event("response.output_text.delta", delta="partial private prose"), "incomplete_response", False),
    (event("response.incomplete"), "incomplete_response", True),
    (event("response.refusal.done", refusal="private"), "unsupported_output", True),
    (event("response.failed", response={"error": {"code": "subscription_sharing_usage_limit_exceeded", "message": "private"}}), "plan_usage_limit", True),
    (event("error", error={"code": "subscription_sharing_usage_unavailable"}), "plan_usage_unavailable", True),
    (b"data: invalid private json\n\n", "invalid_response", False),
    (b"data: " + b"x" * MAX_EVENT_BYTES, "invalid_response", False),
    (event("response.output_text.delta", delta="mismatch") + completed(), "invalid_response", True),
], ids=["disconnect", "incomplete", "refusal", "usage-limit", "usage-unavailable", "bad-json", "oversize", "mismatch"])
def test_terminal_and_uncertain_outcomes_never_return_partial_or_retry(body, category, known):
    calls = []
    with pytest.raises(ProviderError) as caught:
        fixture_provider(body, calls).generate(payload())
    assert len(calls) == 1
    assert caught.value.category == category and caught.value.outcome_known is known
    assert "private" not in str(caught.value) and "synthetic-oauth-secret" not in str(caught.value)


@pytest.mark.parametrize("body,status,category", [
    ({"detail": "private synthetic-oauth-secret"}, 401, "invalid_credentials"),
    ({"error": {"code": "subscription_sharing_user_not_eligible", "message": "private"}}, 403, "plan_not_eligible"),
    ({"error": {"code": "subscription_sharing_usage_limit_exceeded"}}, 429, "plan_usage_limit"),
])
def test_http_admission_safe_classification(body, status, category):
    calls = []
    def fail(req, **kwargs):
        calls.append(req)
        raise error.HTTPError(req.full_url, status, "private", {}, Response(json.dumps(body).encode()))
    provider = fixture_provider(b"")
    provider._opener = fail
    with pytest.raises(ProviderError) as caught:
        provider.generate(payload())
    assert len(calls) == 1 and caught.value.outcome_known
    assert caught.value.status == status and caught.value.category == category
    assert "private" not in str(caught.value)


def test_models_are_account_catalog_order_not_api_key_catalog():
    calls = []
    models = {"models": [{"slug": "second", "display_name": "Second", "visibility": "list"},
        {"slug": "hidden", "display_name": "Hidden", "visibility": "hidden"},
        {"slug": "first", "display_name": "First", "visibility": "list"}]}
    provider = fixture_provider(json.dumps(models).encode(), calls)
    assert provider.list_models() == [{"id": "second", "display_name": "Second"}, {"id": "first", "display_name": "First"}]
    assert calls[0].full_url == "https://api.openai.com/v1/models"


def profile(**changes):
    return {"id": "subscription", "name": "Subscription", "auth_mode": "chatgpt_plan",
        "protocol": "responses", "chatgpt_account_id": "account-1", "model": "account-model", **changes}


@pytest.mark.parametrize("changes", [{"base_url": "https://gateway.example"}, {"api_key": "key"},
    {"protocol": "chat_completions"}, {"chatgpt_account_id": None}, {"thinking_mode": "enabled"}])
def test_plan_rejects_endpoint_key_or_implicit_account(changes):
    with pytest.raises(ValidationError):
        ConnectionProfile(**profile(**changes))


def test_role_resolution_preserves_legacy_and_plan_snapshot(tmp_path):
    settings = StoryGraphSettings(tmp_path)
    settings.chatgpt_login = Login()
    config = AgentRuntimeConfig(llm_api_key="legacy-key", llm_base_url="https://legacy.example/v1",
        connection_profiles=[profile()], task_assignments={"writing": "subscription"})
    apply_agent_config(settings, config)
    resolved = settings_for_task(settings, "writing")
    assert resolved.llm_api_key == resolved.llm_base_url == ""
    assert resolved.llm_chatgpt_account_id == "account-1"
    assert resolved.model_execution["auth_mode"] == "chatgpt_plan"
    assert provider_ready(resolved)
    provider = create_llm_provider(resolved)
    assert isinstance(provider, ChatGPTPlanProvider) and provider._login_service is settings.chatgpt_login
    legacy = settings_for_task(settings, "discussion")
    assert legacy.llm_api_key == "legacy-key" and "auth_mode" not in legacy.model_execution
    assert provider_ready(legacy)
    # Converting a profile clears its former API key and never borrows the default key.
    old = AgentRuntimeConfig(connection_profiles=[{"id": "subscription", "name": "Old", "api_key": "old-key"}])
    changed = update_agent_config(old, AgentRuntimeConfigUpdate(connection_profiles=[profile()]))
    assert changed.connection_profiles[0].api_key == ""

@pytest.mark.parametrize("category,known", [("incomplete_response", True), ("unsupported_output", True),
    ("invalid_response", True), ("incomplete_response", False), ("plan_usage_limit", True)])
def test_plan_transport_failure_does_not_trigger_paid_command_format_correction(category, known):
    from storygraph.services.chatgpt_plan_provider import ChatGPTPlanError
    from tests.test_authoring_service import FakeProvider, make_service, finish
    provider = FakeProvider(ChatGPTPlanError(category, outcome_known=known), finish())
    service, session = make_service(provider)
    with pytest.raises(ProviderError):
        service.turn(project_id="project", session_id=session.id, expected_version=1,
                     message="继续讨论。", max_steps=3)
    assert len(provider.requests) == 1
    saved = service.get("project", session.id)
    assert saved.turn_calls_started == 1
    assert saved.turn_status == ("failed" if known else "unknown")
    assert not any(m.tool_name == "format_correction" for m in saved.messages)


def test_switch_to_plan_does_not_retain_vendor_thinking_options():
    old = AgentRuntimeConfig(connection_profiles=[{"id": "subscription", "name": "Old",
        "base_url": "https://api.deepseek.com/v1", "api_key": "old-key", "thinking_mode": "enabled", "reasoning_effort": "high"}])
    changed = update_agent_config(old, AgentRuntimeConfigUpdate(connection_profiles=[profile()]))
    current = changed.connection_profiles[0]
    assert current.thinking_mode == "provider_default" and current.reasoning_effort is None
    assert current.api_key == current.base_url == ""


@pytest.mark.parametrize("detail,category", [
    ({"code": None, "type": "invalid_request_error", "param": "input",
      "message": "Response input messages must contain the word 'json' in some form to use 'text.format' of type 'json_object'."}, "json_mode_input_required"),
    ({"code": "subscription_sharing_usage_limit_exceeded", "type": "invalid_request_error"}, "plan_usage_limit"),
    ({"type": "chatpass_v2_scope_not_authorized"}, "plan_permission_required"),
    ({"code": None, "type": "invalid_request_error", "message": "private synthetic-oauth-secret"}, "invalid_request"),
    ({"type": "server_error"}, "provider_unavailable"),
    ({"code": "unknown", "type": "unknown", "message": "private synthetic-oauth-secret"}, "request_failed"),
    ({"code": ["invalid_request_error"], "type": {"private": True}}, "request_failed"),
])
def test_stream_error_finite_safe_diagnostics(detail, category):
    calls = []
    with pytest.raises(ProviderError) as caught:
        fixture_provider(event("error", error=detail), calls).generate(payload())
    assert len(calls) == 1
    assert caught.value.category == category and caught.value.outcome_known
    assert caught.value.allow_format_retry is False
    assert "private" not in str(caught.value) and "synthetic-oauth-secret" not in str(caught.value)


def test_http400_unknown_error_remains_invalid_request():
    from storygraph.services.chatgpt_plan_provider import _plan_error
    exc = _plan_error({"error": {"code": "unknown", "message": "private"}}, status=400)
    assert exc.category == "invalid_request" and exc.status == 400
    assert "private" not in str(exc)


@pytest.mark.parametrize("overrides,category", [
    ({"param": "other"}, "invalid_request"),
    ({"message": "private synthetic-oauth-secret json text.format"}, "invalid_request"),
    ({"code": "subscription_sharing_usage_limit_exceeded"}, "plan_usage_limit"),
    ({"code": "chatpass_v2_scope_not_authorized"}, "plan_permission_required"),
])
def test_json_input_diagnostic_is_exact_and_never_overrides_plan_admission(overrides, category):
    from storygraph.services.chatgpt_plan_provider import _plan_error
    detail = {"code": None, "type": "invalid_request_error", "param": "input",
              "message": "Response input messages must contain the word 'json' in some form to use 'text.format' of type 'json_object'."}
    detail.update(overrides)
    exc = _plan_error({"error": detail})
    assert exc.category == category
    assert "synthetic-oauth-secret" not in str(exc)

@pytest.mark.parametrize(("status", "expected"), [(401, "invalid_credentials"), (429, "rate_limit"), (503, "provider_unavailable")])
def test_http_status_has_priority_over_generic_error_type(status, expected):
    from storygraph.services.chatgpt_plan_provider import _plan_error

    classified = _plan_error({"error": {"type":"invalid_request_error"}}, status=status)
    assert classified.category == expected and classified.status == status
