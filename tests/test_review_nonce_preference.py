"""New replies prefer a tail nonce; legacy runtime acceptance and hashes do not change."""
import json
from storygraph.services.semantic_review import SemanticReviewService, resolve_evidence_sources, review_is_current, style_fingerprint
from storygraph.services.canon_snapshot import canonical_json, content_hash
from storygraph.services.llm_provider import LLMResponse
from test_semantic_review import payload
from test_semantic_review_wire import target, canon


def test_preferred_nonce_is_required_even_without_aliases_but_legacy_parser_and_freshness_stay_valid():
    from storygraph.services.semantic_review import semantic_review_output_schema
    from storygraph.models.generation_review import SemanticReviewOutput
    raw = payload()
    assert resolve_evidence_sources(raw, {}, registry_id="current") == raw
    assert SemanticReviewOutput.model_validate(raw)
    preferred = semantic_review_output_schema(registry={}, registry_id="current")
    assert "evidence_registry_id" in preferred["required"]
    class Legacy:
        def generate(self, request):
            return LLMResponse(json.dumps(raw, ensure_ascii=False))
    value, snapshot = target(), canon()
    report = SemanticReviewService(Legacy(), "fixture").review(target=value, canon=snapshot)
    assert report.status == "pass" and review_is_current(report, target=value, canon=snapshot)
    assert report.target_text_sha256 == content_hash(value.text)
    assert report.style_fingerprint == content_hash(canonical_json({"style_rubric": [], "banned_phrases": [], "preset_text": ""})) == style_fingerprint()


def test_new_wire_preserves_complete_sources_and_stable_long_prefix_with_nonce_last():
    value = target(text=canonical_json({"full_content": "中"*30000, "tail": "完整结尾。"}))
    snapshot = canon()
    class Capture:
        def __init__(self): self.requests = []
        def generate(self, request):
            self.requests.append(request)
            sent = json.loads(request.messages[-1].content)
            return LLMResponse(json.dumps(payload(evidence_registry_id=sent["evidence_registry_id"]), ensure_ascii=False))
    provider = Capture()
    service = SemanticReviewService(provider, "fixture")
    for _ in range(2):
        assert service.review(target=value, canon=snapshot, author_brief="保留全部材料。").status == "pass"
    first, second = provider.requests
    a, b = first.messages[-1].content, second.messages[-1].content
    sa, sb = json.loads(a), json.loads(b)
    expected_keys = ["canon", "style_sources", "plan_content", "target", "required_dimensions", "missing_context", "evidence_sources", "evidence_registry_coverage", "output_schema", "evidence_registry_id"]
    assert list(sa) == list(sb) == expected_keys
    assert sa["canon"] == snapshot.model_dump(mode="json")
    assert sa["style_sources"]["author_brief"] == "保留全部材料。"
    assert sa["plan_content"] == json.loads(value.text)
    assert sa["target"]["target_text_sha256"] == content_hash(value.text)
    assert sa["evidence_sources"] and sa["evidence_registry_coverage"]["max_serialized_chars"] == 180000
    na, nb = sa["evidence_registry_id"], sb["evidence_registry_id"]
    assert na != nb and a.endswith('"evidence_registry_id":'+json.dumps(na)+'}')
    assert a.replace(na, "NONCE") == b.replace(nb, "NONCE")
    prefix_a, prefix_b = a[:a.index(na)], b[:b.index(nb)]
    assert prefix_a == prefix_b and len(prefix_a) > 30000
    assert prefix_a.index('"output_schema"') > prefix_a.index('"evidence_registry_coverage"')
    assert first.messages[0].content == second.messages[0].content
    assert na not in first.messages[0].content and nb not in second.messages[0].content
    assert "For EVERY new reply" in first.messages[0].content
    assert "FINAL field of the user JSON" in first.messages[0].content
    # Canonical hashing utility remains sorted and independent of model-wire field order.
    assert canonical_json({"z": 1, "a": 2}) == '{"a":2,"z":1}'
