"""Short ephemeral aliases remain exact, collision-checked source selectors."""

import copy
import json

import pytest

from storygraph.models.generation_review import GenerationReviewReport
from storygraph.services.canon_snapshot import build_canon_snapshot
from storygraph.services.llm_provider import LLMResponse
from storygraph.services.semantic_review import (
    EvidenceSourceCollisionError, SemanticReviewService, build_evidence_sources,
    resolve_evidence_sources, review_is_current,
)
from test_semantic_review import graph as graph
from test_semantic_review import issue, payload, target


def inputs(graph):
    value = target()
    snapshot = build_canon_snapshot(graph, project_id="p", scene_id="s")
    registry, _ = build_evidence_sources(target=value, canon=snapshot, style_sources={})
    return value, snapshot, registry


def test_future_aliases_are_stable_sixteen_hex_with_original_exact_quotes(graph):
    value, snapshot, registry = inputs(graph)
    assert registry and all(key.startswith("ev_") and len(key) == 19 for key in registry)
    assert all(all(ch in "0123456789abcdef" for ch in key[3:]) for key in registry)
    assert registry == build_evidence_sources(target=value, canon=snapshot, style_sources={})[0]
    sources = {"target": {value.target_id: value.text}, "canon": {fact.id: fact.text for fact in snapshot.facts}}
    assert all(entry["quote"] in sources[entry["kind"]][entry["ref"]] for entry in registry.values())


@pytest.mark.parametrize("bad", ["missing_one", "unknown", "ev_8bfd6de5ec5c49e7882eda436c14de2", None])
def test_missing_unknown_and_old_malformed_ids_are_never_fuzzy_repaired(graph, bad):
    _, _, registry = inputs(graph)
    key = next(iter(registry))
    bad = key[:-1] if bad == "missing_one" else "ev_" + "f" * 16 if bad == "unknown" else bad
    original = payload([issue(evidence=[{"source_id": bad}])])
    saved = copy.deepcopy(original)
    with pytest.raises(ValueError, match="unknown_or_overridden"):
        resolve_evidence_sources(original, registry)
    assert original == saved


def test_different_sources_with_same_prefix_fail_closed_before_provider(graph, monkeypatch):
    import storygraph.services.semantic_review as module
    original_hash = module.content_hash
    def collide(value):
        digest = original_hash(value)
        return "0" * 16 + digest[16:] if value.startswith('["target"') or value.startswith('["canon"') else digest
    monkeypatch.setattr(module, "content_hash", collide)
    value = target()
    snapshot = build_canon_snapshot(graph, project_id="p", scene_id="s")
    with pytest.raises(EvidenceSourceCollisionError, match="evidence_source_id_collision"):
        build_evidence_sources(target=value, canon=snapshot, style_sources={})
    class NeverCalled:
        def generate(self, _):
            pytest.fail("Alias collision must fail before provider invocation")
    report = SemanticReviewService(NeverCalled(), "fixture").review(target=value, canon=snapshot)
    assert report.status == "inconclusive" and not report.issues
    assert "semantic_review_evidence_collision" in report.coverage.limitations
    assert report.model_execution is None and report.coverage.method == "deterministic_only"


def test_valid_exact_legacy_quote_form_does_not_require_an_alias(graph):
    value, _, registry = inputs(graph)
    quote = value.text[:10]
    raw = payload([issue(evidence=[{"kind": "target", "ref": value.target_id, "quote": quote}])])
    assert resolve_evidence_sources(raw, registry) == raw


def test_old_canonical_report_remains_current_after_ephemeral_alias_change(graph, monkeypatch):
    import storygraph.services.semantic_review as module
    value, snapshot, _ = inputs(graph)
    class ExactAliases:
        def generate(self, request):
            registry = json.loads(request.messages[-1].content)["evidence_sources"]
            first = next(key for key, entry in registry.items() if entry["kind"] == "target")
            second = next(key for key, entry in registry.items() if entry["kind"] == "canon" and entry["ref"] == "secret")
            return LLMResponse(json.dumps(payload([issue(evidence=[{"source_id": first}, {"source_id": second}])]), ensure_ascii=False))
    monkeypatch.setattr(module, "EVIDENCE_SOURCE_HEX_CHARS", 32)
    old = SemanticReviewService(ExactAliases(), "fixture").review(target=value, canon=snapshot)
    assert old.status == "needs_revision"
    saved = old.model_dump_json()
    monkeypatch.setattr(module, "EVIDENCE_SOURCE_HEX_CHARS", 16)
    assert all(len(key) == 19 for key in build_evidence_sources(target=value, canon=snapshot, style_sources={})[0])
    reloaded = GenerationReviewReport.model_validate_json(saved)
    assert review_is_current(reloaded, target=value, canon=snapshot)
    assert all(set(evidence.model_dump()) == {"kind", "ref", "quote"} for evidence in reloaded.issues[0].evidence)
    assert reloaded.model_dump_json() == saved
