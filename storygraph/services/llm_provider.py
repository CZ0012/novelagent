"""LLM provider interfaces and OpenAI-compatible HTTP client."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Protocol
from urllib import error, request
from urllib.parse import urlsplit


@dataclass(frozen=True)
class LLMMessage:
    role: str
    content: str


@dataclass(frozen=True)
class LLMRequest:
    messages: list[LLMMessage]
    model: str
    temperature: float = 0.2
    max_tokens: int | None = 2048
    response_format: str | None = "json_object"
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResponse:
    content: str
    raw: dict[str, Any] = field(default_factory=dict)


class LLMProvider(Protocol):
    def generate(self, request: LLMRequest) -> LLMResponse:
        ...


class OpenAICompatibleProvider:
    """Small Chat Completions client for third-party OpenAI-compatible APIs."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 60.0,
        json_mode: bool = True,
    ) -> None:
        try:
            parsed_url = urlsplit(base_url)
        except ValueError:
            raise ValueError("Invalid provider HTTP(S) address") from None
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc or parsed_url.username or parsed_url.password or parsed_url.query or parsed_url.fragment:
            raise ValueError("Provider address must be an HTTP(S) URL without credentials, query or fragment")
        if not base_url:
            raise ValueError("base_url is required")
        if not api_key:
            raise ValueError("api_key is required")
        if not model:
            raise ValueError("model is required")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.json_mode = json_mode

    def generate(self, request_payload: LLMRequest) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": request_payload.model or self.model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in request_payload.messages
            ],
            "temperature": request_payload.temperature,
        }
        if request_payload.max_tokens is not None:
            payload["max_tokens"] = request_payload.max_tokens
        _reject_extra(request_payload)
        if self.json_mode and request_payload.response_format == "json_object":
            payload["response_format"] = {"type": "json_object"}

        body = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            self._chat_completions_url(),
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        parsed = self._read_json_response(http_request)
        if not isinstance(parsed, dict) or parsed.get("error"):
            raise _invalid_response()
        try:
            choice = parsed["choices"][0]
            if not isinstance(choice, dict) or not isinstance(choice.get("message"), dict):
                raise _invalid_response()
            if choice.get("finish_reason") not in (None, "stop"):
                raise _invalid_response("incomplete_response")
            if choice["message"].get("refusal") or choice["message"].get("tool_calls"):
                raise _invalid_response("unsupported_output")
            content = parsed["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("LLM provider response did not include choices[0].message.content") from exc
        if not isinstance(content, str):
            raise RuntimeError("LLM provider content must be a string")
        if not content.strip():
            raise _invalid_response()
        return LLMResponse(content=content, raw=_safe_response_metadata(parsed, self.api_key))

    def list_models(self) -> list[dict[str, str]]:
        base = _protocol_base(self.base_url)
        http_request = request.Request(
            f"{base}/models",
            headers={**self._auth_headers(), "Accept": "application/json"},
            method="GET",
        )
        parsed = self._read_json_response(http_request)
        if not isinstance(parsed, dict) or not isinstance(parsed.get("data"), list):
            raise RuntimeError("LLM provider [invalid_response]: Model listing is unsupported.")
        identifiers = {
            item["id"] for item in parsed["data"]
            if isinstance(item, dict) and isinstance(item.get("id"), str)
            and 0 < len(item["id"]) <= 200 and not any(ord(c) < 32 for c in item["id"])
            and self.api_key not in item["id"]
        }
        if len(identifiers) > 1000:
            raise RuntimeError("LLM provider [invalid_response]: Model listing exceeds 1000 entries.")
        return [{"id": identifier} for identifier in sorted(identifiers)]

    def _read_json_response(self, http_request: request.Request) -> Any:
        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            # Provider bodies and error reasons may echo credentials or private prose.
            category, guidance = _http_error_guidance(exc.code)
            exc.close()
            raise RuntimeError(
                f"LLM provider HTTP {exc.code} [{category}]: {guidance}"
            ) from None
        except (error.URLError, TimeoutError, OSError, ValueError):
            raise RuntimeError(
                "LLM provider [connection_error]: Check the provider address, network, "
                "and timeout settings, then retry."
            ) from None
        except UnicodeError:
            raise RuntimeError("LLM provider [invalid_response]: Response is not valid UTF-8.") from None

        try:
            parsed = json.loads(response_body)
        except json.JSONDecodeError:
            raise RuntimeError("LLM provider [invalid_response]: Response is not valid JSON.") from None
        return parsed

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def _chat_completions_url(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{_protocol_base(self.base_url)}/chat/completions"


def _http_error_guidance(status: int) -> tuple[str, str]:
    if status in {401, 403}:
        return "invalid_credentials", "Check your provider API key and model access."
    if status == 429:
        return "rate_limit", "Check provider quota or wait before retrying."
    if status == 404:
        return "endpoint_not_found", "Check the provider base URL and configured model identifier."
    if status in {400, 413, 422}:
        return "invalid_request", "Check model support, JSON mode, and the selected context size."
    if status >= 500:
        return "provider_unavailable", "The provider is unavailable; retry later."
    return "request_failed", "Check provider settings and retry."


def _protocol_base(url: str) -> str:
    for suffix in ("/chat/completions", "/responses", "/messages"):
        if url.endswith(suffix):
            return url[:-len(suffix)]
    return url


def _invalid_response(category="invalid_response") -> RuntimeError:
    return RuntimeError(f"LLM provider [{category}]: The provider did not return complete supported text.")


def _reject_extra(payload: LLMRequest) -> None:
    if payload.extra:
        raise ValueError("Custom provider request fields are unsupported")


def _safe_response_metadata(parsed: dict, secret: str) -> dict:
    # No provider payload, hidden thinking, tool arguments or echoed credentials escape.
    model = parsed.get("model")
    return {"model": model} if isinstance(model, str) and len(model) <= 200 and secret not in model else {}


class ResponsesProvider(OpenAICompatibleProvider):
    """Responses text transport. No implicit tools, history storage, polling or retries."""

    def generate(self, request_payload: LLMRequest) -> LLMResponse:
        _reject_extra(request_payload)
        payload = {
            "model": request_payload.model or self.model,
            "instructions": "\n\n".join(m.content for m in request_payload.messages if m.role in {"system", "developer"}),
            "input": [{"role": m.role, "content": m.content} for m in request_payload.messages if m.role not in {"system", "developer"}],
            "temperature": request_payload.temperature,
            "store": False,
        }
        if request_payload.max_tokens is not None:
            payload["max_output_tokens"] = request_payload.max_tokens
        if self.json_mode and request_payload.response_format == "json_object":
            payload["text"] = {"format": {"type": "json_object"}}
        http_request = request.Request(f"{_protocol_base(self.base_url)}/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={**self._auth_headers(), "Content-Type": "application/json"}, method="POST")
        parsed = self._read_json_response(http_request)
        if not isinstance(parsed, dict) or parsed.get("error") or parsed.get("status") != "completed":
            raise _invalid_response("incomplete_response")
        output = parsed.get("output")
        if not isinstance(output, list):
            raise _invalid_response()
        texts = []
        for item in output:
            if not isinstance(item, dict):
                raise _invalid_response()
            if item.get("type") == "reasoning":
                continue
            if item.get("type") != "message" or item.get("role") != "assistant" or item.get("status", "completed") != "completed":
                raise _invalid_response("unsupported_output")
            blocks = item.get("content")
            if not isinstance(blocks, list):
                raise _invalid_response()
            for block in blocks:
                if not isinstance(block, dict) or block.get("type") != "output_text" or not isinstance(block.get("text"), str):
                    raise _invalid_response("unsupported_output")
                texts.append(block["text"])
        content = "".join(texts)
        if not content.strip():
            raise _invalid_response()
        return LLMResponse(content=content, raw=_safe_response_metadata(parsed, self.api_key))


class AnthropicMessagesProvider(OpenAICompatibleProvider):
    """Anthropic Messages transport for providers explicitly exposing that protocol."""

    def _auth_headers(self) -> dict[str, str]:
        return {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"}

    def generate(self, request_payload: LLMRequest) -> LLMResponse:
        _reject_extra(request_payload)
        payload = {
            "model": request_payload.model or self.model,
            "system": "\n\n".join(m.content for m in request_payload.messages if m.role in {"system", "developer"}),
            "messages": [{"role": m.role, "content": m.content} for m in request_payload.messages if m.role not in {"system", "developer"}],
            "max_tokens": request_payload.max_tokens or 2048,
            "temperature": request_payload.temperature,
        }
        if any(m["role"] not in {"user", "assistant"} for m in payload["messages"]):
            raise ValueError("Unsupported message role")
        http_request = request.Request(f"{_protocol_base(self.base_url)}/messages",
            data=json.dumps(payload).encode("utf-8"),
            headers={**self._auth_headers(), "Content-Type": "application/json"}, method="POST")
        parsed = self._read_json_response(http_request)
        if not isinstance(parsed, dict) or parsed.get("type") != "message" or parsed.get("role") != "assistant":
            raise _invalid_response()
        if parsed.get("stop_reason") not in ("end_turn", "stop_sequence"):
            raise _invalid_response("incomplete_response")
        blocks = parsed.get("content")
        if not isinstance(blocks, list):
            raise _invalid_response()
        texts = []
        for block in blocks:
            if not isinstance(block, dict):
                raise _invalid_response()
            if block.get("type") in ("thinking", "redacted_thinking"):
                continue
            if block.get("type") != "text" or not isinstance(block.get("text"), str):
                raise _invalid_response("unsupported_output")
            texts.append(block["text"])
        content = "".join(texts)
        if not content.strip():
            raise _invalid_response()
        return LLMResponse(content=content, raw=_safe_response_metadata(parsed, self.api_key))
