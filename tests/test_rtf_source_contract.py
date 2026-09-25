"""RTF uses the existing private Source Store and cannot bypass its boundaries."""

from hashlib import sha256

from fastapi.testclient import TestClient

from apps.api.main import create_app
from storygraph.core.config import StoryGraphSettings


def test_rtf_source_import_restart_is_scoped_noncanon_and_text_free_in_lists(tmp_path):
    client = TestClient(create_app(StoryGraphSettings(tmp_path)))
    project = client.post("/projects", json={"title": "资料验收", "language": "zh-CN"}).json()
    project_id = project["project_id"]
    graph_before = (tmp_path / "graph.json").read_bytes()
    raw = b"{\\rtf1\\ansi Synthetic manuscript.}"
    payload = {
        "title": "资料",
        "relative_path": "设定/资料.RTF",
        "media_type": "application/rtf",
        "language": "en-US",
        "byte_size": len(raw),
        "checksum_sha256": sha256(raw).hexdigest(),
        "extraction_status": "ready",
        "extracted_text": "Synthetic manuscript.",
        "provenance": {"imported_by": "test-author", "imported_via": "local_file"},
    }
    response = client.post(f"/projects/{project_id}/sources", json=payload)
    assert response.status_code == 200
    document = response.json()["document"]
    assert "extracted_text" not in document
    assert document["media_type"] == "application/rtf"
    source_id = document["id"]
    assert (tmp_path / "graph.json").read_bytes() == graph_before
    client.close()

    restarted = TestClient(create_app(StoryGraphSettings(tmp_path)))
    detail = restarted.get(f"/projects/{project_id}/sources/{source_id}")
    assert detail.json()["extracted_text"] == payload["extracted_text"]
    assert "extracted_text" not in restarted.get(f"/projects/{project_id}/sources").json()["sources"][0]
    assert restarted.get(f"/projects/another_project/sources/{source_id}").status_code == 404
    mismatched = restarted.post(
        f"/projects/{project_id}/sources", json={**payload, "relative_path": "settings.txt"}
    )
    assert mismatched.status_code == 422
    assert (tmp_path / "graph.json").read_bytes() == graph_before
