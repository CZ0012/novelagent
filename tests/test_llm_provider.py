import json
from urllib import request

from storygraph.services.llm_provider import LLMMessage, LLMRequest, OpenAICompatibleProvider


def test_openai_compatible_provider_posts_chat_completions(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def read(self):
            return json.dumps(
                {"choices": [{"message": {"content": "{\"text\":\"ok\"}"}}]}
            ).encode("utf-8")

    def fake_urlopen(http_request, timeout):
        captured["url"] = http_request.full_url
        captured["timeout"] = timeout
        captured["headers"] = dict(http_request.header_items())
        captured["body"] = json.loads(http_request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr(request, "urlopen", fake_urlopen)
    provider = OpenAICompatibleProvider(
        base_url="https://third-party.example/v1",
        api_key="secret",
        model="deepseek-chat",
        timeout_seconds=12,
    )

    response = provider.generate(
        LLMRequest(
            model="deepseek-chat",
            messages=[LLMMessage(role="user", content="hello")],
        )
    )

    assert captured["url"] == "https://third-party.example/v1/chat/completions"
    assert captured["timeout"] == 12
    assert captured["headers"]["Authorization"] == "Bearer secret"
    assert captured["body"]["model"] == "deepseek-chat"
    assert captured["body"]["messages"] == [{"role": "user", "content": "hello"}]
    assert captured["body"]["max_tokens"] == 2048
    assert captured["body"]["response_format"] == {"type": "json_object"}
    assert response.content == "{\"text\":\"ok\"}"
