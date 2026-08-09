from __future__ import annotations

from hashlib import sha256

import pytest
from pydantic import ValidationError

from storygraph.core.config import StoryGraphSettings
from storygraph.core.errors import ContractError
from storygraph.models.source import SourceDocument, SourceImportProvenance
from storygraph.stores.source_store import SQLiteSourceDocumentStore


def test_source_store_persists_project_scoped_summaries_without_text(tmp_path):
    store_path = tmp_path / "sources.sqlite"
    first = SQLiteSourceDocumentStore(store_path)
    created = first.create_or_get(_source("source_alpha", project_id="project_alpha"))
    document = created.document
    first.close()

    second = SQLiteSourceDocumentStore(store_path)
    summaries = second.list(project_id="project_alpha")

    assert [summary.id for summary in summaries] == [document.id]
    assert "extracted_text" not in summaries[0].model_dump()
    assert second.get(project_id="project_alpha", source_id=document.id).extracted_text == (
        "A short synthetic chapter."
    )
    with pytest.raises(ContractError, match="SourceDocument not found"):
        second.get(project_id="project_beta", source_id=document.id)


def test_source_store_create_or_get_is_idempotent_by_normalized_path_and_checksum(tmp_path):
    store = SQLiteSourceDocumentStore(tmp_path / "sources.sqlite")
    original_result = store.create_or_get(
        _source("source_original", relative_path="Volume One/Chapter.MD")
    )
    retried_result = store.create_or_get(
        _source("source_retry", relative_path="volume one\\chapter.md")
    )

    assert original_result.created is True
    assert original_result.updated is False
    assert retried_result.created is False
    assert retried_result.updated is False
    assert retried_result.document.id == original_result.document.id
    assert [summary.id for summary in store.list(project_id="project_alpha")] == [
        original_result.document.id
    ]


def test_source_store_never_reuses_an_import_across_projects(tmp_path):
    store = SQLiteSourceDocumentStore(tmp_path / "sources.sqlite")
    alpha = store.create_or_get(
        _source("shared_id", project_id="project_alpha")
    ).document
    beta = store.create_or_get(
        _source("shared_id", project_id="project_beta")
    ).document

    assert alpha.project_id == "project_alpha"
    assert beta.project_id == "project_beta"
    assert [item.project_id for item in store.list(project_id="project_alpha")] == [
        "project_alpha"
    ]
    assert [item.project_id for item in store.list(project_id="project_beta")] == [
        "project_beta"
    ]


def test_source_store_changed_checksum_at_same_path_creates_a_new_record(tmp_path):
    store = SQLiteSourceDocumentStore(tmp_path / "sources.sqlite")
    first = store.create_or_get(_source("source_v1", original_bytes=b"version-one"))
    second = store.create_or_get(_source("source_v2", original_bytes=b"version-two"))

    assert first.created is True
    assert second.created is True
    assert second.document.id != first.document.id
    assert [item.id for item in store.list(project_id="project_alpha")] == [
        "source_v1",
        "source_v2",
    ]


def test_source_store_retry_can_recover_failed_extraction_without_duplicate(tmp_path):
    store = SQLiteSourceDocumentStore(tmp_path / "sources.sqlite")
    failed = store.create_or_get(
        _source(
            "source_failed",
            status="failed",
            extracted_text=None,
            warnings=["Synthetic extraction failure."],
        )
    ).document
    recovered = store.create_or_get(_source("source_retry"))

    assert recovered.created is False
    assert recovered.updated is True
    assert recovered.document.id == failed.id
    assert recovered.document.extraction_status == "ready"
    assert recovered.document.extracted_text == "A short synthetic chapter."
    assert len(store.list(project_id="project_alpha")) == 1


def test_source_store_archives_without_deleting_and_hides_archived_by_default(tmp_path):
    store = SQLiteSourceDocumentStore(tmp_path / "sources.sqlite")
    document = store.create_or_get(_source("source_archive")).document

    archived = store.archive(project_id=document.project_id, source_id=document.id)

    assert archived.extraction_status == "archived"
    assert store.list(project_id=document.project_id) == []
    assert [
        summary.id
        for summary in store.list(project_id=document.project_id, include_archived=True)
    ] == [document.id]
    assert store.get(project_id=document.project_id, source_id=document.id).id == document.id

    restored = store.create_or_get(_source("source_reimport", relative_path=document.relative_path))

    assert restored.created is False
    assert restored.updated is True
    assert restored.document.id == document.id
    assert restored.document.extraction_status == "ready"
    assert [item.id for item in store.list(project_id=document.project_id)] == [document.id]


def test_source_store_failed_reimport_does_not_overwrite_archived_ready_text(tmp_path):
    store = SQLiteSourceDocumentStore(tmp_path / "sources.sqlite")
    original = store.create_or_get(_source("source_auditable")).document
    archived = store.archive(project_id=original.project_id, source_id=original.id)

    failed_retry = store.create_or_get(
        _source(
            "source_failed_retry",
            relative_path=original.relative_path,
            status="failed",
            extracted_text=None,
            warnings=["Synthetic retry extraction failure."],
            error="Retry could not extract text.",
        )
    )

    assert failed_retry.created is False
    assert failed_retry.updated is False
    assert failed_retry.document.id == original.id
    assert failed_retry.document.extraction_status == "archived"
    assert failed_retry.document.extracted_text == "A short synthetic chapter."
    assert failed_retry.document.error is None
    assert failed_retry.document.updated_at == archived.updated_at
    persisted = store.get(project_id=original.project_id, source_id=original.id)
    assert persisted == failed_retry.document
    assert store.list(project_id=original.project_id) == []


def test_source_document_rejects_unsupported_media_type_and_unsafe_paths():
    with pytest.raises(ValidationError):
        _source("source_pdf", media_type="pdf")
    with pytest.raises(ValidationError):
        _source("source_escape", relative_path="../private.txt")
    with pytest.raises(ValidationError):
        _source("source_blank", extracted_text="   ")
    with pytest.raises(ValidationError):
        _source("source_failed_without_error", status="failed", extracted_text=None, error=None)
    with pytest.raises(ValidationError):
        _source("source_spoofed_pdf", relative_path="notes.pdf", media_type="text/plain")
    with pytest.raises(ValidationError):
        _source(
            "source_wsl_path",
            provenance={
                "imported_by": "author",
                "imported_via": "local_file",
                "note": "Imported from /mnt/c/private/notes.txt",
            },
        )


@pytest.mark.parametrize(
    ("media_type", "relative_path"),
    [
        ("text/plain", "notes.txt"),
        ("text/markdown", "notes.md"),
        (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "notes.docx",
        ),
    ],
)
def test_source_document_accepts_initial_contract_media_types(media_type, relative_path):
    assert (
        _source(
            "source_supported",
            media_type=media_type,
            relative_path=relative_path,
        ).media_type
        == media_type
    )


def test_storygraph_settings_exposes_source_store_path(tmp_path):
    settings = StoryGraphSettings(tmp_path)

    assert settings.source_store_path == tmp_path / "sources.sqlite"


def _source(
    source_id: str,
    *,
    project_id: str = "project_alpha",
    relative_path: str = "chapters/opening.md",
    media_type: str = "text/markdown",
    status: str = "ready",
    extracted_text: str | None = "A short synthetic chapter.",
    warnings: list[str] | None = None,
    error: str | None = "Synthetic extraction failure.",
    original_bytes: bytes = b"synthetic-source-file-bytes",
    provenance: SourceImportProvenance | dict | None = None,
) -> SourceDocument:
    return SourceDocument(
        id=source_id,
        project_id=project_id,
        title="Synthetic opening",
        relative_path=relative_path,
        media_type=media_type,
        language="en",
        byte_size=len(original_bytes),
        checksum_sha256=sha256(original_bytes).hexdigest(),
        extraction_status=status,
        extracted_text=extracted_text,
        character_count=len(extracted_text or ""),
        warnings=warnings or [],
        error=error if status == "failed" else None,
        provenance=provenance
        or SourceImportProvenance(
            imported_by="author",
            imported_via="local_file",
            source_last_modified_ms=1_750_000_000_000,
            note="Synthetic fixture import.",
        ),
        created_at="2026-08-09T00:00:00Z",
        updated_at="2026-08-09T00:00:00Z",
    )
