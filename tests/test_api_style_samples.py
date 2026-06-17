from fastapi.testclient import TestClient

from apps.api.main import create_app
from storygraph.demo import PROJECT_ID, SCENE_ID


def test_api_style_sample_ingest_feeds_context_pack():
    client = TestClient(create_app())

    sample = client.post(
        f"/projects/{PROJECT_ID}/style-samples",
        json={
            "id": "style_api_tower",
            "text": "Cold restrained tower prose with short lines and subtext.",
            "source_ref": "author_style:chapter_001",
            "pov": "third-person limited",
            "tone": "cold and restrained",
            "dialogue_style": "short lines with subtext",
            "tags": ["tower", "clue"],
        },
    )
    pack = client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/context-pack")

    assert sample.status_code == 200
    assert sample.json()["contract_version"] == "style_sample_v1"
    assert pack.status_code == 200
    assert pack.json()["retrieved_style_samples"] == [
        "style_api_tower: Cold restrained tower prose with short lines and subtext."
    ]
    assert pack.json()["provenance"]["style_sample_refs"] == ["style_api_tower"]

