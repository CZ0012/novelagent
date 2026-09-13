import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from fastapi.testclient import TestClient

from apps.api.main import create_app
from storygraph.core.config import StoryGraphSettings
from storygraph.core.ids import slug_id


@pytest.mark.parametrize("collision_kind", ["chapter", "relationship"])
def test_structure_conflict_leaves_graph_and_proposal_unchanged(tmp_path, collision_kind):
    settings = StoryGraphSettings(tmp_path)
    settings.graph_backend = "json"
    settings.graph_backend_explicit = True
    client = TestClient(create_app(settings))
    project_id = client.post("/projects", json={"title": "Synthetic structure audit"}).json()[
        "project_id"
    ]
    created = client.post(
        f"/projects/{project_id}/chapters",
        json={
            "id": (
                slug_id("chapter", f"{project_id}_2_Existing")
                if collision_kind == "chapter"
                else "chapter_unrelated"
            ),
            "title": "Existing",
            "reviewer": "test_author",
            "rationale": "Create synthetic collision baseline.",
            "source_ref": "test:structure_baseline",
        },
    )
    assert created.status_code == 200
    if collision_kind == "relationship":
        first_chapter_id = slug_id("chapter", f"{project_id}_1_First")
        relation = client.post(
            f"/projects/{project_id}/relations",
            json={
                "id": slug_id("rel", f"{project_id}_HAS_CHAPTER_{first_chapter_id}"),
                "type": "HAS_CHAPTER",
                "source_id": project_id,
                "target_id": "chapter_unrelated",
                "reviewer": "test_author",
                "rationale": "Create synthetic relationship ID collision.",
                "source_ref": "test:structure_relation_baseline",
            },
        )
        assert relation.status_code == 200
    proposal = _accepted_proposal(client, project_id)
    graph_before = client.get(f"/projects/{project_id}/graph/preview").json()
    disk_before = settings.graph_path.read_bytes()

    applied = client.post(
        f"/projects/{project_id}/proposals/{proposal['id']}/apply/project-structure",
        json={
            "reviewer": "test_author",
            "rationale": "Apply synthetic test outline.",
            "expected_version": proposal["version"],
        },
    )

    assert applied.status_code == 409
    assert client.get(f"/projects/{project_id}/graph/preview").json() == graph_before
    assert settings.graph_path.read_bytes() == disk_before
    assert client.get(f"/projects/{project_id}/proposals/{proposal['id']}").json() == proposal


def test_structure_apply_concurrent_original_request_retries_are_idempotent(tmp_path):
    settings = StoryGraphSettings(tmp_path)
    client = TestClient(create_app(settings))
    project_id = client.post("/projects", json={"title": "Concurrent structure"}).json()[
        "project_id"
    ]
    proposal = _accepted_proposal(client, project_id)
    payload = {
        "reviewer": "test_author",
        "rationale": "Apply synthetic outline once.",
        "expected_version": proposal["version"],
    }
    barrier = Barrier(2)

    def apply():
        barrier.wait(timeout=10)
        return client.post(
            f"/projects/{project_id}/proposals/{proposal['id']}/apply/project-structure",
            json=payload,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: apply(), range(2)))

    assert [response.status_code for response in responses] == [200, 200]
    results = [response.json() for response in responses]
    assert sorted(result["already_applied"] for result in results) == [False, True]
    assert results[0]["proposal"] == results[1]["proposal"]
    assert results[0]["chapters"] == results[1]["chapters"]
    assert results[0]["scenes"] == results[1]["scenes"]
    graph_after = settings.graph_path.read_bytes()
    reopened = TestClient(create_app(StoryGraphSettings(tmp_path)))
    repeated = reopened.post(
        f"/projects/{project_id}/proposals/{proposal['id']}/apply/project-structure",
        json=payload,
    )
    assert repeated.status_code == 200
    assert repeated.json()["already_applied"] is True
    assert repeated.json()["proposal"] == results[0]["proposal"]
    assert settings.graph_path.read_bytes() == graph_after


def _accepted_proposal(client, project_id):
    created = client.post(
        f"/projects/{project_id}/proposals",
        json={
            "artifact_type": "project_structure_draft",
            "title": "Synthetic structure proposal",
            "body_format": "structured_json",
            "body": json.dumps(
                {
                    "chapters": [
                        {"title": "First", "scenes": [{"title": "Opening"}]},
                        {"title": "Existing", "scenes": []},
                    ]
                }
            ),
        },
    )
    assert created.status_code == 200
    proposal = created.json()
    accepted = client.post(
        f"/projects/{project_id}/proposals/{proposal['id']}/accept",
        json={"reviewer": "test_author", "expected_version": proposal["version"]},
    )
    assert accepted.status_code == 200
    return accepted.json()
