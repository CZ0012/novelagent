import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient

from apps.api.main import create_app
from storygraph.core.config import StoryGraphSettings
from storygraph.models.proposal import ProposalRef
from storygraph.stores.draft_store import SQLiteDraftStore
from storygraph.stores.proposal_store import SQLiteProposalStore


def test_exact_draft_read_returns_historical_draft_only_in_route_scope(tmp_path):
    settings = _json_settings(tmp_path)
    client = TestClient(create_app(settings))
    project_id = _create_project_with_scenes(
        client,
        title="Exact draft project",
        scene_ids=["scene_exact", "scene_sibling"],
    )
    other_project_id = _create_project_with_scenes(
        client,
        title="Other exact draft project",
        scene_ids=["scene_other_project"],
    )
    first = client.post(
        f"/projects/{project_id}/scenes/scene_exact/draft",
        json={"text": "EXACT_DRAFT_PRIVATE_SENTINEL", "summary": "Synthetic v1"},
    ).json()
    second = client.post(
        f"/projects/{project_id}/scenes/scene_exact/draft",
        json={"text": "Synthetic v2", "summary": "Synthetic v2"},
    ).json()

    direct_store = SQLiteDraftStore(settings.draft_store_path)
    direct_store.mark_discarded(first["id"])
    direct_store.close()

    exact = client.get(
        f"/projects/{project_id}/scenes/scene_exact/drafts/{first['id']}"
    )
    latest = client.get(f"/projects/{project_id}/scenes/scene_exact/draft")
    wrong_scene = client.get(
        f"/projects/{project_id}/scenes/scene_sibling/drafts/{first['id']}"
    )
    wrong_project = client.get(
        f"/projects/{other_project_id}/scenes/scene_other_project/drafts/{first['id']}"
    )
    missing = client.get(
        f"/projects/{project_id}/scenes/scene_exact/drafts/draft_missing"
    )
    missing_route_scene = client.get(
        f"/projects/{project_id}/scenes/scene_missing/drafts/{first['id']}"
    )

    assert exact.status_code == 200
    assert exact.json()["id"] == first["id"]
    assert exact.json()["version"] == 1
    assert exact.json()["discarded"] is True
    assert latest.json()["draft"]["id"] == second["id"]
    for response in [wrong_scene, wrong_project, missing, missing_route_scene]:
        assert response.status_code == 404
        assert "EXACT_DRAFT_PRIVATE_SENTINEL" not in response.text


def test_exact_draft_read_requires_read_permission_gate(tmp_path, monkeypatch):
    settings = _json_settings(tmp_path)
    client = TestClient(create_app(settings))
    project_id = _create_project_with_scenes(
        client,
        title="Draft read permission project",
        scene_ids=["scene_permission"],
    )
    draft = client.post(
        f"/projects/{project_id}/scenes/scene_permission/draft",
        json={"text": "READ_PERMISSION_PRIVATE_SENTINEL"},
    ).json()
    lowered = client.put(
        "/settings/agent",
        json={"scene_writer": "rule_based", "permission_level": "read_only"},
    )
    readable = client.get(
        f"/projects/{project_id}/scenes/scene_permission/drafts/{draft['id']}"
    )

    monkeypatch.setattr("apps.api.main.has_permission", lambda *_args: False)
    blocked = client.get(
        f"/projects/{project_id}/scenes/scene_permission/drafts/{draft['id']}"
    )

    assert lowered.status_code == 200
    assert readable.status_code == 200
    assert readable.json()["id"] == draft["id"]
    assert blocked.status_code == 403
    assert "READ_PERMISSION_PRIVATE_SENTINEL" not in blocked.text


def test_scene_draft_promotion_rejects_mismatch_ambiguity_and_foreign_scene_atomically(
    tmp_path,
):
    client = TestClient(create_app(_json_settings(tmp_path)))
    project_id = _create_project_with_scenes(
        client,
        title="Promotion target project",
        scene_ids=["scene_target", "scene_other"],
    )
    other_project_id = _create_project_with_scenes(
        client,
        title="Promotion foreign project",
        scene_ids=["scene_foreign"],
    )

    cases = [
        (
            "proposal_target_mismatch",
            [{"kind": "scene", "ref": "scene_target"}],
            "scene_other",
        ),
        (
            "proposal_target_ambiguous",
            [
                {"kind": "scene", "ref": "scene_target"},
                {"kind": "scene", "ref": "scene_other"},
            ],
            "scene_target",
        ),
        (
            "proposal_foreign_request_scene",
            [],
            "scene_foreign",
        ),
    ]
    for proposal_id, target_refs, request_scene_id in cases:
        accepted = _create_accepted_scene_proposal(
            client,
            project_id=project_id,
            proposal_id=proposal_id,
            target_refs=target_refs,
        )
        failed = client.post(
            f"/projects/{project_id}/proposals/{proposal_id}/promote/draft",
            json={
                "scene_id": request_scene_id,
                "expected_version": accepted["version"],
            },
        )
        stored = client.get(
            f"/projects/{project_id}/proposals/{proposal_id}"
        ).json()

        assert failed.status_code == 409
        assert "PROMOTION_TARGET_PRIVATE_SENTINEL" not in failed.text
        assert stored["version"] == accepted["version"]
        assert stored["derived_refs"] == []

    assert client.get(
        f"/projects/{project_id}/scenes/scene_target/draft"
    ).json() == {"draft": None}
    assert client.get(
        f"/projects/{project_id}/scenes/scene_other/draft"
    ).json() == {"draft": None}
    assert client.get(
        f"/projects/{other_project_id}/scenes/scene_foreign/draft"
    ).json() == {"draft": None}
    first_real_draft = client.post(
        f"/projects/{project_id}/scenes/scene_target/draft",
        json={"text": "First real target draft"},
    ).json()
    assert first_real_draft["version"] == 1


def test_scene_draft_promotion_is_repeat_safe_and_zero_target_compatible(tmp_path):
    client = TestClient(create_app(_json_settings(tmp_path)))
    project_id = _create_project_with_scenes(
        client,
        title="Repeat-safe promotion project",
        scene_ids=["scene_repeat_safe"],
    )
    accepted = _create_accepted_scene_proposal(
        client,
        project_id=project_id,
        proposal_id="proposal_repeat_safe",
        target_refs=[],
    )

    first = client.post(
        f"/projects/{project_id}/proposals/proposal_repeat_safe/promote/draft",
        json={
            "scene_id": "scene_repeat_safe",
            "expected_version": accepted["version"],
        },
    )
    repeated = client.post(
        f"/projects/{project_id}/proposals/proposal_repeat_safe/promote/draft",
        json={
            "scene_id": "scene_repeat_safe",
            "expected_version": accepted["version"],
        },
    )
    next_manual = client.post(
        f"/projects/{project_id}/scenes/scene_repeat_safe/draft",
        json={"text": "Manual draft after repeat-safe retry"},
    ).json()

    assert first.status_code == 200
    assert repeated.status_code == 200
    assert repeated.json()["draft"]["id"] == first.json()["draft"]["id"]
    assert repeated.json()["proposal"]["version"] == first.json()["proposal"]["version"]
    assert repeated.json()["proposal"]["derived_refs"] == first.json()["proposal"][
        "derived_refs"
    ]
    assert len(repeated.json()["proposal"]["derived_refs"]) == 1
    assert next_manual["version"] == 2


def test_scene_draft_promotion_treats_legacy_whitespace_scene_ref_as_zero_target(
    tmp_path,
):
    settings = _json_settings(tmp_path)
    client = TestClient(create_app(settings))
    project_id = _create_project_with_scenes(
        client,
        title="Whitespace target promotion project",
        scene_ids=["scene_whitespace_target"],
    )
    rejected_new = client.post(
        f"/projects/{project_id}/proposals",
        json={
            "id": "proposal_new_whitespace_target",
            "artifact_type": "scene_draft",
            "title": "Invalid whitespace target",
            "body": "Synthetic body.",
            "target_refs": [{"kind": "scene", "ref": "   "}],
        },
    )
    assert rejected_new.status_code == 422

    accepted = _create_accepted_scene_proposal(
        client,
        project_id=project_id,
        proposal_id="proposal_whitespace_target",
        target_refs=[],
    )
    connection = sqlite3.connect(settings.proposal_store_path)
    try:
        row = connection.execute(
            """
            SELECT payload_json FROM proposal_artifacts
            WHERE id = ? AND version = ?
            """,
            ("proposal_whitespace_target", accepted["version"]),
        ).fetchone()
        legacy_payload = json.loads(row[0])
        legacy_payload["target_refs"] = [{"kind": "scene", "ref": "   "}]
        connection.execute(
            """
            UPDATE proposal_artifacts SET payload_json = ?
            WHERE id = ? AND version = ?
            """,
            (
                json.dumps(legacy_payload, ensure_ascii=False),
                "proposal_whitespace_target",
                accepted["version"],
            ),
        )
        connection.commit()
    finally:
        connection.close()

    promoted = client.post(
        f"/projects/{project_id}/proposals/proposal_whitespace_target/promote/draft",
        json={
            "scene_id": "scene_whitespace_target",
            "expected_version": accepted["version"],
        },
    )

    assert promoted.status_code == 200
    assert promoted.json()["draft"]["scene_id"] == "scene_whitespace_target"
    assert promoted.json()["draft"]["version"] == 1
    assert promoted.json()["proposal"]["target_refs"] == []
    reloaded = client.get(
        f"/projects/{project_id}/proposals/proposal_whitespace_target"
    )
    assert reloaded.status_code == 200
    assert reloaded.json()["target_refs"] == []


def test_scene_draft_promotion_compensates_synchronous_derived_ref_failure(
    tmp_path,
    monkeypatch,
):
    settings = _json_settings(tmp_path)
    client = TestClient(create_app(settings))
    project_id = _create_project_with_scenes(
        client,
        title="Compensated promotion project",
        scene_ids=["scene_compensated"],
    )
    accepted = _create_accepted_scene_proposal(
        client,
        project_id=project_id,
        proposal_id="proposal_compensated",
        target_refs=[{"kind": "scene", "ref": "scene_compensated"}],
    )
    original_record_derived_ref = SQLiteProposalStore.record_derived_ref

    def fail_record_derived_ref(*_args, **_kwargs):
        raise RuntimeError("synthetic synchronous derived-ref failure")

    monkeypatch.setattr(
        SQLiteProposalStore,
        "record_derived_ref",
        fail_record_derived_ref,
    )
    failed = client.post(
        f"/projects/{project_id}/proposals/proposal_compensated/promote/draft",
        json={
            "scene_id": "scene_compensated",
            "expected_version": accepted["version"],
        },
    )
    stored_after_failure = client.get(
        f"/projects/{project_id}/proposals/proposal_compensated"
    ).json()
    direct_draft_store = SQLiteDraftStore(settings.draft_store_path)
    drafts_after_failure = direct_draft_store.list_versions(
        project_id,
        "scene_compensated",
    )
    direct_draft_store.close()

    assert failed.status_code == 409
    assert stored_after_failure["version"] == accepted["version"]
    assert stored_after_failure["derived_refs"] == []
    assert drafts_after_failure == []
    assert client.get(
        f"/projects/{project_id}/scenes/scene_compensated/draft"
    ).json() == {"draft": None}

    monkeypatch.setattr(
        SQLiteProposalStore,
        "record_derived_ref",
        original_record_derived_ref,
    )
    retried = client.post(
        f"/projects/{project_id}/proposals/proposal_compensated/promote/draft",
        json={
            "scene_id": "scene_compensated",
            "expected_version": accepted["version"],
        },
    )
    assert retried.status_code == 200
    assert retried.json()["draft"]["version"] == 1


def test_scene_draft_promotion_rolls_back_uncommitted_derived_version(
    tmp_path,
    monkeypatch,
):
    settings = _json_settings(tmp_path)
    client = TestClient(create_app(settings))
    project_id = _create_project_with_scenes(
        client,
        title="Uncommitted derived version project",
        scene_ids=["scene_uncommitted"],
    )
    accepted = _create_accepted_scene_proposal(
        client,
        project_id=project_id,
        proposal_id="proposal_uncommitted",
        target_refs=[{"kind": "scene", "ref": "scene_uncommitted"}],
    )
    original_insert = SQLiteProposalStore._insert

    def insert_then_raise(self, proposal):
        original_insert(self, proposal)
        if proposal.derived_refs:
            raise RuntimeError("synthetic failure after insert and before commit")

    monkeypatch.setattr(SQLiteProposalStore, "_insert", insert_then_raise)
    failed = client.post(
        f"/projects/{project_id}/proposals/proposal_uncommitted/promote/draft",
        json={
            "scene_id": "scene_uncommitted",
            "expected_version": accepted["version"],
        },
    )

    independent_proposals = SQLiteProposalStore(settings.proposal_store_path)
    durable_history = independent_proposals.history("proposal_uncommitted")
    independent_proposals.close()
    independent_drafts = SQLiteDraftStore(settings.draft_store_path)
    durable_drafts = independent_drafts.list_versions(project_id, "scene_uncommitted")
    independent_drafts.close()
    app_projection = client.get(
        f"/projects/{project_id}/proposals/proposal_uncommitted"
    ).json()

    assert failed.status_code == 409
    assert [proposal.version for proposal in durable_history] == [1, 2]
    assert all(proposal.derived_refs == [] for proposal in durable_history)
    assert durable_drafts == []
    assert app_projection["version"] == accepted["version"]
    assert app_projection["derived_refs"] == []


def test_scene_draft_promotion_recovers_when_commit_succeeded_before_exception(
    tmp_path,
    monkeypatch,
):
    settings = _json_settings(tmp_path)
    client = TestClient(create_app(settings))
    project_id = _create_project_with_scenes(
        client,
        title="Committed recovery project",
        scene_ids=["scene_committed_recovery"],
    )
    accepted = _create_accepted_scene_proposal(
        client,
        project_id=project_id,
        proposal_id="proposal_committed_recovery",
        target_refs=[{"kind": "scene", "ref": "scene_committed_recovery"}],
    )
    original_record_derived_ref = SQLiteProposalStore.record_derived_ref

    def commit_then_raise(self, *args, **kwargs):
        original_record_derived_ref(self, *args, **kwargs)
        raise RuntimeError("synthetic failure after durable commit")

    monkeypatch.setattr(
        SQLiteProposalStore,
        "record_derived_ref",
        commit_then_raise,
    )
    recovered = client.post(
        f"/projects/{project_id}/proposals/proposal_committed_recovery/promote/draft",
        json={
            "scene_id": "scene_committed_recovery",
            "expected_version": accepted["version"],
        },
    )

    independent_proposals = SQLiteProposalStore(settings.proposal_store_path)
    durable_proposal = independent_proposals.get("proposal_committed_recovery")
    independent_proposals.close()
    independent_drafts = SQLiteDraftStore(settings.draft_store_path)
    durable_drafts = independent_drafts.list_versions(
        project_id,
        "scene_committed_recovery",
    )
    independent_drafts.close()

    assert recovered.status_code == 200
    assert recovered.json()["proposal"]["version"] == accepted["version"] + 1
    assert len(durable_proposal.derived_refs) == 1
    assert len(durable_drafts) == 1
    assert recovered.json()["draft"]["id"] == durable_drafts[0].id
    assert durable_proposal.derived_refs[0].ref == durable_drafts[0].id


def test_scene_draft_promotion_serializes_same_payload_concurrently(tmp_path):
    settings = _json_settings(tmp_path)
    client = TestClient(create_app(settings))
    project_id = _create_project_with_scenes(
        client,
        title="Concurrent promotion project",
        scene_ids=["scene_concurrent"],
    )
    accepted = _create_accepted_scene_proposal(
        client,
        project_id=project_id,
        proposal_id="proposal_concurrent",
        target_refs=[{"kind": "scene", "ref": "scene_concurrent"}],
    )
    payload = {
        "scene_id": "scene_concurrent",
        "expected_version": accepted["version"],
    }
    start = Barrier(2)

    def promote():
        start.wait(timeout=5)
        return client.post(
            f"/projects/{project_id}/proposals/proposal_concurrent/promote/draft",
            json=payload,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _index: promote(), range(2)))

    draft_ids = {response.json()["draft"]["id"] for response in responses}
    direct_draft_store = SQLiteDraftStore(settings.draft_store_path)
    drafts = direct_draft_store.list_versions(project_id, "scene_concurrent")
    direct_draft_store.close()
    direct_proposal_store = SQLiteProposalStore(settings.proposal_store_path)
    history = direct_proposal_store.history("proposal_concurrent")
    direct_proposal_store.close()

    assert [response.status_code for response in responses] == [200, 200]
    assert len(draft_ids) == 1
    assert len(drafts) == 1
    assert drafts[0].id in draft_ids
    derived_versions = [proposal for proposal in history if proposal.derived_refs]
    assert len(derived_versions) == 1
    assert len(derived_versions[0].derived_refs) == 1
    assert derived_versions[0].derived_refs[0].ref == drafts[0].id


def test_scene_draft_promotion_fails_closed_for_corrupt_derived_draft_refs(tmp_path):
    settings = _json_settings(tmp_path)
    client = TestClient(create_app(settings))
    project_id = _create_project_with_scenes(
        client,
        title="Corrupt promotion project",
        scene_ids=["scene_corrupt_target", "scene_corrupt_other"],
    )
    other_scene_draft = client.post(
        f"/projects/{project_id}/scenes/scene_corrupt_other/draft",
        json={"text": "Wrong-scope existing draft"},
    ).json()
    proposal_store = SQLiteProposalStore(settings.proposal_store_path)
    cases = [
        ("proposal_missing_derived", ["draft_missing"]),
        ("proposal_multiple_derived", ["draft_missing_a", "draft_missing_b"]),
        ("proposal_wrong_scope_derived", [other_scene_draft["id"]]),
    ]
    try:
        for proposal_id, derived_draft_ids in cases:
            accepted = _create_accepted_scene_proposal(
                client,
                project_id=project_id,
                proposal_id=proposal_id,
                target_refs=[{"kind": "scene", "ref": "scene_corrupt_target"}],
            )
            with_refs = proposal_store.record_derived_refs(
                proposal_id,
                derived_refs=[
                    ProposalRef(kind="draft", ref=draft_id)
                    for draft_id in derived_draft_ids
                ],
                actor="synthetic-test",
                content_language=accepted["content_language"],
                expected_version=accepted["version"],
            )
            failed = client.post(
                f"/projects/{project_id}/proposals/{proposal_id}/promote/draft",
                json={
                    "scene_id": "scene_corrupt_target",
                    "expected_version": with_refs.version,
                },
            )
            stored = client.get(
                f"/projects/{project_id}/proposals/{proposal_id}"
            ).json()

            assert failed.status_code == 409
            assert "PROMOTION_TARGET_PRIVATE_SENTINEL" not in failed.text
            assert stored["version"] == with_refs.version
            assert [ref["ref"] for ref in stored["derived_refs"]] == derived_draft_ids
    finally:
        proposal_store.close()

    assert client.get(
        f"/projects/{project_id}/scenes/scene_corrupt_target/draft"
    ).json() == {"draft": None}


def _create_accepted_scene_proposal(
    client: TestClient,
    *,
    project_id: str,
    proposal_id: str,
    target_refs: list[dict],
) -> dict:
    created = client.post(
        f"/projects/{project_id}/proposals",
        json={
            "id": proposal_id,
            "artifact_type": "scene_draft",
            "title": "Synthetic scene proposal",
            "body": "PROMOTION_TARGET_PRIVATE_SENTINEL",
            "target_refs": target_refs,
        },
    )
    assert created.status_code == 200
    accepted = client.post(
        f"/projects/{project_id}/proposals/{proposal_id}/accept",
        json={"reviewer": "author", "expected_version": created.json()["version"]},
    )
    assert accepted.status_code == 200
    return accepted.json()


def _create_project_with_scenes(
    client: TestClient,
    *,
    title: str,
    scene_ids: list[str],
) -> str:
    project = client.post(
        "/projects",
        json={"title": title, "language": "zh-CN"},
    )
    assert project.status_code == 200
    project_id = project.json()["project_id"]
    chapter_id = f"{project_id}_chapter"
    chapter = client.post(
        f"/projects/{project_id}/chapters",
        json={
            "id": chapter_id,
            "title": "Synthetic chapter",
            "chapter_index": 1,
            "reviewer": "author",
            "rationale": "Synthetic draft scope fixture.",
            "source_ref": "test:draft-scope",
        },
    )
    assert chapter.status_code == 200
    for index, scene_id in enumerate(scene_ids, start=1):
        scene = client.post(
            f"/projects/{project_id}/chapters/{chapter_id}/scenes",
            json={
                "id": scene_id,
                "title": f"Synthetic scene {index}",
                "scene_index": index,
                "reviewer": "author",
                "rationale": "Synthetic draft scope fixture.",
                "source_ref": "test:draft-scope",
            },
        )
        assert scene.status_code == 200
    return project_id


def _json_settings(tmp_path) -> StoryGraphSettings:
    settings = StoryGraphSettings(tmp_path)
    settings.graph_backend = "json"
    settings.graph_backend_explicit = True
    settings.ensure_workspace()
    return settings
