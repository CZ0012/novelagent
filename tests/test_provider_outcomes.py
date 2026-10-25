"""Safe transport outcome classification and explicit critic retry authorization."""

from http.client import IncompleteRead
import io
import json
from urllib import error, request

import pytest

from storygraph.core.errors import GraphStoreError
from storygraph.models.planning_run import PlanningRunResume
from storygraph.services.llm_provider import (
    AnthropicMessagesProvider, LLMMessage, LLMRequest, OpenAICompatibleProvider, ProviderError, ResponsesProvider,
)
from test_planning_run import setup as setup
from test_planning_run import create


def provider(cls=OpenAICompatibleProvider):
    return cls(base_url="https://gateway.example/v1", api_key="synthetic-private-key", model="fixture")


def payload():
    return LLMRequest(model="fixture", messages=[LLMMessage("user", "JSON")])


class Response:
    def __init__(self, body):
        self.body = body
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return None
    def read(self):
        return self.body


@pytest.mark.parametrize("cls", [OpenAICompatibleProvider, ResponsesProvider, AnthropicMessagesProvider])
@pytest.mark.parametrize("failure", [TimeoutError("PRIVATE transport text"), error.URLError("PRIVATE address"),
                                      IncompleteRead(b"PRIVATE partial body", 50)])
def test_unknown_transport_is_safe_runtime_error_and_never_retried(monkeypatch, cls, failure):
    calls = []
    def fail(req, timeout):
        calls.append(req)
        raise failure
    monkeypatch.setattr(request, "urlopen", fail)
    with pytest.raises(ProviderError) as caught:
        provider(cls).generate(payload())
    exc = caught.value
    assert isinstance(exc, RuntimeError) and not exc.outcome_known and exc.status is None
    assert exc.category == "connection_error" and "PRIVATE" not in str(exc)
    assert "synthetic-private-key" not in str(exc) and len(calls) == 1


@pytest.mark.parametrize("cls", [OpenAICompatibleProvider, ResponsesProvider, AnthropicMessagesProvider])
def test_http_response_is_known_without_exposing_reason_body_or_credentials(monkeypatch, cls):
    def fail(req, timeout):
        raise error.HTTPError(req.full_url, 429, "PRIVATE reason", {}, io.BytesIO(b"PRIVATE body synthetic-private-key"))
    monkeypatch.setattr(request, "urlopen", fail)
    with pytest.raises(ProviderError) as caught:
        provider(cls).generate(payload())
    assert caught.value.outcome_known and caught.value.status == 429
    assert caught.value.category == "rate_limit" and "PRIVATE" not in str(caught.value)


@pytest.mark.parametrize("body", [None, b"not JSON PRIVATE", b"\xff", b'{"choices":[]}',
    json.dumps({"choices": [{"finish_reason": "length", "message": {"content": "PRIVATE partial", "reasoning_content": "PRIVATE reasoning"}}]}).encode()])
def test_completed_invalid_or_length_limited_response_has_known_outcome(monkeypatch, body):
    monkeypatch.setattr(request, "urlopen", lambda *_a, **_k: Response(body))
    with pytest.raises(ProviderError) as caught:
        provider().generate(payload())
    assert caught.value.outcome_known and "PRIVATE" not in str(caught.value)


@pytest.mark.parametrize("failure", [TimeoutError("PRIVATE timeout"), ConnectionError("PRIVATE connection")])
def test_critic_unknown_preserves_reservation_and_requires_explicit_retry_flag(setup, failure):
    graph, _, runs, writer, reviewer, service, _ = setup
    run = create(setup)
    original = reviewer.generate
    def fail(req):
        reviewer.requests.append(req)
        raise failure
    reviewer.generate = fail
    paused = service.execute(run.id)
    assert paused.status == "paused" and paused.pause_reason == "uncertain_call"
    assert paused.pending_call.task == "continuity" and paused.pending_call.operation == "review"
    assert paused.calls_reserved == 2 and len(writer.calls) == len(reviewer.requests) == 1
    diagnostic_id = paused.steps[0].review_id
    diagnostic = runs.report(run.id, diagnostic_id)
    assert diagnostic.status == "inconclusive"
    assert "semantic_review_provider_outcome_unknown" in diagnostic.coverage.limitations
    assert "PRIVATE" not in diagnostic.model_dump_json() and "PRIVATE" not in paused.model_dump_json()
    assert service.execute(run.id).pending_call == paused.pending_call
    for extra in ({}, {"recheck_current_step": True}):
        with pytest.raises(GraphStoreError):
            service.resume("book", run.id, PlanningRunResume(expected_version=paused.version, **extra))
    assert len(writer.calls) == len(reviewer.requests) == 1
    reviewer.generate = original
    resumed = service.resume("book", run.id,
        PlanningRunResume(expected_version=paused.version, retry_uncertain_call=True))
    result = service.execute(resumed.id)
    assert result.status == "awaiting_review" and result.calls_reserved == 12
    assert len(writer.calls) == 5 and len(reviewer.requests) == 7
    assert runs.report(run.id, diagnostic_id).status == "inconclusive"
    assert len(graph.nodes) == 1


def test_known_truncated_critic_is_recheckable_without_unknown_call_retry(setup):
    _, _, runs, writer, reviewer, service, _ = setup
    run = create(setup)
    original = reviewer.generate
    def length(req):
        reviewer.requests.append(req)
        raise ProviderError("incomplete_response", outcome_known=True)
    reviewer.generate = length
    paused = service.execute(run.id)
    assert paused.pause_reason == "review_failed" and paused.pending_call is None
    diagnostic = runs.report(run.id, paused.steps[0].review_id)
    assert "semantic_review_provider_outcome_known" in diagnostic.coverage.limitations
    assert "semantic_review_provider_outcome_unknown" not in diagnostic.coverage.limitations
    reviewer.generate = original
    queued = service.resume("book", run.id,
        PlanningRunResume(expected_version=paused.version, recheck_current_step=True))
    result = service.execute(queued.id)
    assert result.status == "awaiting_review" and len(writer.calls) == 5


def test_final_book_critic_unknown_retries_only_final_pass_after_explicit_authorization(setup):
    _, _, _, writer, reviewer, service, _ = setup
    original = reviewer.generate
    def fail_final(req):
        data = json.loads(req.messages[-1].content)
        if data["target"]["target_id"].startswith("book_review_"):
            reviewer.requests.append(req)
            raise TimeoutError("PRIVATE final review timeout")
        return original(req)
    reviewer.generate = fail_final
    paused = service.execute(create(setup).id)
    assert paused.pause_reason == "uncertain_call" and paused.stage == "book_review"
    assert paused.pending_call.operation == "book_review" and paused.final_review_id is not None
    assert all(step.status == "passed" for step in paused.steps)
    with pytest.raises(GraphStoreError):
        service.resume("book", paused.id, PlanningRunResume(expected_version=paused.version))
    reviewer.generate = original
    queued = service.resume("book", paused.id,
        PlanningRunResume(expected_version=paused.version, retry_uncertain_call=True))
    assert queued.final_review_id is None
    result = service.execute(queued.id)
    assert result.status == "awaiting_review" and len(writer.calls) == 5 and len(reviewer.requests) == 7


def test_generator_known_http_error_does_not_pretend_call_is_still_inflight(setup):
    _, _, _, writer, _, service, _ = setup
    def known(_):
        raise ProviderError("rate_limit", outcome_known=True, status=429)
    writer.generate = known
    paused = service.execute(create(setup).id)
    assert paused.status == "paused" and paused.pause_reason == "execution_failed"
    assert paused.pending_call is None and paused.calls_reserved == 1
