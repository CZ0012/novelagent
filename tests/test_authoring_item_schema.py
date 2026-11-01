"""Advertised conditional item constraints match existing runtime validators."""
import json
import shutil
import subprocess

import pytest
from pydantic import ValidationError

from storygraph.models.authoring import AuthoringDesignItem, authoring_tool_schema
from storygraph.core.errors import ModelOutputError
from test_authoring_protocol import RawProvider
from test_authoring_service import make_service, card


CASES = [
    ({"kind": "character_belief"}, False),
    ({"kind": "character_belief", "character_id": None}, False),
    ({"kind": "character_belief", "character_id": "actor"}, True),
    ({"kind": "character_claim"}, False),
    ({"kind": "character_claim", "character_id": "actor"}, True),
    ({"kind": "open_question", "status": "author_decided"}, False),
    ({"kind": "open_question", "status": "alternative"}, True),
    ({"kind": "open_question"}, True),
    ({"kind": "world_fact", "status": "author_decided"}, True),
]


@pytest.mark.parametrize("fields,valid", CASES)
def test_item_runtime_constraints_remain_unchanged(fields, valid):
    item = {"id": "item", "text": "一个仍待讨论的设计。", **fields}
    if valid:
        assert AuthoringDesignItem.model_validate(item).kind == fields["kind"]
    else:
        with pytest.raises(ValidationError):
            AuthoringDesignItem.model_validate(item)


def test_standard_schema_validator_enforces_item_rules_inside_real_tool_schema(tmp_path):
    pwsh = shutil.which("pwsh")
    if not pwsh:
        pytest.skip("PowerShell 7 Test-Json is an optional existing standard JSON Schema validator")
    suite = [{"expected": valid, "output": {"tool": "propose_workspace", "args": {
        "summary": "设计提案。", "patch": {"upsert_items": [{"id": "item", "text": "一个仍待讨论的设计。", **fields}]}}}}
        for fields, valid in CASES]
    for status, expected in (("proposed", True), ("approved", False)):
        suite.append({"expected": expected, "output": {"tool": "propose_workspace", "args": {
            "summary": "模型只可提出待审卡片。", "patch": {"upsert_scene_cards": [card(status=status, depends_on=[])]}}}})
    data = tmp_path / "schema.json"
    data.write_text(json.dumps({"schema": authoring_tool_schema(), "cases": suite}, ensure_ascii=False), encoding="utf-8")
    script = tmp_path / "schema.ps1"
    script.write_text('''param([string]$DataPath)
$data = Get-Content -LiteralPath $DataPath -Raw | ConvertFrom-Json
$schemaText = $data.schema | ConvertTo-Json -Depth 100 -Compress
$results = @($data.cases | ForEach-Object {
  $outputText = $_.output | ConvertTo-Json -Depth 100 -Compress
  $valid = Test-Json -Json $outputText -Schema $schemaText -ErrorAction SilentlyContinue
  [PSCustomObject]@{ valid = [bool]$valid; expected = $_.expected }
})
ConvertTo-Json -InputObject $results -Depth 5 -Compress
''', encoding="utf-8")
    result = subprocess.run([pwsh, "-NoProfile", "-NonInteractive", "-File", str(script), str(data)],
        capture_output=True, text=True, encoding="utf-8", timeout=30, check=True)
    values = json.loads(result.stdout)
    assert len(values) == len(suite)
    assert all(value["valid"] == value["expected"] for value in values), values


@pytest.mark.parametrize("fields,code", [
    ({"kind": "character_belief"}, "subjective_item_requires_character_id"),
    ({"kind": "open_question", "status": "author_decided"}, "open_question_cannot_be_author_decided"),
])
def test_safe_diagnostics_explain_known_cross_field_rules_without_echoing_item(fields, code):
    raw = {"tool": "propose_workspace", "args": {"summary": "等待审查。", "patch": {
        "upsert_items": [{"id": "PRIVATE_ID_CANARY", "text": "PRIVATE_TEXT_CANARY", **fields}]}}}
    provider = RawProvider(json.dumps(raw))
    service, session = make_service(provider)
    with pytest.raises(ModelOutputError):
        service.turn(project_id="project", session_id=session.id, expected_version=1, message="整理设计。", max_steps=1)
    failed = service.get("project", session.id)
    diagnostic = next(message.content for message in failed.messages if message.tool_name == "format_diagnostic")
    parsed = json.loads(diagnostic)["result"]["diagnostic"]
    assert parsed["hints"][0]["code"] == code
    assert "PRIVATE_ID_CANARY" not in diagnostic and "PRIVATE_TEXT_CANARY" not in diagnostic
    assert len(provider.requests) == 1 and failed.turn_calls_started == 1 and failed.turn_status == "failed"
    assert failed.workspace.items == [] and failed.proposals == []
