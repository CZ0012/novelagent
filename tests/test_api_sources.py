from __future__ import annotations

from hashlib import sha256
import json
import sqlite3

from fastapi.testclient import TestClient

from apps.api.main import create_app
from storygraph.core.config import StoryGraphSettings
from storygraph.services.llm_provider import LLMResponse


def test_source_api_persists_across_app_restart_and_keeps_lists_text_free(tmp_path):
    settings = _json_settings(tmp_path)
    first_client = TestClient(create_app(settings))
    project_id = _create_project(first_client, "来源持久化项目")
    imported = first_client.post(
        f"/projects/{project_id}/sources",
        json=_source_payload(text="第一章\n星门在雨夜开启。"),
    )

    assert imported.status_code == 200
    created = imported.json()
    assert created["created"] is True
    assert created["updated"] is False
    assert "extracted_text" not in created["document"]
    assert created["document"]["character_count"] == len("第一章\n星门在雨夜开启。")
    source_id = created["document"]["id"]
    first_client.close()

    second_client = TestClient(create_app(_json_settings(tmp_path)))
    listed = second_client.get(f"/projects/{project_id}/sources")
    detail = second_client.get(f"/projects/{project_id}/sources/{source_id}")

    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["sources"]] == [source_id]
    assert "extracted_text" not in listed.json()["sources"][0]
    assert detail.status_code == 200
    assert detail.json()["extracted_text"] == "第一章\n星门在雨夜开启。"


def test_source_api_reports_idempotence_failed_retry_and_changed_content(tmp_path):
    client = TestClient(create_app(_json_settings(tmp_path)))
    project_id = _create_project(client, "来源幂等项目")
    original = _source_payload(
        text="同一份正文。",
        relative_path="设定集/世界观.MD",
    )
    first = client.post(f"/projects/{project_id}/sources", json=original).json()
    unchanged = client.post(
        f"/projects/{project_id}/sources",
        json={**original, "relative_path": "设定集\\世界观.md"},
    ).json()

    assert (first["created"], first["updated"]) == (True, False)
    assert (unchanged["created"], unchanged["updated"]) == (False, False)
    assert unchanged["document"]["id"] == first["document"]["id"]

    failed_bytes = b"synthetic-docx-source"
    failed_payload = _source_payload(
        text=None,
        relative_path="章节/损坏.docx",
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
        extraction_status="failed",
        original_bytes=failed_bytes,
        error="无法读取测试文档。",
    )
    failed = client.post(f"/projects/{project_id}/sources", json=failed_payload).json()
    recovered_payload = _source_payload(
        text="恢复后的章节正文。",
        relative_path="章节/损坏.docx",
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
        original_bytes=failed_bytes,
    )
    recovered = client.post(
        f"/projects/{project_id}/sources",
        json=recovered_payload,
    ).json()

    assert failed["document"]["extraction_status"] == "failed"
    assert (recovered["created"], recovered["updated"]) == (False, True)
    assert recovered["document"]["id"] == failed["document"]["id"]
    recovered_detail = client.get(
        f"/projects/{project_id}/sources/{recovered['document']['id']}"
    ).json()
    assert recovered_detail["extracted_text"] == "恢复后的章节正文。"
    assert recovered_detail["error"] is None

    changed = client.post(
        f"/projects/{project_id}/sources",
        json=_source_payload(
            text="正文发生变化。",
            relative_path="设定集/世界观.md",
        ),
    ).json()
    assert changed["created"] is True
    assert changed["document"]["id"] != first["document"]["id"]

    invalid = client.post(
        f"/projects/{project_id}/sources",
        json=_source_payload(text="   ", relative_path="空白.txt"),
    )
    unsafe = client.post(
        f"/projects/{project_id}/sources",
        json=_source_payload(
            text="无效请求中的私有正文不得回显。",
            relative_path="../private.md",
        ),
    )
    assert invalid.status_code == 422
    assert unsafe.status_code == 422
    assert "无效请求中的私有正文不得回显" not in unsafe.text
    assert len(client.get(f"/projects/{project_id}/sources").json()["sources"]) == 3


def test_source_api_enforces_project_scope_without_leaking_metadata(tmp_path):
    client = TestClient(create_app(_json_settings(tmp_path)))
    alpha_id = _create_project(client, "来源项目 Alpha")
    beta_id = _create_project(client, "来源项目 Beta")
    payload = _source_payload(text="Alpha 的私有正文。", relative_path="private/note.md")
    alpha_source = client.post(
        f"/projects/{alpha_id}/sources",
        json=payload,
    ).json()["document"]

    assert client.get(f"/projects/{beta_id}/sources").json()["sources"] == []
    detail = client.get(f"/projects/{beta_id}/sources/{alpha_source['id']}")
    archive = client.post(
        f"/projects/{beta_id}/sources/{alpha_source['id']}/archive"
    )
    structure = client.post(
        f"/projects/{beta_id}/sources/{alpha_source['id']}/structure-draft",
        json={},
    )

    assert detail.status_code == 404
    assert archive.status_code == 404
    assert structure.status_code == 404
    assert "Alpha 的私有正文" not in detail.text + archive.text + structure.text

    beta_source = client.post(f"/projects/{beta_id}/sources", json=payload).json()
    assert beta_source["created"] is True
    assert beta_source["document"]["id"] != alpha_source["id"]
    assert client.get("/projects/project_missing/sources").status_code == 404


def test_source_api_rejects_non_project_graph_nodes_and_oversized_metadata(tmp_path):
    client = TestClient(create_app(_json_settings(tmp_path)))
    project_id, scene_id = _create_project_with_scene(client, "来源边界项目")
    private_marker = "PRIVATE-METADATA-MARKER"

    wrong_scope = client.post(
        f"/projects/{scene_id}/sources",
        json=_source_payload(text="不能挂到 Scene 节点。"),
    )
    oversized_warning = client.post(
        f"/projects/{project_id}/sources",
        json={
            **_source_payload(text="合法正文。", relative_path="warning.md"),
            "warnings": [private_marker + ("x" * 220)],
        },
    )
    absolute_note = client.post(
        f"/projects/{project_id}/sources",
        json={
            **_source_payload(text="合法正文。", relative_path="note.md"),
            "provenance": {
                "imported_by": "author",
                "imported_via": "local_file",
                "note": r"Imported from C:\private\manuscript.md",
            },
        },
    )
    spoofed_extension = client.post(
        f"/projects/{project_id}/sources",
        json=_source_payload(
            text="不能把 PDF 伪装成纯文本。",
            relative_path="notes.pdf",
            media_type="text/plain",
        ),
    )

    assert wrong_scope.status_code == 404
    assert oversized_warning.status_code == 422
    assert absolute_note.status_code == 422
    assert spoofed_extension.status_code == 422
    assert private_marker not in oversized_warning.text
    assert r"C:\private\manuscript.md" not in absolute_note.text
    assert client.get(f"/projects/{project_id}/sources").json()["sources"] == []


def test_source_archive_is_idempotent_and_preserves_auditable_detail(tmp_path):
    client = TestClient(create_app(_json_settings(tmp_path)))
    project_id = _create_project(client, "来源归档项目")
    source = client.post(
        f"/projects/{project_id}/sources",
        json=_source_payload(text="归档后仍可审计的正文。"),
    ).json()["document"]

    first = client.post(f"/projects/{project_id}/sources/{source['id']}/archive")
    second = client.post(f"/projects/{project_id}/sources/{source['id']}/archive")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["extraction_status"] == "archived"
    assert second.json() == first.json()
    assert "extracted_text" not in first.json()
    assert client.get(f"/projects/{project_id}/sources").json()["sources"] == []
    audited = client.get(
        f"/projects/{project_id}/sources",
        params={"include_archived": True},
    ).json()["sources"]
    assert [item["id"] for item in audited] == [source["id"]]
    detail = client.get(f"/projects/{project_id}/sources/{source['id']}").json()
    assert detail["extraction_status"] == "archived"
    assert detail["extracted_text"] == "归档后仍可审计的正文。"
    assert client.post(
        f"/projects/{project_id}/sources/{source['id']}/structure-draft",
        json={},
    ).status_code == 409


def test_source_api_failed_reimport_preserves_archived_ready_text_until_ready_restore(
    tmp_path,
):
    client = TestClient(create_app(_json_settings(tmp_path)))
    project_id = _create_project(client, "归档重导项目")
    original_text = "必须保留用于审计的归档正文。"
    original_bytes = original_text.encode("utf-8")
    ready_payload = _source_payload(
        text=original_text,
        original_bytes=original_bytes,
    )
    source = client.post(
        f"/projects/{project_id}/sources",
        json=ready_payload,
    ).json()["document"]
    archived = client.post(
        f"/projects/{project_id}/sources/{source['id']}/archive"
    ).json()

    failed_retry = client.post(
        f"/projects/{project_id}/sources",
        json=_source_payload(
            text=None,
            extraction_status="failed",
            original_bytes=original_bytes,
            error="Retry extraction failed.",
        ),
    )

    assert failed_retry.status_code == 200
    failed_result = failed_retry.json()
    assert (failed_result["created"], failed_result["updated"]) == (False, False)
    assert failed_result["document"]["id"] == source["id"]
    assert failed_result["document"]["extraction_status"] == "archived"
    assert failed_result["document"]["updated_at"] == archived["updated_at"]
    assert client.get(f"/projects/{project_id}/sources").json()["sources"] == []
    preserved = client.get(
        f"/projects/{project_id}/sources/{source['id']}"
    ).json()
    assert preserved["extraction_status"] == "archived"
    assert preserved["extracted_text"] == original_text
    assert preserved["error"] is None

    ready_restore = client.post(
        f"/projects/{project_id}/sources",
        json=ready_payload,
    )

    assert ready_restore.status_code == 200
    restored_result = ready_restore.json()
    assert (restored_result["created"], restored_result["updated"]) == (False, True)
    assert restored_result["document"]["id"] == source["id"]
    assert restored_result["document"]["extraction_status"] == "ready"
    assert client.get(
        f"/projects/{project_id}/sources/{source['id']}"
    ).json()["extracted_text"] == original_text


def test_source_routes_apply_read_and_read_generate_permissions(tmp_path):
    client = TestClient(create_app(_json_settings(tmp_path)))
    project_id = _create_project(client, "来源权限项目")
    source = client.post(
        f"/projects/{project_id}/sources",
        json=_source_payload(text="权限测试正文。"),
    ).json()["document"]
    lowered = client.put(
        "/settings/agent",
        json={"scene_writer": "rule_based", "permission_level": "read_only"},
    )

    assert lowered.status_code == 200
    assert client.get(f"/projects/{project_id}/sources").status_code == 200
    assert client.get(f"/projects/{project_id}/sources/{source['id']}").status_code == 200
    assert client.post(
        f"/projects/{project_id}/sources",
        json=_source_payload(text="不能导入。", relative_path="blocked.txt"),
    ).status_code == 403
    assert client.post(
        f"/projects/{project_id}/sources/{source['id']}/archive"
    ).status_code == 403
    assert client.post(
        f"/projects/{project_id}/sources/{source['id']}/structure-draft",
        json={},
    ).status_code == 403


def test_source_structure_proposal_has_stable_ref_and_no_canon_side_effects(tmp_path):
    settings = _json_settings(tmp_path)
    client = TestClient(create_app(settings))
    project_id = _create_project(client, "来源结构项目")
    graph_before = client.get(f"/projects/{project_id}/graph/preview").json()
    graph_file_before = settings.graph_path.read_bytes()
    stores_before = _store_counts(settings)

    source = client.post(
        f"/projects/{project_id}/sources",
        json=_source_payload(
            title="结构资料.md",
            relative_path="大纲/结构资料.md",
            text=(
                "第一章 星门开启\n\n林瑾在雨夜抵达旧港。\n\n"
                "第二章 地下钟声\n\n众人在车站发现残缺年表。"
            ),
        ),
    ).json()["document"]

    assert _store_counts(settings) == stores_before
    assert settings.graph_path.read_bytes() == graph_file_before
    assert client.get(f"/projects/{project_id}/graph/preview").json() == graph_before

    created = client.post(
        f"/projects/{project_id}/sources/{source['id']}/structure-draft",
        json={"max_chapters": 4, "max_scenes_per_chapter": 3},
    )

    assert created.status_code == 200
    proposal = created.json()["proposal"]
    assert proposal["artifact_type"] == "project_structure_draft"
    assert [
        {key: ref[key] for key in ("kind", "ref", "note")}
        for ref in proposal["source_refs"]
    ] == [
        {
            "kind": "source_document",
            "ref": source["id"],
            "note": "结构资料.md",
        }
    ]
    stores_after_structure = _store_counts(settings)
    assert stores_after_structure["proposal_artifacts"] == (
        stores_before["proposal_artifacts"] + 1
    )
    for table in ("drafts", "candidate_facts", "workflow_runs"):
        assert stores_after_structure[table] == stores_before[table]
    assert client.get(f"/projects/{project_id}/facts/pending").json()["facts"] == []
    assert client.get(f"/projects/{project_id}/runs").json()["runs"] == []
    assert client.get(f"/projects/{project_id}/graph/preview").json() == graph_before
    assert settings.graph_path.read_bytes() == graph_file_before

    client.post(f"/projects/{project_id}/sources/{source['id']}/archive")
    assert _store_counts(settings) == stores_after_structure
    assert settings.graph_path.read_bytes() == graph_file_before


def test_llm_source_structure_fields_are_bounded_before_proposal_persistence(
    tmp_path,
    monkeypatch,
):
    long_text = "MODEL-COPIED-SOURCE-" + ("x" * 60_000)

    class FakeProvider:
        def generate(self, request):
            return LLMResponse(
                content=json.dumps(
                    {
                        "source_title": long_text,
                        "summary": long_text,
                        "chapters": [
                            {
                                "title": long_text,
                                "summary": long_text,
                                "purpose": long_text,
                                "scenes": [
                                    {
                                        "title": long_text,
                                        "summary": long_text,
                                        "goal": long_text,
                                        "conflict": long_text,
                                        "timeline_position": long_text,
                                        "pov_label": long_text,
                                        "location_label": long_text,
                                    }
                                ],
                            }
                        ],
                    }
                )
            )

    monkeypatch.setattr("apps.api.main.create_llm_provider", lambda settings: FakeProvider())
    client = TestClient(create_app(_llm_settings(tmp_path)))
    project_id = _create_project(client, "结构字段预算项目")
    source = client.post(
        f"/projects/{project_id}/sources",
        json=_source_payload(text="用于结构分析的短正文。"),
    ).json()["document"]

    response = client.post(
        f"/projects/{project_id}/sources/{source['id']}/structure-draft",
        json={},
    )

    assert response.status_code == 200
    body = response.json()["proposal"]["body"]
    outline = json.loads(body)
    scene = outline["chapters"][0]["scenes"][0]
    assert len(body) < 6_000
    assert len(outline["source_title"]) == 500
    assert len(outline["summary"]) == 1_000
    assert len(outline["chapters"][0]["summary"]) == 500
    assert len(scene["summary"]) == 500
    assert len(scene["goal"]) == 300
    assert len(scene["timeline_position"]) == 120


def test_agent_discussion_resolves_only_explicit_ready_source_ids_with_stable_refs(
    tmp_path,
    monkeypatch,
):
    captured_payload: dict = {}

    class FakeProvider:
        def generate(self, request):
            captured_payload.update(json.loads(request.messages[-1].content))
            return LLMResponse(
                content=json.dumps(
                    {
                        "reply": "已仅参考作者明确选择的资料。",
                        "proposal_title": "显式来源讨论",
                        "proposal_body": "# 讨论\n只生成非 canon 提案。",
                    },
                    ensure_ascii=False,
                )
            )

    monkeypatch.setattr("apps.api.main.create_llm_provider", lambda settings: FakeProvider())
    settings = _llm_settings(tmp_path)
    client = TestClient(create_app(settings))
    project_id, scene_id = _create_project_with_scene(client, "Agent 来源项目")
    selected = client.post(
        f"/projects/{project_id}/sources",
        json=_source_payload(
            title="已选择资料.md",
            relative_path="资料/已选择.md",
            text="主角此时尚不知道星门的代价。",
        ),
    ).json()["document"]
    unselected = client.post(
        f"/projects/{project_id}/sources",
        json=_source_payload(
            title="未选择资料.md",
            relative_path="资料/未选择.md",
            text="这份正文不能被隐式发送。",
        ),
    ).json()["document"]
    graph_before = client.get(f"/projects/{project_id}/graph/preview").json()
    graph_file_before = settings.graph_path.read_bytes()
    stores_before = _store_counts(settings)

    response = client.post(
        f"/projects/{project_id}/scenes/{scene_id}/agent-discussion",
        json={
            "mode": "discuss",
            "instruction": "这一幕应如何保持信息差？",
            "include_context_pack": False,
            "include_latest_draft": False,
            "source_document_ids": [selected["id"], selected["id"]],
            "local_sources": [
                {
                    "kind": "imported_document",
                    "ref": "legacy:note",
                    "title": "兼容资料.txt",
                    "text": "旧请求内联资料。",
                }
            ],
        },
    )

    assert response.status_code == 200
    persisted_sources = [
        item for item in captured_payload["local_sources"] if item["kind"] == "source_document"
    ]
    assert len(persisted_sources) == 1
    assert persisted_sources[0]["ref"] == selected["id"]
    assert persisted_sources[0]["text"] == "主角此时尚不知道星门的代价。"
    assert unselected["id"] not in json.dumps(captured_payload, ensure_ascii=False)
    proposal_refs = response.json()["proposal"]["source_refs"]
    source_document_refs = [ref for ref in proposal_refs if ref["kind"] == "source_document"]
    assert [ref["ref"] for ref in source_document_refs] == [selected["id"]]
    assert any(ref["ref"] == "legacy:note" for ref in proposal_refs)

    stores_after = _store_counts(settings)
    assert stores_after["proposal_artifacts"] == stores_before["proposal_artifacts"] + 1
    for table in ("drafts", "candidate_facts", "workflow_runs"):
        assert stores_after[table] == stores_before[table]
    assert client.get(f"/projects/{project_id}/scenes/{scene_id}/draft").json()["draft"] is None
    assert client.get(f"/projects/{project_id}/facts/pending").json()["facts"] == []
    assert client.get(f"/projects/{project_id}/graph/preview").json() == graph_before
    assert settings.graph_path.read_bytes() == graph_file_before


def test_agent_source_resolution_rejects_cross_project_and_failed_sources_before_llm(
    tmp_path,
    monkeypatch,
):
    calls = 0

    class FailIfCalledProvider:
        def generate(self, request):
            nonlocal calls
            calls += 1
            raise AssertionError("Provider must not run for invalid Source Documents.")

    monkeypatch.setattr(
        "apps.api.main.create_llm_provider",
        lambda settings: FailIfCalledProvider(),
    )
    settings = _llm_settings(tmp_path)
    client = TestClient(create_app(settings))
    alpha_id, alpha_scene = _create_project_with_scene(client, "Agent Alpha")
    beta_id, beta_scene = _create_project_with_scene(client, "Agent Beta")
    alpha_ready = client.post(
        f"/projects/{alpha_id}/sources",
        json=_source_payload(text="Alpha ready source.", relative_path="alpha.md"),
    ).json()["document"]
    alpha_failed = client.post(
        f"/projects/{alpha_id}/sources",
        json=_source_payload(
            text=None,
            relative_path="failed.md",
            extraction_status="failed",
            error="Synthetic extraction failure.",
        ),
    ).json()["document"]

    cross_project = client.post(
        f"/projects/{beta_id}/scenes/{beta_scene}/agent-discussion",
        json={
            "instruction": "Do not run.",
            "include_context_pack": False,
            "include_latest_draft": False,
            "source_document_ids": [alpha_ready["id"]],
        },
    )
    failed = client.post(
        f"/projects/{alpha_id}/scenes/{alpha_scene}/agent-discussion",
        json={
            "instruction": "Do not run.",
            "include_context_pack": False,
            "include_latest_draft": False,
            "source_document_ids": [alpha_failed["id"]],
        },
    )
    spoofed_inline_source = client.post(
        f"/projects/{alpha_id}/scenes/{alpha_scene}/agent-discussion",
        json={
            "instruction": "Do not run.",
            "include_context_pack": False,
            "include_latest_draft": False,
            "local_sources": [
                {
                    "kind": "source_document",
                    "ref": alpha_ready["id"],
                    "title": "Spoofed persisted source",
                    "text": "This inline text was not loaded from Source Store.",
                }
            ],
        },
    )

    assert cross_project.status_code == 404
    assert failed.status_code == 409
    assert spoofed_inline_source.status_code == 409
    assert calls == 0
    assert client.get(f"/projects/{alpha_id}/proposals").json()["proposals"] == []
    assert client.get(f"/projects/{beta_id}/proposals").json()["proposals"] == []


def _source_payload(
    *,
    text: str | None,
    title: str = "来源资料.md",
    relative_path: str = "资料/来源资料.md",
    media_type: str = "text/markdown",
    extraction_status: str = "ready",
    original_bytes: bytes | None = None,
    error: str | None = None,
) -> dict:
    source_bytes = original_bytes if original_bytes is not None else (text or "").encode("utf-8")
    return {
        "title": title,
        "relative_path": relative_path,
        "media_type": media_type,
        "language": "zh-CN",
        "byte_size": len(source_bytes),
        "checksum_sha256": sha256(source_bytes).hexdigest(),
        "extraction_status": extraction_status,
        "extracted_text": text,
        "warnings": ["Synthetic failed import."] if extraction_status == "failed" else [],
        "error": error,
        "provenance": {
            "imported_by": "author",
            "imported_via": "local_file",
            "source_last_modified_ms": 1_750_000_000_000,
            "note": "Synthetic API test fixture.",
        },
    }


def _create_project(client: TestClient, title: str) -> str:
    response = client.post("/projects", json={"title": title})
    assert response.status_code == 200
    return response.json()["project_id"]


def _create_project_with_scene(client: TestClient, title: str) -> tuple[str, str]:
    project_id = _create_project(client, title)
    chapter_id = f"{project_id}_chapter"
    scene_id = f"{project_id}_scene"
    chapter = client.post(
        f"/projects/{project_id}/chapters",
        json={
            "id": chapter_id,
            "title": "第一章",
            "reviewer": "author",
            "rationale": "Synthetic API test chapter.",
            "source_ref": "author_seed:test",
        },
    )
    scene = client.post(
        f"/projects/{project_id}/chapters/{chapter_id}/scenes",
        json={
            "id": scene_id,
            "title": "开场",
            "reviewer": "author",
            "rationale": "Synthetic API test scene.",
            "source_ref": "author_seed:test",
        },
    )
    assert chapter.status_code == 200
    assert scene.status_code == 200
    return project_id, scene_id


def _store_counts(settings: StoryGraphSettings) -> dict[str, int]:
    stores = {
        "drafts": settings.draft_store_path,
        "candidate_facts": settings.candidate_store_path,
        "proposal_artifacts": settings.proposal_store_path,
        "workflow_runs": settings.workflow_store_path,
    }
    counts: dict[str, int] = {}
    for table, path in stores.items():
        with sqlite3.connect(path) as connection:
            counts[table] = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return counts


def _json_settings(tmp_path) -> StoryGraphSettings:
    settings = StoryGraphSettings(tmp_path)
    settings.graph_backend = "json"
    settings.graph_backend_explicit = True
    settings.ensure_workspace()
    return settings


def _llm_settings(tmp_path) -> StoryGraphSettings:
    settings = _json_settings(tmp_path)
    settings.llm_base_url = "https://api.example.test/v1"
    settings.llm_api_key = "test-key"
    settings.llm_model = "test-model"
    return settings
