from fastapi.testclient import TestClient

from apps.api.main import create_app
from storygraph.demo import PROJECT_ID


def test_context_and_manual_draft_reject_cross_project_scene_without_leaking_content():
    client = TestClient(create_app())
    project_id = client.post(
        "/projects",
        json={"title": "Scope Project", "language": "zh-CN"},
    ).json()["project_id"]
    chapter_id = "chapter_scope_private"
    scene_id = "scene_scope_private"
    client.post(
        f"/projects/{project_id}/chapters",
        json={
            "id": chapter_id,
            "title": "Scope Chapter",
            "chapter_index": 1,
            "reviewer": "author",
            "rationale": "Synthetic scope regression fixture.",
            "source_ref": "test:scope",
        },
    )
    scene = client.post(
        f"/projects/{project_id}/chapters/{chapter_id}/scenes",
        json={
            "id": scene_id,
            "title": "Scope Scene",
            "scene_index": 1,
            "goal": "PRIVATE_CROSS_PROJECT_SENTINEL",
            "reviewer": "author",
            "rationale": "Synthetic scope regression fixture.",
            "source_ref": "test:scope",
        },
    )
    assert scene.status_code == 200

    context = client.post(f"/projects/{PROJECT_ID}/scenes/{scene_id}/context-pack")
    draft = client.post(
        f"/projects/{PROJECT_ID}/scenes/{scene_id}/draft",
        json={"text": "PRIVATE_CROSS_PROJECT_DRAFT"},
    )

    assert context.status_code == 409
    assert "PRIVATE_CROSS_PROJECT_SENTINEL" not in context.text
    assert draft.status_code == 409
    cross_project_latest = client.get(
        f"/projects/{PROJECT_ID}/scenes/{scene_id}/draft"
    )
    assert cross_project_latest.status_code == 409
    assert client.get(f"/projects/{project_id}/scenes/{scene_id}/draft").json() == {
        "draft": None
    }
