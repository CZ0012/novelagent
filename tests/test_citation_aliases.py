"""Request-local compact handles retain exact source and invocation binding."""

import copy
import json

import pytest

from storygraph.models.generation_review import GenerationReviewReport
from storygraph.services.canon_snapshot import build_canon_snapshot
from storygraph.services.llm_provider import LLMResponse
from storygraph.services.semantic_review import (
    SemanticReviewService, build_evidence_sources,
    resolve_evidence_sources, review_is_current,
)
from test_semantic_review import graph as graph
from test_semantic_review import issue, payload, target


def inputs(graph):
    value = target()
    snapshot = build_canon_snapshot(graph, project_id="p", scene_id="s")
    registry, _ = build_evidence_sources(target=value, canon=snapshot, style_sources={})
    return value, snapshot, registry


def test_compact_handles_are_request_local_and_exact(graph):
    value, snapshot, registry = inputs(graph)
    assert list(registry) == [f"E{i}" for i in range(1, len(registry)+1)]
    assert registry == build_evidence_sources(target=value, canon=snapshot, style_sources={})[0]
    sources = {"target": {value.target_id: value.text}, "canon": {fact.id: fact.text for fact in snapshot.facts}}
    assert all(entry["quote"] in sources[entry["kind"]][entry["ref"]] for entry in registry.values())


@pytest.mark.parametrize("bad", ["E", "e1", "E01", "E99999", "ev_9c53", None])
def test_missing_unknown_and_old_malformed_ids_are_never_fuzzy_repaired(graph, bad):
    _, _, registry = inputs(graph)
    raw = payload([issue(evidence=[{"source_id": bad}])], evidence_registry_id="request-a")
    saved = copy.deepcopy(raw)
    with pytest.raises(ValueError, match="unknown_or_overridden"):
        resolve_evidence_sources(raw, registry, registry_id="request-a")
    assert raw == saved


@pytest.mark.parametrize("supplied", [None, "request-old", 1])
def test_compact_aliases_require_exact_request_instance_token(graph, supplied):
    _, _, registry = inputs(graph)
    raw = payload([issue(evidence=[{"source_id": "E1"}])])
    if supplied is not None:
        raw["evidence_registry_id"] = supplied
    with pytest.raises(ValueError, match="invalid_evidence_registry_id"):
        resolve_evidence_sources(raw, registry, registry_id="request-new")


def test_mixed_canonical_alias_evidence_and_override_rejection(graph):
    value, _, registry = inputs(graph)
    direct = {"kind": "target", "ref": value.target_id, "quote": value.text[:10]}
    raw = payload([issue(evidence=[direct, {"source_id": "E1"}])], evidence_registry_id="request-a")
    resolved = resolve_evidence_sources(raw, registry, registry_id="request-a")
    assert "evidence_registry_id" not in resolved
    assert resolved["issues"][0]["evidence"][0] == direct
    raw["issues"][0]["evidence"][1]["quote"] = "override"
    with pytest.raises(ValueError, match="unknown_or_overridden"):
        resolve_evidence_sources(raw, registry, registry_id="request-a")


def test_valid_exact_legacy_quote_form_does_not_require_an_alias(graph):
    value, _, registry = inputs(graph)
    quote = value.text[:10]
    raw = payload([issue(evidence=[{"kind": "target", "ref": value.target_id, "quote": quote}])])
    assert resolve_evidence_sources(raw, registry) == raw


def test_canonical_report_stays_current_independently_of_ephemeral_registry(graph):
    value, snapshot, _ = inputs(graph)
    class CanonicalLegacy:
        def generate(self, request):
            return LLMResponse(json.dumps(payload([issue()]), ensure_ascii=False))
    old = SemanticReviewService(CanonicalLegacy(), "fixture").review(target=value, canon=snapshot)
    assert old.status == "needs_revision"
    saved = old.model_dump_json()

    assert list(build_evidence_sources(target=value, canon=snapshot, style_sources={})[0])[0] == "E1"
    reloaded = GenerationReviewReport.model_validate_json(saved)
    assert review_is_current(reloaded, target=value, canon=snapshot)
    assert all(set(evidence.model_dump()) == {"kind", "ref", "quote"} for evidence in reloaded.issues[0].evidence)
    assert reloaded.model_dump_json() == saved


@pytest.mark.parametrize("changed", [False, True])
def test_stale_response_cannot_select_new_registry_even_for_same_target(graph, changed):
    value, snapshot, _ = inputs(graph)
    class Stale:
        previous = None
        def generate(self, request):
            sent = json.loads(request.messages[-1].content)
            if self.previous is None:
                self.previous = payload([issue(finding="advice", severity="low", evidence=[{"source_id": "E1"}])],
                    evidence_registry_id=sent["evidence_registry_id"])
            return LLMResponse(json.dumps(self.previous, ensure_ascii=False))
    service = SemanticReviewService(Stale(), "fixture")
    assert service.review(target=value, canon=snapshot).status == "pass"
    if changed:
        value = value.model_copy(update={"text": value.text+"extra"})
    result = service.review(target=value, canon=snapshot)
    assert result.status == "inconclusive" and not result.issues
    assert "semantic_review_invalid_output" in result.coverage.limitations


@pytest.mark.parametrize("token", [None, 1, "old-request"])
def test_supplied_invalid_token_rejected_even_with_canonical_only_evidence(graph, token):
    _, _, registry = inputs(graph)
    raw = payload([issue()], evidence_registry_id=token)
    with pytest.raises(ValueError, match="invalid_evidence_registry_id"):
        resolve_evidence_sources(raw, registry, registry_id="current-request")
