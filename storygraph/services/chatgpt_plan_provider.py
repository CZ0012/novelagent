"""Official ChatGPT plan transport. OAuth tokens never enter API-key configuration."""
from __future__ import annotations

import json
from http.client import HTTPException
from urllib import error, request

from storygraph.services.llm_provider import (
    LLMRequest, LLMResponse, ProviderError, _enable_responses_json_object, _http_error_guidance, _reject_extra,
)

MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_EVENT_BYTES = 1024 * 1024
PLAN_ERROR_CODES = {
    "subscription_sharing_user_not_eligible": "plan_not_eligible",
    "subscription_sharing_usage_limit_exceeded": "plan_usage_limit",
    "subscription_sharing_usage_unavailable": "plan_usage_unavailable",
    "subscription_sharing_unsupported_capability": "invalid_request",
    "subscription_sharing_route_not_supported": "invalid_request",
    "subscription_sharing_invalid_user": "invalid_credentials",
    "chatpass_v2_scope_not_authorized": "plan_permission_required",
    "chatpass_v2_invalid_authorization_context": "plan_permission_required",
    "subscription_sharing_user_unavailable": "provider_unavailable",
}


class ChatGPTPlanError(ProviderError):
    """A plan transport outcome cannot authorize an upper-layer paid format retry."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.allow_format_retry = False


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _plan_error(payload, *, status=None):
    detail = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(detail, dict):
        detail = payload if isinstance(payload, dict) else {}
    # Read only finite, known diagnostics. Never retain or display provider text.
    values = [detail.get("code"), detail.get("type")]
    category = next((PLAN_ERROR_CODES[value] for value in values
                     if isinstance(value, str) and value in PLAN_ERROR_CODES), None)
    if category is None:
        if ("invalid_request_error" in values and detail.get("param") == "input"
                and detail.get("message") == "Response input messages must contain the word 'json' in some form to use 'text.format' of type 'json_object'."):
            category = "json_mode_input_required"
        elif status is None:
            # A stream may have no admission status. For an HTTP rejection keep
            # the authoritative status (e.g. 401 or 429) over a generic error type.
            generic = {"invalid_request_error": "invalid_request",
                       "server_error": "provider_unavailable"}
            category = next((generic[value] for value in values
                             if isinstance(value, str) and value in generic), None)
    if category is None:
        category = _http_error_guidance(status)[0] if status else "request_failed"
    return ChatGPTPlanError(category, outcome_known=True, status=status)


class ChatGPTPlanProvider:
    """One request, official endpoint, bounded SSE; no retry or billing fallback."""
    protocol = "responses"
    base_url = "https://api.openai.com/v1"

    def __init__(self, *, model: str, account_id=None, timeout_seconds=60.0,
                 json_mode=True, login_service=None, opener=None):
        self.model = model
        self.account_id = account_id
        self.timeout_seconds = timeout_seconds
        self.json_mode = json_mode
        self._login_service = login_service
        self._opener = opener or request.build_opener(_NoRedirect()).open

    def _token(self):
        from storygraph.services.chatgpt_login import get_default_chatgpt_login_service, ChatGPTLoginError
        service = self._login_service or get_default_chatgpt_login_service()
        try:
            return service.access_token(self.account_id)
        except ChatGPTLoginError as exc:
            category = "provider_unavailable" if exc.category in {
                "connection_error", "refresh_not_yet_available", "provider_unavailable"
            } else "plan_permission_required"
            # Refresh failed before inference was dispatched, so no model usage is uncertain.
            raise ChatGPTPlanError(category, outcome_known=True) from None

    def _open(self, http_request):
        try:
            return self._opener(http_request, timeout=self.timeout_seconds)
        except error.HTTPError as exc:
            try:
                body = exc.read(MAX_EVENT_BYTES + 1)
                parsed = json.loads(body) if len(body) <= MAX_EVENT_BYTES else {}
            except (ValueError, OSError, HTTPException):
                parsed = {}
            finally:
                exc.close()
            raise _plan_error(parsed, status=exc.code) from None
        except (error.URLError, TimeoutError, OSError, ValueError, HTTPException):
            raise ChatGPTPlanError("connection_error", outcome_known=False) from None

    def list_models(self):
        token = self._token()
        req = request.Request(self.base_url + "/models", headers={
            "Authorization": "Bearer " + token, "Accept": "application/json"})
        try:
            with self._open(req) as response:
                data = response.read(MAX_RESPONSE_BYTES + 1)
            if len(data) > MAX_RESPONSE_BYTES:
                raise ValueError()
            parsed = json.loads(data)
            models = parsed["models"]
            if not isinstance(models, list) or len(models) > 1000:
                raise ValueError()
            result = []
            for item in models:
                if not isinstance(item, dict):
                    raise ValueError()
                if item.get("visibility") != "list":
                    continue
                slug, name = item.get("slug"), item.get("display_name")
                if not all(isinstance(v, str) and 0 < len(v) <= 200 and token not in v
                           and not any(ord(c) < 32 for c in v) for v in (slug, name)):
                    raise ValueError()
                result.append({"id": slug, "display_name": name})
            return result
        except ProviderError:
            raise
        except (error.URLError, TimeoutError, OSError, HTTPException):
            raise ChatGPTPlanError("connection_error", outcome_known=False) from None
        except (ValueError, KeyError, TypeError):
            raise ChatGPTPlanError("invalid_response", outcome_known=True) from None

    def generate(self, request_payload: LLMRequest) -> LLMResponse:
        _reject_extra(request_payload)
        if not (request_payload.model or self.model):
            raise ValueError("model is required")
        # Preview forbids temperature and max_output_tokens, including defaults.
        payload = {
            "model": request_payload.model or self.model,
            "instructions": "\n\n".join(m.content for m in request_payload.messages
                                         if m.role in {"system", "developer"}),
            "input": [{"role": m.role, "content": m.content}
                      for m in request_payload.messages if m.role not in {"system", "developer"}],
            "store": False, "stream": True,
        }
        if self.json_mode and request_payload.response_format == "json_object":
            _enable_responses_json_object(payload)
        token = self._token()
        req = request.Request(self.base_url + "/responses", data=json.dumps(payload).encode(),
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json",
                     "Accept": "text/event-stream"}, method="POST")
        total = 0
        event_size = 0
        data_lines = []
        deltas = []
        completed = None
        try:
            with self._open(req) as response:
                while True:
                    line = response.readline(MAX_EVENT_BYTES + 1)
                    if not line:
                        break
                    total += len(line)
                    event_size += len(line)
                    if total > MAX_RESPONSE_BYTES or event_size > MAX_EVENT_BYTES:
                        raise ChatGPTPlanError("invalid_response", outcome_known=False)
                    line = line.decode("utf-8").rstrip("\r\n")
                    if line:
                        if line.startswith("data:"):
                            data_lines.append(line[5:].lstrip(" "))
                        continue
                    event_size = 0
                    if not data_lines:
                        continue
                    data = "\n".join(data_lines)
                    data_lines = []
                    if data == "[DONE]":
                        break
                    event = json.loads(data)
                    if not isinstance(event, dict):
                        raise ValueError()
                    kind = event.get("type")
                    if kind in {"response.failed", "error"}:
                        detail = event.get("response", event)
                        raise _plan_error(detail)
                    if kind == "response.incomplete":
                        raise ChatGPTPlanError("incomplete_response", outcome_known=True)
                    if kind in {"response.refusal.delta", "response.refusal.done"}:
                        raise ChatGPTPlanError("unsupported_output", outcome_known=True)
                    if kind == "response.output_text.delta":
                        delta = event.get("delta")
                        if not isinstance(delta, str):
                            raise ValueError()
                        deltas.append(delta)
                    if kind == "response.completed":
                        completed = event.get("response")
                        break
        except ProviderError:
            raise
        except (error.URLError, TimeoutError, OSError, HTTPException):
            raise ChatGPTPlanError("connection_error", outcome_known=False) from None
        except (ValueError, TypeError, UnicodeError):
            raise ChatGPTPlanError("invalid_response", outcome_known=False) from None
        if not isinstance(completed, dict) or completed.get("status") != "completed":
            raise ChatGPTPlanError("incomplete_response", outcome_known=False)
        if completed.get("error"):
            raise _plan_error(completed)
        output = completed.get("output")
        if not isinstance(output, list):
            raise ChatGPTPlanError("invalid_response", outcome_known=True)
        texts = []
        for item in output:
            if isinstance(item, dict) and item.get("type") == "reasoning":
                continue
            if not isinstance(item, dict) or item.get("type") != "message" or item.get("role") != "assistant" or item.get("status", "completed") != "completed":
                raise ChatGPTPlanError("unsupported_output", outcome_known=True)
            blocks = item.get("content")
            if not isinstance(blocks, list):
                raise ChatGPTPlanError("invalid_response", outcome_known=True)
            for block in blocks:
                if not isinstance(block, dict) or block.get("type") != "output_text" or not isinstance(block.get("text"), str):
                    raise ChatGPTPlanError("unsupported_output", outcome_known=True)
                texts.append(block["text"])
        content = "".join(texts)
        if not content.strip():
            raise ChatGPTPlanError("invalid_response", outcome_known=True)
        if deltas and "".join(deltas) != content:
            raise ChatGPTPlanError("invalid_response", outcome_known=True)
        return LLMResponse(content=content)
