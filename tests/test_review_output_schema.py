"""Wire schema informs the critic; strict parsing remains the only acceptance path."""
import copy
import json
import pytest
from storygraph.models.generation_review import SemanticReviewOutput
from storygraph.services.canon_snapshot import build_canon_snapshot, canonical_json, content_hash
from storygraph.services.semantic_review import (
    SemanticReviewService, semantic_review_output_schema, MAX_EVIDENCE_SOURCES,
)
from storygraph.services.llm_provider import LLMResponse
from test_semantic_review import graph as graph
from test_semantic_review import target, payload, issue, Replay
from test_semantic_review_wire import target as plan_target, canon as plan_canon


def test_model_facing_schema_retains_parser_shape_with_only_exact_transport_variants():
    base = SemanticReviewOutput.model_json_schema()
    schema = semantic_review_output_schema(registry={"E1": {}, "E2": {}}, registry_id="request-a")
    assert schema["additionalProperties"] is False
    assert schema["required"] == [*base["required"], "evidence_registry_id"]
    assert schema["properties"]["evidence_registry_id"] == {"type": "string", "const": "request-a"}
    assert "status_reason" not in schema["properties"]
    items = schema["$defs"]["GenerationReviewIssue"]["properties"]["evidence"]["items"]["anyOf"]
    assert items[0] == {"$ref": "#/$defs/GenerationReviewEvidence"}
    assert items[1] == {"type": "object", "additionalProperties": False,
        "properties": {"source_id": {"type": "string", "enum": ["E1", "E2"]}}, "required": ["source_id"]}
    assert schema["allOf"][0]["then"] == {"required": ["evidence_registry_id"]}
    # Removing only the explicit transport additions yields the original model schema exactly.
    original = copy.deepcopy(schema)
    original.pop("allOf")
    original["properties"].pop("evidence_registry_id")
    original["required"].remove("evidence_registry_id")
    original["$defs"]["GenerationReviewIssue"]["properties"]["evidence"]["items"] = items[0]
    original["$defs"]["GenerationReviewIssue"].pop("allOf")
    assert original == base
    assert base["additionalProperties"] is False
    assert all(v["additionalProperties"] is False for v in schema["$defs"].values())


@pytest.mark.parametrize("form", ["alias", "canonical"])
def test_actual_wire_schema_nonce_and_legacy_output_compatibility(graph, form):
    snapshot = build_canon_snapshot(graph, project_id="p", scene_id="s")
    class Critic:
        def __init__(self): self.sent = []
        def generate(self, request):
            sent = json.loads(request.messages[-1].content)
            self.sent.append(sent)
            assert sent["output_schema"]["properties"]["evidence_registry_id"]["const"] == sent["evidence_registry_id"]
            assert "Follow the supplied output_schema exactly" in request.messages[0].content
            if form == "canonical":
                output = payload([issue()])  # No token remains compatible for canonical-only output.
            else:
                registry = sent["evidence_sources"]
                ids = [next(k for k, v in registry.items() if v["kind"] == "target"),
                       next(k for k, v in registry.items() if v["kind"] == "canon" and v["ref"] == "secret")]
                output = payload([issue(evidence=[{"source_id": key} for key in ids])], evidence_registry_id=sent["evidence_registry_id"])
            return LLMResponse(json.dumps(output, ensure_ascii=False))
    provider = Critic()
    service = SemanticReviewService(provider, "fixture")
    assert service.review(target=target(), canon=snapshot).status == "needs_revision"
    assert service.review(target=target(), canon=snapshot).status == "needs_revision"
    assert provider.sent[0]["evidence_registry_id"] != provider.sent[1]["evidence_registry_id"]
    assert provider.sent[0]["output_schema"] != provider.sent[1]["output_schema"]


@pytest.mark.parametrize("extra_scope", ["output", "issue", "evidence"])
def test_explicit_schema_does_not_accept_unknown_extra_fields_or_status_reason(graph, extra_scope):
    output = payload([issue()])
    where = output if extra_scope == "output" else output["issues"][0] if extra_scope == "issue" else output["issues"][0]["evidence"][0]
    where["status_reason"] = "unsupported"
    snapshot = build_canon_snapshot(graph, project_id="p", scene_id="s")
    report = SemanticReviewService(Replay(output), "fixture").review(target=target(), canon=snapshot)
    assert report.status == "inconclusive" and not report.issues
    assert "semantic_review_invalid_output" in report.coverage.limitations


def test_schema_is_bounded_and_complete_plan_payload_and_registry_budgets_are_preserved():
    registry = {f"E{i}": {} for i in range(1, MAX_EVIDENCE_SOURCES+1)}
    schema = semantic_review_output_schema(registry=registry, registry_id="review_request_123456789012")
    assert len(canonical_json(schema)) < 40000
    value = plan_target(text=canonical_json({"full_content": "中"*140000, "tail": "完整结尾。"}))
    class Capture:
        def generate(self, request):
            sent = json.loads(request.messages[-1].content)
            assert sent["plan_content"] == json.loads(value.text)
            assert sent["target"]["target_text_sha256"] == content_hash(value.text)
            assert sent["evidence_registry_coverage"]["max_entries"] == 2000
            assert sent["evidence_registry_coverage"]["max_serialized_chars"] == 180000
            assert "output_schema" in sent and "style_sources" in sent and "canon" in sent
            return LLMResponse(json.dumps(payload(), ensure_ascii=False))
    assert SemanticReviewService(Capture(), "fixture", max_target_chars=200000).review(target=value, canon=plan_canon()).status == "pass"
