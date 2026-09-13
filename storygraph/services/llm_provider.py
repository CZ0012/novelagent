"""LLM provider interfaces and OpenAI-compatible HTTP client."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Protocol
from urllib import error, request


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
        payload.update(request_payload.extra)
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
        try:
            content = parsed["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("LLM provider response did not include choices[0].message.content") from exc
        if not isinstance(content, str):
            raise RuntimeError("LLM provider content must be a string")
        return LLMResponse(content=content, raw=parsed)

    def list_models(self) -> list[dict[str, str]]:
        base = self.base_url.removesuffix("/chat/completions")
        http_request = request.Request(
            f"{base}/models",
            headers={"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"},
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
        except (error.URLError, TimeoutError, OSError):
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

    def _chat_completions_url(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"


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
