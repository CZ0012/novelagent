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
        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            raise RuntimeError(f"LLM provider request failed with HTTP {exc.code}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"LLM provider request failed: {exc.reason}") from exc

        parsed = json.loads(response_body)
        try:
            content = parsed["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("LLM provider response did not include choices[0].message.content") from exc
        if not isinstance(content, str):
            raise RuntimeError("LLM provider content must be a string")
        return LLMResponse(content=content, raw=parsed)

    def _chat_completions_url(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"
