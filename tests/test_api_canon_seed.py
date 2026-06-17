from fastapi.testclient import TestClient

from apps.api.main import create_app
from storygraph.demo import PROJECT_ID


def test_api_author_seed_character_location_and_relation():
    client = TestClient(create_app())

    character = client.post(
        f"/projects/{PROJECT_ID}/characters",
        json={
            "id": "character_mara",
            "name": "Mara",
            "properties": {"role": "scout"},
            "reviewer": "editor",
            "rationale": "Seeded from story bible.",
            "source_ref": "author_seed:story_bible_v1",
        },
    )
    location = client.post(
        f"/projects/{PROJECT_ID}/locations",
        json={
            "id": "location_harbor",
            "name": "Harbor",
            "properties": {"type": "port"},
            "reviewer": "editor",
            "rationale": "Seeded from story bible.",
            "source_ref": "author_seed:story_bible_v1",
        },
    )
    relation = client.post(
        f"/projects/{PROJECT_ID}/relations",
        json={
            "id": "rel_mara_located_at_harbor",
            "type": "LOCATED_AT",
            "source_id": "character_mara",
            "target_id": "location_harbor",
            "properties": {"scene_id": "scene_seed"},
            "reviewer": "editor",
            "rationale": "Author placed Mara at the harbor.",
            "source_ref": "author_seed:story_bible_v1",
        },
    )

    assert character.status_code == 200
    assert character.json()["status"] == "CANON"
    assert character.json()["reviewer"] == "editor"
    assert character.json()["rationale"] == "Seeded from story bible."
    assert character.json()["source_ref"] == "author_seed:story_bible_v1"
    assert character.json()["event_id"]
    assert character.json()["properties"]["project_id"] == PROJECT_ID
    assert character.json()["properties"]["role"] == "scout"
    assert location.status_code == 200
    assert location.json()["type"] == "Location"
    assert relation.status_code == 200
    assert relation.json()["status"] == "CANON"
    assert relation.json()["source_id"] == "character_mara"
    assert relation.json()["target_id"] == "location_harbor"
    assert relation.json()["properties"]["project_id"] == PROJECT_ID

    pending = client.get(f"/projects/{PROJECT_ID}/facts/pending")
    assert pending.status_code == 200
    assert pending.json()["facts"] == []


def test_api_author_seed_rejects_duplicate_and_invalid_relation():
    client = TestClient(create_app())
    body = {
        "id": "character_duplicate_seed",
        "name": "Duplicate Seed",
        "reviewer": "editor",
        "rationale": "Seeded from story bible.",
        "source_ref": "author_seed:story_bible_v1",
    }

    first = client.post(f"/projects/{PROJECT_ID}/characters", json=body)
    duplicate = client.post(f"/projects/{PROJECT_ID}/characters", json=body)
    invalid_relation = client.post(
        f"/projects/{PROJECT_ID}/relations",
        json={
            "id": "rel_invalid_seed",
            "type": "FRIENDS",
            "source_id": "character_duplicate_seed",
            "target_id": "character_linj",
            "reviewer": "editor",
            "rationale": "Unsupported relation should fail.",
            "source_ref": "author_seed:story_bible_v1",
        },
    )
    missing_endpoint = client.post(
        f"/projects/{PROJECT_ID}/relations",
        json={
            "id": "rel_missing_endpoint",
            "type": "KNOWS",
            "source_id": "character_duplicate_seed",
            "target_id": "character_missing_seed",
            "reviewer": "editor",
            "rationale": "Missing endpoint should fail.",
            "source_ref": "author_seed:story_bible_v1",
        },
    )

    assert first.status_code == 200
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["category"] == "duplicate_id"
    assert invalid_relation.status_code == 409
    assert invalid_relation.json()["detail"]["category"] == "conflict_detected"
    assert missing_endpoint.status_code == 404
    assert missing_endpoint.json()["detail"]["category"] == "not_found"

