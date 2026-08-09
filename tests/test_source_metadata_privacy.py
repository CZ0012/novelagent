import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from apps.api.main import create_app
from storygraph.models.proposal import ProposalRef


@pytest.mark.parametrize(
    ("path", "payload", "private_path"),
    [
        (
            "/projects/missing/imports/structure-draft",
            {
                "title": "Synthetic source",
                "text": "Synthetic text",
                "source_language": "en-US",
            },
            r"C:\Users\private\manuscript.txt",
        ),
        (
            "/projects/missing/scenes/missing/extract-document-facts",
            {
                "title": "Synthetic source",
                "text": "Synthetic text",
                "source_language": "en-US",
            },
            r"\\server\private\manuscript.txt",
        ),
        (
            "/projects/missing/scenes/missing/agent-discussion",
            {
                "instruction": "Discuss the selected source.",
                "include_context_pack": False,
                "include_latest_draft": False,
                "local_sources": [
                    {
                        "kind": "imported_document",
                        "title": "Synthetic source",
                        "text": "Synthetic text",
                        "language": "en-US",
                    }
                ],
            },
            "/home/private/manuscript.txt",
        ),
    ],
)
def test_legacy_source_metadata_rejects_absolute_paths_without_echo(
    path,
    payload,
    private_path,
):
    client = TestClient(create_app())
    if "local_sources" in payload:
        payload["local_sources"][0]["ref"] = private_path
    else:
        payload["source_ref"] = private_path

    response = client.post(path, json=payload)

    assert response.status_code == 422
    assert private_path not in response.text


@pytest.mark.parametrize(
    "field_value",
    [
        {"quote": r"C:\Users\synthetic\private.txt"},
        {"source_span": {"file": r"\\server\synthetic\private.txt"}},
        {"source_span": {"file": "/home/synthetic/private.txt"}},
        {"source_span": {r"C:\Users\synthetic\private.txt": 1}},
        {"source_span": {"nested": {r"\\server\synthetic\private.txt": 1}}},
        {"source_span": {"note": "x" * 2001}},
    ],
)
def test_proposal_ref_rejects_private_or_unbounded_source_metadata(field_value):
    with pytest.raises(ValidationError):
        ProposalRef(kind="source_document", ref="source_demo", **field_value)


@pytest.mark.parametrize(
    ("source_ref", "private_value"),
    [
        (
            {"kind": "source_document", "ref": "source_demo", "quote": None},
            r"C:\Users\synthetic\private.txt",
        ),
        (
            {
                "kind": "source_document",
                "ref": "source_demo",
                "source_span": {"file": None},
            },
            r"\\server\synthetic\private.txt",
        ),
        (
            {
                "kind": "source_document",
                "ref": "source_demo",
                "source_span": {"nested": {}},
            },
            r"C:\Users\synthetic\private.txt",
        ),
    ],
)
def test_proposal_api_rejects_private_ref_metadata_without_echo(
    source_ref,
    private_value,
):
    client = TestClient(create_app())
    if "quote" in source_ref:
        source_ref["quote"] = private_value
    elif "nested" in source_ref["source_span"]:
        source_ref["source_span"]["nested"][private_value] = 1
    else:
        source_ref["source_span"]["file"] = private_value

    response = client.post(
        "/projects/missing/proposals",
        json={
            "artifact_type": "scene_rebuild",
            "title": "Synthetic proposal",
            "source_refs": [source_ref],
        },
    )

    assert response.status_code == 422
    assert private_value not in response.text


def test_proposal_ref_quote_is_bounded():
    with pytest.raises(ValidationError):
        ProposalRef(
            kind="source_document",
            ref="source_demo",
            quote="x" * 501,
        )
