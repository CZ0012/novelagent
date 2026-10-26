"""Advertised style evidence mirrors existing validation; no response is salvaged."""
import copy
import json
import shutil
import subprocess
import pytest
from storygraph.models.generation_review import SemanticReviewOutput
from storygraph.services.semantic_review import semantic_review_output_schema, resolve_evidence_sources, _validate_output
from storygraph.services.canon_snapshot import canonical_json
from test_semantic_review import target, payload, issue
from test_semantic_review_wire import canon

REGISTRY = {
    "E1": {"kind": "style", "ref": "author_brief", "quote": "摘要宜简洁。"},
    "E31": {"kind": "target", "ref": "d", "quote": "摘要宜简洁。"},
    "E520": {"kind": "target", "ref": "d", "quote": "偏长的摘要。"},
    "E9": {"kind": "canon", "ref": "rule", "quote": "既定规则。"},
}
NONCE = "review_request_synthetic"


def evidence_output(evidence, *, dimension="style_constraint", nonce=True):
    value = payload([issue(dimension=dimension, finding="advice", severity="low", evidence=evidence)])
    if nonce:
        value["evidence_registry_id"] = NONCE
    return value


def test_actual_target_only_alias_pattern_remains_invalid_to_unchanged_runtime():
    value = target("偏长的摘要。摘要宜简洁。", purpose="plan", target_type="proposal", scene_id=None)
    snapshot = canon().model_copy(update={"project_id": "p"})
    raw = evidence_output([{"source_id": "E520"}, {"source_id": "E31"}])
    parsed = SemanticReviewOutput.model_validate(resolve_evidence_sources(raw, REGISTRY, registry_id=NONCE))
    with pytest.raises(ValueError, match="missing_style_evidence"):
        _validate_output(parsed, target=value, canon=snapshot, style_sources={"author_brief": "摘要宜简洁。"})
    assert raw["issues"][0]["evidence"] == [{"source_id": "E520"}, {"source_id": "E31"}]


def test_existing_standard_schema_validator_checks_style_alias_canonical_and_mixed_pairs(tmp_path):
    pwsh = shutil.which("pwsh")
    if not pwsh:
        pytest.skip("PowerShell 7 Test-Json is an optional existing standard JSON Schema validator")
    schema = semantic_review_output_schema(registry=REGISTRY, registry_id=NONCE)
    empty = semantic_review_output_schema(registry={}, registry_id=NONCE)
    t, s = {"kind": "target", "ref": "d", "quote": "偏长的摘要。"}, {"kind": "style", "ref": "author_brief", "quote": "摘要宜简洁。"}
    cases = [
        ("actual_target_only_pair", schema, evidence_output([{"source_id": "E520"}, {"source_id": "E31"}]), False),
        ("alias_pair", schema, evidence_output([{"source_id": "E520"}, {"source_id": "E1"}]), True),
        ("canonical_pair_without_nonce", schema, evidence_output([t, s], nonce=False), True),
        ("target_alias_style_canonical", schema, evidence_output([{"source_id": "E520"}, s]), True),
        ("target_canonical_style_alias", schema, evidence_output([t, {"source_id": "E1"}]), True),
        ("canon_alias_not_style", schema, evidence_output([{"source_id": "E520"}, {"source_id": "E9"}]), False),
        ("style_without_target", schema, evidence_output([{"source_id": "E1"}]), False),
        ("target_without_style", schema, evidence_output([t], nonce=False), False),
        ("nonstyle_target_only_unchanged", schema, evidence_output([{"source_id": "E520"}], dimension="timeline"), True),
        ("empty_registry_canonical_pair", empty, evidence_output([t, s], nonce=False), True),
        ("empty_registry_target_only", empty, evidence_output([t], nonce=False), False),
        ("empty_registry_no_alias", empty, evidence_output([t, {"source_id": "E1"}]), False),
        ("missing_nonce_alias_pair", schema, evidence_output([{"source_id": "E520"}, {"source_id": "E1"}], nonce=False), False),
        ("unknown_alias", schema, evidence_output([{"source_id": "E520"}, {"source_id": "E999"}]), False),
        ("mixed_override", schema, evidence_output([t, {"source_id": "E1", "kind": "style"}]), False),
    ]
    suite = [{"name": n, "schema": sc, "output": out, "expected": expected} for n, sc, out, expected in cases]
    suite_path = tmp_path/"schema-cases.json"
    suite_path.write_text(json.dumps(suite, ensure_ascii=False), encoding="utf-8")
    script = tmp_path/"check-schema.ps1"
    script.write_text('''param([string]$SuitePath)
$cases = Get-Content -LiteralPath $SuitePath -Raw | ConvertFrom-Json
$results = @($cases | ForEach-Object {
  $schemaText = $_.schema | ConvertTo-Json -Depth 100 -Compress
  $outputText = $_.output | ConvertTo-Json -Depth 100 -Compress
  $valid = Test-Json -Json $outputText -Schema $schemaText -ErrorAction SilentlyContinue
  [PSCustomObject]@{ name = $_.name; valid = [bool]$valid; expected = $_.expected }
})
ConvertTo-Json -InputObject $results -Depth 5 -Compress
''', encoding="utf-8")
    completed = subprocess.run([pwsh, "-NoProfile", "-NonInteractive", "-File", str(script), str(suite_path)],
        capture_output=True, text=True, encoding="utf-8", timeout=30, check=True)
    results = json.loads(completed.stdout)
    assert len(results) == len(cases)
    assert all(v["valid"] == v["expected"] for v in results), results


def test_style_conditional_is_fresh_bounded_and_does_not_change_nonstyle_schema():
    schema = semantic_review_output_schema(registry=REGISTRY, registry_id=NONCE)
    issue_shape = schema["$defs"]["GenerationReviewIssue"]
    rule = issue_shape["allOf"][0]
    assert rule["if"]["properties"]["dimension"] == {"const": "style_constraint"}
    selectors = rule["then"]["properties"]["evidence"]["allOf"]
    assert selectors[0]["contains"]["anyOf"][1]["properties"]["source_id"]["enum"] == ["E1"]
    assert selectors[1]["contains"]["anyOf"][1]["properties"]["source_id"]["enum"] == ["E31", "E520"]
    fresh = copy.deepcopy(schema)
    selectors[0]["contains"]["anyOf"].clear()
    assert semantic_review_output_schema(registry=REGISTRY, registry_id=NONCE) == fresh
    big = {f"E{i}": {"kind": "style" if i%2 else "target"} for i in range(1, 2001)}
    assert len(canonical_json(semantic_review_output_schema(registry=big, registry_id=NONCE))) < 40000
