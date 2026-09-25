import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi.testclient import TestClient

from apps.api import main
from storygraph.core.config import StoryGraphSettings
from storygraph.core.errors import ContractError, GraphStoreError
from storygraph.services.llm_provider import LLMResponse
from storygraph.services.outline_language_repair import require_local_graph
from storygraph.services.project_language import validate_generated_output_language
from storygraph.stores.memory_graph import InMemoryGraphStore
from storygraph.stores.proposal_store import SQLiteProposalStore


TRANSLATIONS = {
    "The Long Road": "漫长归途", "She leaves.": "她离开了。", "Find the key": "寻找钥匙。",
    "The Last Gate": "最后一道门", "He returns.": "他回来了。", "Open the gate": "打开城门。",
    "The gate is shut": "城门紧闭。", "Before the sunrise": "日出之前",
}
SEED = {"reviewer": "author", "rationale": "Synthetic fixture", "source_ref": "test:outline"}


class Provider:
    def __init__(self):
        self.requests = []
        self.override = None

    def generate(self, request):
        self.requests.append(request)
        payload = json.loads(request.messages[-1].content)
        output = {"changes": [
            {"node_id": item["node_id"], "field": item["field"], "after": TRANSLATIONS[item["text"]]}
            for item in payload["entries"] if item["text"] in TRANSLATIONS
        ]}
        if self.override is not None:
            output = self.override(output)
        return LLMResponse(content=json.dumps(output, ensure_ascii=False))


@pytest.fixture
def setup(tmp_path, monkeypatch):
    settings = StoryGraphSettings(tmp_path)
    settings.graph_backend = "json"
    settings.graph_backend_explicit = True
    settings.llm_base_url = "https://synthetic.invalid/v1"
    settings.llm_api_key = "fixture-secret-never-sent-as-prompt"
    settings.llm_model = "synthetic-model"
    provider = Provider()
    monkeypatch.setattr(main, "create_llm_provider", lambda _: provider)
    original_factory = main.open_configured_graph_store
    captured = {}

    def factory(*args, **kwargs):
        result = original_factory(*args, **kwargs)
        captured["graph"] = result.graph
        return result

    monkeypatch.setattr(main, "open_configured_graph_store", factory)
    client = TestClient(main.create_app(settings))
    project = client.post("/projects", json={"title": "测试作品", "language": "zh-CN"}).json()["project_id"]
    assert client.post(f"/projects/{project}/chapters", json={
        **SEED,
        "id": "chapter_local", "title": "The Long Road", "summary": "She leaves.", "purpose": "Find the key",
    }).status_code == 200
    assert client.post(f"/projects/{project}/chapters/chapter_local/scenes", json={
        **SEED,
        "id": "scene_local", "title": "The Last Gate", "goal": "Open the gate",
        "conflict": "The gate is shut", "timeline_position": "Before the sunrise",
        "properties": {"summary": "He returns.", "pov_label": "PRIVATE_NAME_SENTINEL",
                       "private_notes": "PRIVATE_GRAPH_SENTINEL"},
    }).status_code == 200
    assert client.post(f"/projects/{project}/scenes/scene_local/draft", json={
        "text": "PRIVATE_MANUSCRIPT_SENTINEL", "summary": "PRIVATE_DRAFT_SUMMARY_SENTINEL",
    }).status_code == 200
    return client, settings, project, provider, captured["graph"]


def generate(setup):
    client, _, project, _, _ = setup
    response = client.post(f"/projects/{project}/outline/localization-proposal", json={})
    assert response.status_code == 200, response.text
    return response.json()["proposal"]


def accept(setup, proposal):
    client, _, project, _, _ = setup
    result = client.post(f"/projects/{project}/proposals/{proposal['id']}/accept", json={
        "expected_version": proposal["version"], "reviewer": "author",
    })
    assert result.status_code == 200, result.text
    return result.json()


def apply(setup, proposal):
    client, _, project, _, _ = setup
    return client.post(f"/projects/{project}/proposals/{proposal['id']}/apply/outline-language", json={
        "expected_version": proposal["version"], "reviewer": "author", "rationale": "作者确认译文。",
    })


def revise(setup, proposal, mutate):
    client, _, project, _, _ = setup
    body = json.loads(proposal["body"])
    mutate(body)
    result = client.patch(f"/projects/{project}/proposals/{proposal['id']}", json={
        "expected_version": proposal["version"], "body": json.dumps(body, ensure_ascii=False),
    })
    assert result.status_code == 200, result.text
    return result.json()


def test_generation_uses_only_metadata_and_never_changes_graph(setup):
    client, settings, project, provider, _ = setup
    before = settings.graph_path.read_bytes()
    proposal = generate(setup)
    assert settings.graph_path.read_bytes() == before
    assert proposal["artifact_type"] == "canon_patch"
    assert proposal["status"] == "agent_revised"
    assert proposal["content_language"] == "zh-CN"
    assert len(json.loads(proposal["body"])["changes"]) == 8
    sent = "\n".join(item.content for item in provider.requests[0].messages)
    for secret in ("PRIVATE_MANUSCRIPT_SENTINEL", "PRIVATE_DRAFT_SUMMARY_SENTINEL",
                   "PRIVATE_NAME_SENTINEL", "PRIVATE_GRAPH_SENTINEL", settings.llm_api_key):
        assert secret not in sent
    assert "before" not in json.loads(provider.requests[0].messages[-1].content)
    assert apply(setup, proposal).status_code == 409
    assert settings.graph_path.read_bytes() == before
    accept(setup, proposal)
    assert settings.graph_path.read_bytes() == before
    assert client.get(f"/projects/{project}/facts/pending").json() == {"facts": []}


def test_apply_preserves_ids_relations_prose_and_retries_without_events(setup):
    client, settings, project, _, graph = setup
    proposal = accept(setup, generate(setup))
    before = json.loads(settings.graph_path.read_text(encoding="utf-8"))
    original_draft = client.get(f"/projects/{project}/scenes/scene_local/draft").json()
    result = apply(setup, proposal)
    assert result.status_code == 200, result.text
    assert result.json()["applied_count"] == 8
    assert result.json()["already_applied"] is False
    after = json.loads(settings.graph_path.read_text(encoding="utf-8"))
    assert {item["id"] for item in after["nodes"]} == {item["id"] for item in before["nodes"]}
    assert after["relationships"] == before["relationships"]
    assert len(after["event_log"]) == len(before["event_log"]) + 2
    assert graph.get_node("scene_local").properties["summary"] == "他回来了。"
    assert graph.get_node("scene_local").properties["pov_label"] == "PRIVATE_NAME_SENTINEL"
    assert client.get(f"/projects/{project}/scenes/scene_local/draft").json() == original_draft
    repeat = apply(setup, proposal)  # Original accepted version after response loss.
    assert repeat.status_code == 200
    assert repeat.json()["already_applied"] is True
    assert repeat.json()["proposal"] == result.json()["proposal"]
    assert json.loads(settings.graph_path.read_text(encoding="utf-8")) == after


@pytest.mark.parametrize("mutation", [
    lambda body: body["changes"][0].update(field="project_id", after="foreign"),
    lambda body: body["changes"][0].update(before="Forged original"),
    lambda body: body["changes"][0].update(node_id="scene_local", node_type="Scene"),
    lambda body: body.update(project_id="foreign_project"),
    lambda body: body.update(output_language="en-US"),
    lambda body: body.update(schema="arbitrary_canon_patch"),
    lambda body: body["changes"][0].update(operation="delete_node"),
    lambda body: body["changes"].append(body["changes"][0].copy()),
    lambda body: body["changes"][0].update(after="He returns."),
])
def test_edited_body_injection_is_rejected_without_any_write(setup, mutation):
    _, settings, _, _, _ = setup
    proposal = accept(setup, revise(setup, generate(setup), mutation))
    before = settings.graph_path.read_bytes()
    result = apply(setup, proposal)
    assert result.status_code == 409
    assert settings.graph_path.read_bytes() == before


def test_author_can_edit_only_replacement_and_omit_changes(setup):
    def edit(body):
        body["changes"] = body["changes"][:1]
        body["changes"][0]["after"] = "作者调整后的中文目的。"
    proposal = accept(setup, revise(setup, generate(setup), edit))
    result = apply(setup, proposal)
    assert result.status_code == 200, result.text
    assert result.json()["applied_count"] == 1


@pytest.mark.parametrize("stale", ["field", "language", "version"])
def test_stale_snapshot_or_language_rejects_entire_patch(setup, stale):
    client, settings, project, _, _ = setup
    proposal = accept(setup, generate(setup))
    if stale == "field":
        assert client.patch(f"/projects/{project}/scenes/scene_local", json={**SEED, "title": "作者新标题"}).status_code == 200
    elif stale == "language":
        assert client.patch(f"/projects/{project}", json={
            "language": "en-US", "expected_language": "zh-CN", "language_change_policy": "future_outputs_only",
        }).status_code == 200
    else:
        proposal["version"] -= 1
    before = settings.graph_path.read_bytes()
    result = apply(setup, proposal)
    assert result.status_code == 409
    assert result.json()["detail"]["category"] == "outline_language_stale"
    assert settings.graph_path.read_bytes() == before


def test_cross_project_route_and_target_reference_injection_rejected(setup):
    client, settings, project, _, _ = setup
    proposal = generate(setup)
    modified = client.patch(f"/projects/{project}/proposals/{proposal['id']}", json={
        "expected_version": proposal["version"], "target_refs": [{"kind": "graph_node", "ref": "foreign"}],
    }).json()
    accepted = accept(setup, modified)
    before = settings.graph_path.read_bytes()
    assert apply(setup, accepted).status_code == 409
    assert client.post(f"/projects/foreign/proposals/{proposal['id']}/apply/outline-language", json={
        "expected_version": accepted["version"],
    }).status_code == 409
    assert settings.graph_path.read_bytes() == before


@pytest.mark.parametrize("permission", ["read_only", "read_generate"])
def test_permissions_are_enforced_before_calls_and_graph_writes(setup, permission):
    client, settings, project, provider, _ = setup
    proposal = accept(setup, generate(setup))
    assert client.put("/settings/agent", json={"permission_level": permission}).status_code == 200
    before = settings.graph_path.read_bytes()
    calls = len(provider.requests)
    generated = client.post(f"/projects/{project}/outline/localization-proposal", json={})
    assert generated.status_code == (403 if permission == "read_only" else 200)
    assert len(provider.requests) == calls + (permission == "read_generate")
    assert apply(setup, proposal).status_code == 403
    assert settings.graph_path.read_bytes() == before


@pytest.mark.parametrize("failure", ["disk", "stage"])
def test_staging_or_atomic_save_failure_leaves_live_and_disk_graph_unchanged(setup, monkeypatch, failure):
    client, settings, project, _, graph = setup
    proposal = accept(setup, generate(setup))
    before = settings.graph_path.read_bytes()
    live_before = {key: value.model_dump() for key, value in graph.nodes.items()}
    events_before = graph.event_log.list()
    if failure == "disk":
        def fail_save(*_):
            raise OSError("PRIVATE_DISK_DETAILS")
        monkeypatch.setattr("storygraph.stores.json_graph._serialize_payload", fail_save)
    else:
        original_update = InMemoryGraphStore.update_node
        count = 0
        def fail_second(self, *args, **kwargs):
            nonlocal count
            count += 1
            if count == 2:
                raise RuntimeError("PRIVATE_STAGING_DETAILS")
            return original_update(self, *args, **kwargs)
        monkeypatch.setattr(InMemoryGraphStore, "update_node", fail_second)
    result = apply(setup, proposal)
    assert result.status_code == 503
    assert "PRIVATE_" not in result.text
    assert settings.graph_path.read_bytes() == before
    assert {key: value.model_dump() for key, value in graph.nodes.items()} == live_before
    assert graph.event_log.list() == events_before
    assert client.get(f"/projects/{project}/proposals/{proposal['id']}").json() == proposal


def test_derived_ref_failure_recovers_without_repeating_graph_writes(setup, monkeypatch):
    _, settings, _, _, _ = setup
    proposal = accept(setup, generate(setup))
    original = SQLiteProposalStore.record_derived_refs
    def fail(*args, **kwargs):
        raise OSError("PRIVATE_SQLITE_DETAILS")
    monkeypatch.setattr(SQLiteProposalStore, "record_derived_refs", fail)
    result = apply(setup, proposal)
    assert result.status_code == 503
    after = settings.graph_path.read_bytes()
    monkeypatch.setattr(SQLiteProposalStore, "record_derived_refs", original)
    result = apply(setup, proposal)
    assert result.status_code == 200
    assert result.json()["already_applied"] is True
    assert len(result.json()["proposal"]["derived_refs"]) == 2
    assert settings.graph_path.read_bytes() == after


def test_concurrent_apply_has_one_event_batch(setup):
    _, _, _, _, graph = setup
    proposal = accept(setup, generate(setup))
    before = len(graph.event_log.list())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: apply(setup, proposal), range(2)))
    assert all(item.status_code == 200 for item in results)
    assert sorted(item.json()["already_applied"] for item in results) == [False, True]
    assert len(graph.event_log.list()) == before + 2


def test_incomplete_event_evidence_fails_closed(setup):
    _, settings, _, _, graph = setup
    proposal = accept(setup, generate(setup))
    assert apply(setup, proposal).status_code == 200
    graph.event_log._events.pop()
    before = settings.graph_path.read_bytes()
    assert apply(setup, proposal).status_code == 409
    assert settings.graph_path.read_bytes() == before


def test_foreign_derived_refs_fail_closed(setup):
    _, settings, _, _, _ = setup
    from storygraph.models.proposal import ProposalRef
    proposal = accept(setup, generate(setup))
    store = SQLiteProposalStore(settings.proposal_store_path)
    store.record_derived_refs(proposal["id"], derived_refs=[ProposalRef(kind="canon_event", ref="evt_foreign")], actor="author")
    before = settings.graph_path.read_bytes()
    assert apply(setup, proposal).status_code == 409
    assert settings.graph_path.read_bytes() == before
    store.close()


def test_target_transferred_to_another_project_fails_before_any_mutation(setup):
    _, settings, _, _, graph = setup
    proposal = accept(setup, generate(setup))
    graph.update_node("scene_local", {"project_id": "foreign"}, **{
        "reviewer": "author", "rationale": "Synthetic scope test", "source_ref": "test:scope",
    })
    before = settings.graph_path.read_bytes()
    assert apply(setup, proposal).status_code == 409
    assert settings.graph_path.read_bytes() == before


def test_generation_language_change_creates_no_proposal(setup):
    client, settings, project, provider, _ = setup
    def change_language(output):
        assert client.patch(f"/projects/{project}", json={
            "language": "en-US", "expected_language": "zh-CN", "language_change_policy": "future_outputs_only",
        }).status_code == 200
        return output
    provider.override = change_language
    result = client.post(f"/projects/{project}/outline/localization-proposal", json={})
    assert result.status_code == 409
    assert result.json()["detail"]["category"] == "outline_language_stale"
    assert client.get(f"/projects/{project}/proposals").json()["proposals"] == []
    assert json.loads(settings.graph_path.read_text(encoding="utf-8"))["nodes"]


def test_generation_preserves_original_values_despite_concurrent_author_edit(setup):
    client, _, project, provider, _ = setup
    def change_title(output):
        assert client.patch(f"/projects/{project}/scenes/scene_local", json={**SEED, "title": "作者刚改过"}).status_code == 200
        return output
    provider.override = change_title
    proposal = generate(setup)
    entry = next(item for item in json.loads(proposal["body"])["changes"] if item["node_id"] == "scene_local" and item["field"] == "title")
    assert entry["before"] == "The Last Gate"
    assert apply(setup, accept(setup, proposal)).status_code == 409


def test_restart_recovers_missing_proposal_refs_without_duplicate_events(setup, monkeypatch):
    _, settings, project, _, _ = setup
    proposal = accept(setup, generate(setup))
    original = SQLiteProposalStore.record_derived_refs
    monkeypatch.setattr(SQLiteProposalStore, "record_derived_refs", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("Fail")))
    assert apply(setup, proposal).status_code == 503
    before = settings.graph_path.read_bytes()
    monkeypatch.setattr(SQLiteProposalStore, "record_derived_refs", original)
    restarted = TestClient(main.create_app(settings))
    result = restarted.post(f"/projects/{project}/proposals/{proposal['id']}/apply/outline-language", json={"expected_version": proposal["version"]})
    assert result.status_code == 200, result.text
    assert result.json()["already_applied"] is True
    assert len(result.json()["proposal"]["derived_refs"]) == 2
    assert settings.graph_path.read_bytes() == before


def test_accepted_proposal_cannot_be_edited_while_application_is_saving(setup, monkeypatch):
    client, _, project, _, _ = setup
    proposal = accept(setup, generate(setup))
    saving, resume = Event(), Event()
    original = main.save_json_graph
    def pause_save(*args):
        saving.set()
        assert resume.wait(5)
        return original(*args)
    monkeypatch.setattr(main, "save_json_graph", pause_save)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(apply, setup, proposal)
        assert saving.wait(5)
        try:
            result = client.patch(f"/projects/{project}/proposals/{proposal['id']}", json={
                "expected_version": proposal["version"], "body": "{}",
            })
            assert result.status_code == 409
        finally:
            resume.set()
        assert pending.result(timeout=5).status_code == 200


def test_completed_retry_never_overwrites_later_author_changes(setup):
    client, settings, project, _, _ = setup
    proposal = accept(setup, generate(setup))
    assert apply(setup, proposal).status_code == 200
    assert client.patch(f"/projects/{project}/scenes/scene_local", json={**SEED, "title": "作者后来写的新标题"}).status_code == 200
    before = settings.graph_path.read_bytes()
    repeat = apply(setup, proposal)
    assert repeat.status_code == 200
    assert repeat.json()["already_applied"] is True
    assert settings.graph_path.read_bytes() == before


@pytest.mark.parametrize("output", [
    {"changes": []},
    {"changes": [{"node_id": "foreign", "field": "title", "after": "中文标题"}]},
    {"changes": [{"node_id": "scene_local", "field": "summary", "after": "He returns."}]},
    {"changes": [{"node_id": "scene_local", "field": "summary", "after": "中文摘要", "before": "forged"}]},
])
def test_invalid_or_empty_generation_has_no_proposal_or_graph_write(setup, output):
    client, settings, project, provider, _ = setup
    provider.override = lambda _: output
    before = settings.graph_path.read_bytes()
    result = client.post(f"/projects/{project}/outline/localization-proposal", json={})
    assert result.status_code == 409
    assert settings.graph_path.read_bytes() == before
    assert client.get(f"/projects/{project}/proposals").json()["proposals"] == []


def test_size_budget_and_unsupported_backend_reject_before_provider(setup):
    client, _, project, provider, graph = setup
    graph.update_node("scene_local", {"summary": "x" * 2001}, reviewer="author", rationale="Test", source_ref="test")
    assert client.post(f"/projects/{project}/outline/localization-proposal", json={}).status_code == 409
    assert provider.requests == []
    with pytest.raises(GraphStoreError, match="local JSON"):
        require_local_graph(object())


@pytest.mark.parametrize("field", ["summary", "reply", "self_check[0]", "proposal_body"])
def test_short_generated_english_prose_rejected(field):
    with pytest.raises(ContractError):
        validate_generated_output_language(output_language="zh-CN", fields={field: "He returns."})


@pytest.mark.parametrize("name", ["The Who", "King's Landing", "New York", "AI", "Mars", "scene_001"])
def test_short_proper_names_remain_allowed(name):
    validate_generated_output_language(output_language="zh-CN", fields={"summary": name})


def test_english_project_repairs_chinese_metadata_in_english(setup):
    client, _, project, provider, graph = setup
    assert client.patch(f"/projects/{project}", json={
        "language": "en-US", "expected_language": "zh-CN", "language_change_policy": "future_outputs_only",
    }).status_code == 200
    assert client.patch(f"/projects/{project}/scenes/scene_local", json={**SEED, "title": "最后一道门"}).status_code == 200
    provider.override = lambda _: {"changes": [{"node_id": "scene_local", "field": "title", "after": "The Last Gate"}]}
    proposal = generate(setup)
    assert proposal["content_language"] == "en-US"
    assert json.loads(provider.requests[0].messages[-1].content)["output_language"] == "en-US"
    assert apply(setup, accept(setup, proposal)).status_code == 200
    assert graph.get_node("scene_local").properties["title"] == "The Last Gate"


def test_archived_node_cannot_be_repaired(setup):
    _, settings, _, _, graph = setup
    proposal = accept(setup, generate(setup))
    graph.nodes["scene_local"] = graph.nodes["scene_local"].model_copy(update={"status": "DEPRECATED"})
    before = settings.graph_path.read_bytes()
    assert apply(setup, proposal).status_code == 404
    assert settings.graph_path.read_bytes() == before


@pytest.mark.parametrize("provider_error,category,http_status", [
    ("LLM provider HTTP 404 [endpoint_not_found]: PRIVATE_PROVIDER_TEXT", "endpoint_not_found", 404),
    ("LLM provider HTTP 401 [invalid_credentials]: PRIVATE_PROVIDER_TEXT", "invalid_credentials", 401),
    ("LLM provider HTTP 429 [rate_limit]: PRIVATE_PROVIDER_TEXT", "rate_limit", 429),
    ("LLM provider [connection_error]: PRIVATE_PROVIDER_TEXT", "connection_error", None),
    ("PRIVATE_PROVIDER_TEXT", "failed", None),
])
def test_provider_failure_keeps_only_safe_category_and_status(setup, provider_error, category, http_status):
    client, settings, project, provider, _ = setup
    def fail(_):
        raise RuntimeError(provider_error)
    provider.override = fail
    before = settings.graph_path.read_bytes()
    result = client.post(f"/projects/{project}/outline/localization-proposal", json={})
    assert result.status_code == 502
    assert "PRIVATE_PROVIDER_TEXT" not in result.text
    assert result.json()["detail"]["category"] == "outline_language_provider_" + category
    assert result.json()["detail"].get("provider_http_status") == http_status
    assert client.get(f"/projects/{project}/proposals").json()["proposals"] == []
    assert settings.graph_path.read_bytes() == before


@pytest.mark.parametrize("wrapper,accepted", [
    ("```json\n%s\n```", True),
    ("```\n%s\n```", True),
    (" \n```JSON\r\n%s\r\n```\n ", True),
    ("Here is the translation:\n```json\n%s\n```", False),
    ("```json\n%s\n```\nExtra explanation", False),
    ("<think>reasoning</think>\n```json\n%s\n```", False),
    ("```json\n%s\n```\n```json\n{}\n```", False),
    ("```json\n%s", False),
])
def test_exact_single_json_fence_supported_without_extra_text(setup, monkeypatch, wrapper, accepted):
    client, settings, project, provider, _ = setup
    original = provider.generate
    def wrapped(request):
        return LLMResponse(content=wrapper % original(request).content)
    monkeypatch.setattr(provider, "generate", wrapped)
    before = settings.graph_path.read_bytes()
    response = client.post(f"/projects/{project}/outline/localization-proposal", json={})
    assert response.status_code == (200 if accepted else 409), response.text
    assert settings.graph_path.read_bytes() == before
    proposals = client.get(f"/projects/{project}/proposals").json()["proposals"]
    assert len(proposals) == int(accepted)
