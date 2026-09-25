import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from apps.api import main
from storygraph.core.config import StoryGraphSettings
from storygraph.services.llm_provider import LLMResponse
from storygraph.stores.draft_store import SQLiteDraftStore
from storygraph.stores.proposal_store import SQLiteProposalStore

SEED = {"reviewer": "author", "rationale": "Synthetic fixture", "source_ref": "test:manuscript"}


class Provider:
    def __init__(self):
        self.requests = []
        self.override = None

    def generate(self, request):
        self.requests.append(request)
        payload = json.loads(request.messages[-1].content)
        if "scope" in payload:
            output = {
                "volume_title": "远行之卷" if payload["scope"] == "volume" else None,
                "chapters": [
                    {
                        "title": "雾中的来信",
                        "summary": "林谨在码头收到来信。",
                        "purpose": "推动主角启程。",
                        "scenes": [
                            {
                                "title": "码头来信",
                                "summary": "林谨在码头收到来信。",
                                "goal": "找到送信人。",
                                "conflict": "送信人已经离开。",
                                "prose": "林谨把信收入口袋。海风吹过码头，他沿着台阶向灯塔走去。",
                            }
                            for _ in range(payload["scenes_per_chapter"])
                        ],
                    }
                    for _ in range(payload["chapter_count"])
                ],
            }
        else:
            output = {
                "reply": "已根据所选上下文生成草稿。",
                "proposal_title": "码头正文草稿",
                "proposal_body": "海风掠过码头，林谨收起信。",
                "replacement_text": "新的段落。",
                "continuation_text": "他沿着台阶向灯塔走去。",
            }
        if self.override:
            output = self.override(output)
        return LLMResponse(content=json.dumps(output, ensure_ascii=False))


@pytest.fixture
def setup(tmp_path, monkeypatch):
    settings = StoryGraphSettings(tmp_path)
    settings.graph_backend = "json"
    settings.graph_backend_explicit = True
    settings.llm_base_url = "https://fixture.invalid/v1"
    settings.llm_api_key = "fixture-secret"
    settings.llm_model = "third-party-test-model"
    provider = Provider()
    monkeypatch.setattr(main, "create_llm_provider", lambda _: provider)
    captured = {}
    factory = main.open_configured_graph_store

    def capture(*args, **kwargs):
        result = factory(*args, **kwargs)
        captured["graph"] = result.graph
        return result

    monkeypatch.setattr(main, "open_configured_graph_store", capture)
    client = TestClient(main.create_app(settings))
    project = client.post("/projects", json={"title": "合成作品", "language": "zh-CN"}).json()[
        "project_id"
    ]
    assert (
        client.post(
            f"/projects/{project}/chapters",
            json={**SEED, "id": "chapter_existing", "title": "旧章", "chapter_index": 1},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/projects/{project}/chapters/chapter_existing/scenes",
            json={**SEED, "id": "scene_existing", "title": "旧场景"},
        ).status_code
        == 200
    )
    return client, settings, project, provider, captured


def generate(setup, **values):
    client, _, project, _, _ = setup
    response = client.post(
        f"/projects/{project}/composition-proposals",
        json={"instruction": "根据背景生成新的章节正文。", **values},
    )
    assert response.status_code == 200, response.text
    return response.json()["proposal"]


def accept(setup, proposal):
    client, _, project, _, _ = setup
    response = client.post(
        f"/projects/{project}/proposals/{proposal['id']}/accept",
        json={"expected_version": proposal["version"], "reviewer": "author"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def apply(setup, proposal):
    client, _, project, _, _ = setup
    return client.post(
        f"/projects/{project}/proposals/{proposal['id']}/apply/composition",
        json={
            "expected_version": proposal["version"],
            "reviewer": "author",
            "rationale": "确认结构和正文草稿。",
        },
    )


def import_source(setup, text="正文😀第一段。\n正文第二段。", language="zh-CN"):
    client, _, project, _, _ = setup
    response = client.post(
        f"/projects/{project}/sources",
        json={
            "title": "资料",
            "relative_path": "material.txt",
            "media_type": "text/plain",
            "language": language,
            "byte_size": len(text.encode()),
            "checksum_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "extraction_status": "ready",
            "extracted_text": text,
            "provenance": {"imported_by": "author"},
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["document"]


def source_request(source, text="正文😀第一段。\n正文第二段。", **overrides):
    return {
        "source_document_id": source["id"],
        "expected_source_updated_at": source["updated_at"],
        "expected_source_checksum": source["checksum_sha256"],
        "start": 0,
        "end": len(text.encode("utf-16-le")) // 2,
        "expected_text": text,
        "expected_current_draft_id": None,
        **overrides,
    }


def test_composition_review_gates_generation_preset_and_repeat(setup):
    client, settings, project, provider, _ = setup
    before = settings.graph_path.read_bytes()
    proposal = generate(setup, scope="volume", chapter_count=2, scenes_per_chapter=2)
    assert settings.graph_path.read_bytes() == before
    assert apply(setup, proposal).status_code == 409
    assert "agent_preset=" in proposal["provenance"]["note"]
    assert any("少用状语" in message.content for message in provider.requests[0].messages)
    accepted = accept(setup, proposal)
    assert settings.graph_path.read_bytes() == before
    response = apply(setup, accepted)
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["chapters"]) == 2 and len(data["scenes"]) == len(data["drafts"]) == 4
    assert len({scene["id"] for scene in data["scenes"]}) == 4
    assert all(chapter["properties"]["volume_index"] == 2 for chapter in data["chapters"])
    after = settings.graph_path.read_bytes()
    again = apply(setup, accepted)
    assert again.status_code == 200, again.text
    assert again.json()["already_applied"]
    assert [draft["id"] for draft in again.json()["drafts"]] == [
        draft["id"] for draft in data["drafts"]
    ]
    assert settings.graph_path.read_bytes() == after
    assert client.get(f"/projects/{project}/scenes/scene_existing/draft").json()["draft"] is None


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: {**p, "other": "untrusted"},
        lambda p: {**p, "chapters": []},
        lambda p: {**p, "chapters": p["chapters"] * 2},
        lambda p: {**p, "chapters": [{**p["chapters"][0], "title": "The Last Gate"}]},
        lambda p: {
            **p,
            "chapters": [
                {**p["chapters"][0], "scenes": [{**p["chapters"][0]["scenes"][0], "prose": ""}]}
            ],
        },
        lambda p: {
            **p,
            "chapters": [
                {
                    **p["chapters"][0],
                    "scenes": [{**p["chapters"][0]["scenes"][0], "prose": "文" * 8001}],
                }
            ],
        },
    ],
)
def test_invalid_provider_output_never_persists(setup, mutation):
    client, settings, project, provider, _ = setup
    before = settings.graph_path.read_bytes()
    provider.override = mutation
    response = client.post(
        f"/projects/{project}/composition-proposals", json={"instruction": "写作。"}
    )
    assert response.status_code == 409
    assert settings.graph_path.read_bytes() == before
    assert not SQLiteProposalStore(settings.proposal_store_path).list(project_id=project)


def test_explicit_sources_and_pinned_draft_no_implicit_private_content(setup):
    client, _, project, provider, _ = setup
    source = import_source(
        setup, text="The courier left a private reference document at the gate.", language="en-US"
    )
    saved = client.post(
        f"/projects/{project}/scenes/scene_existing/draft", json={"text": "私有正文。"}
    ).json()
    generate(setup)
    payload = json.loads(provider.requests[-1].messages[-1].content)
    assert payload["sources"] == [] and payload["included_draft"] is None
    rejected = client.post(
        f"/projects/{project}/composition-proposals",
        json={"instruction": "写作。", "source_document_ids": [source["id"]]},
    )
    assert rejected.status_code == 409 and len(provider.requests) == 1
    proposal = generate(
        setup,
        source_document_ids=[source["id"]],
        cross_language_policy="explicit_reference",
        scene_id="scene_existing",
        included_draft_id=saved["id"],
    )
    payload = json.loads(provider.requests[-1].messages[-1].content)
    assert payload["included_draft"]["text"] == saved["text"]
    assert payload["sources"][0]["id"] == source["id"]
    assert {ref["kind"] for ref in proposal["source_refs"]} == {
        "project",
        "source_document",
        "draft",
    }


def test_too_large_input_rejected_before_provider(setup):
    client, _, project, provider, _ = setup
    source = import_source(setup, text="文" * 100001)
    result = client.post(
        f"/projects/{project}/composition-proposals",
        json={"instruction": "写作。", "source_document_ids": [source["id"]]},
    )
    assert result.status_code == 409 and not provider.requests


@pytest.mark.parametrize("damage", ["relation", "node_type", "event_payload", "volume_collision"])
def test_structure_evidence_or_position_damage_rejected(setup, damage):
    _, settings, _, _, captured = setup
    proposal = accept(setup, generate(setup, scope="volume", scenes_per_chapter=2))
    graph = captured["graph"]
    if damage == "volume_collision":
        node = graph.nodes["chapter_existing"]
        graph.nodes[node.id] = node.model_copy(
            update={"properties": {**node.properties, "volume_index": 2}}
        )
        assert apply(setup, proposal).status_code == 409
        return
    first = apply(setup, proposal).json()
    if damage == "relation":
        relation = next(
            value for value in graph.relationships.values() if value.type == "NEXT_SCENE"
        )
        del graph.relationships[relation.id]
    elif damage == "node_type":
        node = graph.nodes[first["scenes"][0]["id"]]
        graph.nodes[node.id] = node.model_copy(update={"type": "Character"})
    else:
        event = next(
            value for value in graph.event_log.list() if value.target == first["scenes"][0]["id"]
        )
        event.payload["properties"]["title"] = "错误标题"
    result = apply(setup, proposal)
    assert result.status_code in {404, 409}
    assert (
        len(
            SQLiteDraftStore(settings.draft_store_path).list_versions(
                first["drafts"][0]["project_id"], first["drafts"][0]["scene_id"]
            )
        )
        == 1
    )


def test_graph_failure_leaves_no_graph_or_draft(setup, monkeypatch):
    _, settings, project, _, _ = setup
    proposal = accept(setup, generate(setup))
    before = settings.graph_path.read_bytes()

    def fail(*args):
        raise OSError("fixture disk failure")

    monkeypatch.setattr(main, "save_json_graph", fail)
    response = apply(setup, proposal)
    assert response.status_code == 503
    assert settings.graph_path.read_bytes() == before
    assert (
        SQLiteDraftStore(settings.draft_store_path)
        ._connection.execute("SELECT COUNT(*) FROM drafts")
        .fetchone()[0]
        == 0
    )


def test_draft_batch_and_ref_failure_recover_after_restart(setup, monkeypatch):
    client, settings, project, _, _ = setup
    proposal = accept(setup, generate(setup, scenes_per_chapter=2))
    original = SQLiteDraftStore._insert
    calls = 0

    def fail_second(self, draft):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("fixture draft disk failure")
        return original(self, draft)

    monkeypatch.setattr(SQLiteDraftStore, "_insert", fail_second)
    response = apply(setup, proposal)
    assert response.status_code == 503
    assert response.json()["detail"]["category"] == "composition_persistence_failed"
    assert (
        SQLiteDraftStore(settings.draft_store_path)
        ._connection.execute("SELECT COUNT(*) FROM drafts")
        .fetchone()[0]
        == 0
    )
    monkeypatch.setattr(SQLiteDraftStore, "_insert", original)
    recreated = (TestClient(main.create_app(settings)), settings, project, setup[3], setup[4])
    after_graph = settings.graph_path.read_bytes()
    response = apply(recreated, proposal)
    assert response.status_code == 200, response.text
    assert response.json()["already_applied"] and len(response.json()["drafts"]) == 2
    assert settings.graph_path.read_bytes() == after_graph


def test_ref_failure_retries_without_duplicate_drafts(setup, monkeypatch):
    proposal = accept(setup, generate(setup))
    original = SQLiteProposalStore.record_derived_refs

    def fail(*args, **kwargs):
        raise OSError("fixture ref failure")

    monkeypatch.setattr(SQLiteProposalStore, "record_derived_refs", fail)
    assert apply(setup, proposal).status_code == 503
    monkeypatch.setattr(SQLiteProposalStore, "record_derived_refs", original)
    response = apply(setup, proposal)
    assert response.status_code == 200 and response.json()["already_applied"]
    draft = response.json()["drafts"][0]
    assert (
        len(SQLiteDraftStore(setup[1].draft_store_path).list_versions(setup[2], draft["scene_id"]))
        == 1
    )


def test_concurrent_apply_creates_one_set(setup):
    proposal = accept(setup, generate(setup))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: apply(setup, proposal), range(2)))
    assert all(value.status_code == 200 for value in results)
    assert results[0].json()["drafts"][0]["id"] == results[1].json()["drafts"][0]["id"]


def test_source_adoption_exact_unicode_provenance_and_stale_guard(setup):
    client, settings, project, _, _ = setup
    source = import_source(setup)
    before = settings.graph_path.read_bytes()
    request = source_request(source, start=2, end=4, expected_text="😀")
    url = f"/projects/{project}/scenes/scene_existing/draft/from-source"
    result = client.post(url, json=request)
    assert result.status_code == 200, result.text
    draft = result.json()
    assert draft["text"] == "😀" and draft["provenance"]["offset_unit"] == "utf16"
    assert client.post(url, json=request).json()["id"] == draft["id"]
    assert settings.graph_path.read_bytes() == before
    assert client.post(url, json=source_request(source)).status_code == 409
    assert (
        client.post(
            url, json=source_request(source, expected_current_draft_id=draft["id"])
        ).status_code
        == 200
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"start": 3, "end": 4, "expected_text": "😀"},
        {"end": 9999},
        {"expected_text": "不同正文"},
        {"expected_source_checksum": "0" * 64},
        {"expected_source_updated_at": "stale"},
    ],
)
def test_source_adoption_bad_span_or_stale_has_no_side_effect(setup, overrides):
    client, _, project, _, _ = setup
    source = import_source(setup)
    result = client.post(
        f"/projects/{project}/scenes/scene_existing/draft/from-source",
        json=source_request(source, **overrides),
    )
    assert result.status_code == 409
    assert client.get(f"/projects/{project}/scenes/scene_existing/draft").json()["draft"] is None


def test_source_cross_language_not_relabeled(setup):
    client, _, project, _, _ = setup
    text = "A private source document in English."
    source = import_source(setup, text=text, language="en-US")
    result = client.post(
        f"/projects/{project}/scenes/scene_existing/draft/from-source",
        json=source_request(source, text=text),
    )
    assert result.status_code == 409
    assert result.json()["detail"]["category"] == "source_language_mismatch"


def test_create_scene_generates_only_reviewable_proposal_and_selection_exact(setup):
    client, settings, project, provider, _ = setup
    url = f"/projects/{project}/scenes/scene_existing/agent-discussion"
    before = settings.graph_path.read_bytes()
    result = client.post(
        url,
        json={
            "mode": "create_scene",
            "instruction": "写码头的开头。",
            "include_latest_draft": False,
        },
    )
    assert result.status_code == 200, result.text
    assert result.json()["proposal"]["artifact_type"] == "scene_draft"
    assert client.get(f"/projects/{project}/scenes/scene_existing/draft").json()["draft"] is None
    assert settings.graph_path.read_bytes() == before
    text = "😀第一段。\n相同段落。\n相同段落。\n结尾。"
    draft = client.post(
        f"/projects/{project}/scenes/scene_existing/draft", json={"text": text}
    ).json()
    assert (
        client.post(url, json={"mode": "create_scene", "instruction": "写作。"}).status_code == 409
    )
    start = len(text[: text.rindex("相同段落。")].encode("utf-16-le")) // 2
    result = client.post(
        url,
        json={
            "mode": "revise_selection",
            "instruction": "修改选中段落。",
            "selected_text": "相同段落。",
            "selected_start": start,
            "selected_end": start + 5,
            "included_draft_id": draft["id"],
        },
    )
    assert result.status_code == 200, result.text
    assert result.json()["proposal"]["body"] == "😀第一段。\n相同段落。\n新的段落。\n结尾。"
    before_count = len(provider.requests)
    result = client.post(
        url,
        json={
            "mode": "revise_selection",
            "instruction": "修改。",
            "selected_text": "相同段落。",
            "selected_start": 1,
            "selected_end": 6,
            "included_draft_id": draft["id"],
        },
    )
    assert result.status_code == 409 and len(provider.requests) == before_count


def test_completed_retry_preserves_later_author_draft_and_title(setup):
    client, settings, project, _, captured = setup
    proposal = accept(setup, generate(setup))
    first = apply(setup, proposal).json()
    scene = first["scenes"][0]
    saved = client.post(
        f"/projects/{project}/scenes/{scene['id']}/draft", json={"text": "作者后来亲自修改的正文。"}
    ).json()
    captured["graph"].update_node(
        scene["id"],
        {"title": "作者修改的场景名"},
        reviewer="author",
        rationale="Author edit",
        source_ref="author:edit",
    )
    repeat = apply(setup, proposal)
    assert repeat.status_code == 200, repeat.text
    assert (
        client.get(f"/projects/{project}/scenes/{scene['id']}/draft").json()["draft"]["id"]
        == saved["id"]
    )
    assert repeat.json()["scenes"][0]["properties"]["title"] == "作者修改的场景名"


def test_orphan_creation_evidence_cannot_recreate_structure(setup):
    _, _, _, _, captured = setup
    proposal = accept(setup, generate(setup))
    first = apply(setup, proposal).json()
    graph = captured["graph"]
    for node in first["chapters"] + first["scenes"]:
        del graph.nodes[node["id"]]
    assert apply(setup, proposal).status_code == 409


def test_new_chapter_inherits_named_volume_title(setup):
    _, _, _, _, captured = setup
    graph = captured["graph"]
    existing = graph.nodes["chapter_existing"]
    graph.nodes[existing.id] = existing.model_copy(
        update={
            "properties": {**existing.properties, "volume_title": "既有卷名", "volume_index": 3}
        }
    )
    proposal = generate(setup)
    assert json.loads(proposal["body"])["volume_title"] == "既有卷名"
    result = apply(setup, accept(setup, proposal))
    assert result.status_code == 200, result.text
    assert result.json()["chapters"][0]["properties"]["volume_title"] == "既有卷名"


@pytest.mark.parametrize("saved_empty", [False, True])
def test_empty_scene_proposal_baseline_cannot_override_new_author_draft(setup, saved_empty):
    client, _, project, _, _ = setup
    draft_url = f"/projects/{project}/scenes/scene_existing/draft"
    if saved_empty:
        old = client.post(draft_url, json={"text": ""}).json()
    else:
        old = None
    proposal = client.post(
        f"/projects/{project}/scenes/scene_existing/agent-discussion",
        json={"mode": "create_scene", "instruction": "写第一段。", "include_latest_draft": False},
    ).json()["proposal"]
    original = next(ref for ref in proposal["source_refs"] if ref["kind"] == "scene_draft_baseline")
    assert original["source_span"] == {"empty": True, "draft_id": old["id"] if old else None}
    # An author removing the current refs cannot remove the server's v1 guard.
    proposal = client.patch(
        f"/projects/{project}/proposals/{proposal['id']}",
        json={"expected_version": proposal["version"], "source_refs": []},
    ).json()
    proposal = accept(setup, proposal)
    current = client.post(draft_url, json={"text": "作者另写的新正文。"}).json()
    result = client.post(
        f"/projects/{project}/proposals/{proposal['id']}/promote/draft",
        json={
            "scene_id": "scene_existing",
            "expected_version": proposal["version"],
            "expected_current_draft_id": current["id"],
        },
    )
    assert (
        result.status_code == 409 and result.json()["detail"]["category"] == "draft_baseline_stale"
    )
    assert client.get(draft_url).json()["draft"]["id"] == current["id"]


@pytest.mark.parametrize("saved_empty", [False, True])
def test_empty_scene_adoption_and_completed_retry(setup, saved_empty):
    client, _, project, _, _ = setup
    draft_url = f"/projects/{project}/scenes/scene_existing/draft"
    current = client.post(draft_url, json={"text": ""}).json() if saved_empty else None
    proposal = client.post(
        f"/projects/{project}/scenes/scene_existing/agent-discussion",
        json={"mode": "create_scene", "instruction": "写第一段。", "include_latest_draft": False},
    ).json()["proposal"]
    proposal = accept(setup, proposal)
    request = {
        "scene_id": "scene_existing",
        "expected_version": proposal["version"],
        "expected_current_draft_id": current["id"] if current else None,
    }
    url = f"/projects/{project}/proposals/{proposal['id']}/promote/draft"
    result = client.post(url, json=request)
    assert result.status_code == 200, result.text
    again = client.post(url, json=request)
    assert again.status_code == 200
    assert again.json()["draft"]["id"] == result.json()["draft"]["id"]


def test_selection_offsets_keep_whitespace_and_provenance(setup):
    client, _, project, _, _ = setup
    original = "段首。\n  重复段落。 \n段尾。"
    saved = client.post(
        f"/projects/{project}/scenes/scene_existing/draft", json={"text": original}
    ).json()
    selected = "  重复段落。 "
    start = original.index(selected)
    result = client.post(
        f"/projects/{project}/scenes/scene_existing/agent-discussion",
        json={
            "mode": "revise_selection",
            "instruction": "润色。",
            "selected_text": selected,
            "selected_start": start,
            "selected_end": start + len(selected),
            "included_draft_id": saved["id"],
        },
    )
    assert result.status_code == 200, result.text
    proposal = result.json()["proposal"]
    assert proposal["body"] == "段首。\n新的段落。\n段尾。"
    source = next(ref for ref in proposal["source_refs"] if ref["kind"] == "draft")
    assert source["source_span"]["start"] == start
    assert source["source_span"]["text_sha256"] == hashlib.sha256(selected.encode()).hexdigest()


@pytest.mark.parametrize("permission", ["read_only", "read_generate"])
def test_manuscript_permissions(setup, permission):
    client, _, project, provider, _ = setup
    source = import_source(setup)
    proposal = accept(setup, generate(setup))
    assert client.put("/settings/agent", json={"permission_level": permission}).status_code == 200
    assert apply(setup, proposal).status_code == 403
    assert (
        client.post(
            f"/projects/{project}/scenes/scene_existing/draft/from-source",
            json=source_request(source),
        ).status_code
        == 403
    )
    before_count = len(provider.requests)
    response = client.post(
        f"/projects/{project}/composition-proposals", json={"instruction": "写作。"}
    )
    assert response.status_code == (403 if permission == "read_only" else 200)
    assert len(provider.requests) == before_count + (permission == "read_generate")


def test_foreign_and_archived_sources_fail_before_provider_or_draft(setup):
    client, _, project, provider, _ = setup
    source = import_source(setup)
    other = client.post("/projects", json={"title": "另一作品", "language": "zh-CN"}).json()[
        "project_id"
    ]
    assert (
        client.post(
            f"/projects/{other}/chapters", json={**SEED, "id": "chapter_other", "title": "另一章"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/projects/{other}/chapters/chapter_other/scenes",
            json={**SEED, "id": "scene_other", "title": "另一场景"},
        ).status_code
        == 200
    )
    foreign = client.post(
        f"/projects/{other}/scenes/scene_other/draft/from-source", json=source_request(source)
    )
    assert foreign.status_code in {404, 409}
    foreign = client.post(
        f"/projects/{other}/composition-proposals",
        json={"instruction": "写作。", "source_document_ids": [source["id"]]},
    )
    assert foreign.status_code in {404, 409}
    assert client.post(f"/projects/{project}/sources/{source['id']}/archive").status_code == 200
    archived = client.post(
        f"/projects/{project}/scenes/scene_existing/draft/from-source", json=source_request(source)
    )
    assert archived.status_code == 409
    archived = client.post(
        f"/projects/{project}/composition-proposals",
        json={"instruction": "写作。", "source_document_ids": [source["id"]]},
    )
    assert archived.status_code == 409 and not provider.requests


@pytest.mark.parametrize("expectation", [None, "draft_wrong", "omitted"])
def test_regular_scene_proposal_optional_cas_and_legacy_behavior(setup, expectation):
    client, _, project, _, _ = setup
    saved = client.post(
        f"/projects/{project}/scenes/scene_existing/draft", json={"text": "作者现有正文。"}
    ).json()
    proposal = client.post(
        f"/projects/{project}/proposals",
        json={
            "artifact_type": "scene_draft",
            "title": "正文提案",
            "body": "修改后的正文。",
            "target_refs": [{"kind": "scene", "ref": "scene_existing"}],
        },
    ).json()
    proposal = accept(setup, proposal)
    request = {"scene_id": "scene_existing", "expected_version": proposal["version"]}
    if expectation != "omitted":
        request["expected_current_draft_id"] = expectation
    result = client.post(
        f"/projects/{project}/proposals/{proposal['id']}/promote/draft", json=request
    )
    assert result.status_code == (200 if expectation == "omitted" else 409)
    if expectation != "omitted":
        assert (
            client.get(f"/projects/{project}/scenes/scene_existing/draft").json()["draft"]["id"]
            == saved["id"]
        )
        result = client.post(
            f"/projects/{project}/proposals/{proposal['id']}/promote/draft",
            json={**request, "expected_current_draft_id": saved["id"]},
        )
        assert result.status_code == 200


def test_composition_foreign_pinned_draft_rejected_before_provider(setup):
    client, _, project, provider, _ = setup
    saved = client.post(
        f"/projects/{project}/scenes/scene_existing/draft", json={"text": "作者正文。"}
    ).json()
    other = client.post("/projects", json={"title": "另一作品", "language": "zh-CN"}).json()[
        "project_id"
    ]
    response = client.post(
        f"/projects/{other}/composition-proposals",
        json={
            "instruction": "写作。",
            "scene_id": "scene_existing",
            "included_draft_id": saved["id"],
        },
    )
    assert response.status_code in {404, 409} and not provider.requests


def test_retry_against_archived_project_fails_closed(setup):
    _, _, project, _, captured = setup
    proposal = accept(setup, generate(setup))
    assert apply(setup, proposal).status_code == 200
    node = captured["graph"].nodes[project]
    captured["graph"].nodes[project] = node.model_copy(update={"status": "ARCHIVED"})
    assert apply(setup, proposal).status_code in {404, 409}


def test_english_composition_and_new_volume_output_language(setup):
    client, settings, _, provider, captured = setup
    project = client.post("/projects", json={"title": "A New Story", "language": "en-US"}).json()[
        "project_id"
    ]
    provider.override = lambda _: {
        "volume_title": "The Distant Harbor",
        "chapters": [
            {
                "title": "The Letter",
                "summary": "Mara finds a letter at the harbor.",
                "purpose": "Begin the journey.",
                "scenes": [
                    {
                        "title": "The Courier",
                        "summary": "The courier has vanished.",
                        "goal": "Find the courier.",
                        "conflict": "The gate is locked.",
                        "prose": "Mara folded the letter and slipped it into her pocket. The harbor bell rang once.",
                    }
                ],
            }
        ],
    }
    local_setup = (client, settings, project, provider, captured)
    proposal = generate(local_setup, scope="volume")
    assert proposal["content_language"] == "en-US"
    result = apply(local_setup, accept(local_setup, proposal))
    assert result.status_code == 200, result.text
    assert result.json()["drafts"][0]["content_language"] == "en-US"


def test_existing_foreign_volume_title_is_preserved_not_retranslated(setup):
    captured = setup[-1]
    graph = captured["graph"]
    node = graph.nodes["chapter_existing"]
    title = "The Very Long Journey Through the Mountains"
    graph.nodes[node.id] = node.model_copy(
        update={"properties": {**node.properties, "volume_index": 1, "volume_title": title}}
    )
    proposal = generate(setup)
    assert json.loads(proposal["body"])["volume_title"] == title
    assert apply(setup, accept(setup, proposal)).status_code == 200
