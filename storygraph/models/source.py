"""Project-scoped imported source document models."""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Literal

from pydantic import Field, field_validator, model_validator

from storygraph.models.common import ContractModel


SourceMediaType = Literal[
    "text/plain",
    "text/markdown",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]
SourceExtractionStatus = Literal["ready", "failed", "archived"]


class SourceImportProvenance(ContractModel):
    imported_by: str = Field(..., min_length=1, max_length=100)
    imported_via: Literal["local_file"] = "local_file"
    source_last_modified_ms: int | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=300)

    @field_validator("imported_by")
    @classmethod
    def imported_by_has_no_absolute_path(cls, value: str) -> str:
        return _safe_metadata_text(value, field_name="provenance.imported_by") or ""

    @field_validator("note")
    @classmethod
    def note_has_no_absolute_path(cls, value: str | None) -> str | None:
        return _safe_metadata_text(value, field_name="provenance.note")


class SourceDocumentSummary(ContractModel):
    """Source metadata safe for list responses; never contains extracted prose."""

    contract_version: Literal["source_document_v1"] = "source_document_v1"
    id: str = Field(..., max_length=200)
    project_id: str = Field(..., max_length=200)
    title: str = Field(..., max_length=500)
    relative_path: str = Field(..., max_length=2048)
    media_type: SourceMediaType
    language: str = Field(..., max_length=35)
    byte_size: int = Field(ge=0)
    checksum_sha256: str
    extraction_status: SourceExtractionStatus
    character_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list, max_length=32)
    error: str | None = Field(default=None, max_length=500)
    provenance: SourceImportProvenance
    created_at: str
    updated_at: str

    @field_validator("id", "project_id", "title", "language", "created_at", "updated_at")
    @classmethod
    def required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("source document fields cannot be empty")
        return value

    @field_validator("relative_path")
    @classmethod
    def relative_path_only(cls, value: str) -> str:
        normalized = value.strip().replace("\\", "/")
        if not normalized or normalized.startswith("/"):
            raise ValueError("relative_path must be a non-empty relative path")
        if len(normalized) >= 2 and normalized[1] == ":":
            raise ValueError("relative_path must not contain a drive prefix")
        raw_parts = normalized.split("/")
        if any(part in {".", ".."} for part in raw_parts):
            raise ValueError("relative_path must not escape the source root")
        parts = [part for part in raw_parts if part]
        if not parts:
            raise ValueError("relative_path must be a non-empty relative path")
        return "/".join(parts)

    @field_validator("checksum_sha256")
    @classmethod
    def valid_sha256(cls, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(character not in "0123456789abcdef" for character in normalized):
            raise ValueError("checksum_sha256 must contain 64 hexadecimal characters")
        return normalized

    @field_validator("warnings")
    @classmethod
    def bounded_safe_warnings(cls, value: list[str]) -> list[str]:
        normalized = [
            _safe_metadata_text(item, field_name="warning")
            for item in value
        ]
        warnings = [item for item in normalized if item is not None]
        if any(not item for item in warnings):
            raise ValueError("source document warnings cannot be empty")
        if any(len(item) > 200 for item in warnings) or sum(map(len, warnings)) > 2000:
            raise ValueError("source document warnings exceed the metadata budget")
        return warnings

    @field_validator("error")
    @classmethod
    def bounded_safe_error(cls, value: str | None) -> str | None:
        return _safe_metadata_text(value, field_name="error")

    @model_validator(mode="after")
    def media_type_matches_file_extension(self) -> "SourceDocumentSummary":
        extension = PurePosixPath(self.relative_path).suffix.casefold()
        expected_extensions = {
            "text/plain": {".txt"},
            "text/markdown": {".md", ".markdown"},
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {
                ".docx"
            },
        }
        if extension not in expected_extensions[self.media_type]:
            raise ValueError("source media_type does not match the relative_path extension")
        return self


class SourceDocument(SourceDocumentSummary):
    """Persisted local source text that is neither draft nor canon."""

    extracted_text: str | None = None

    @model_validator(mode="after")
    def extraction_fields_match_status(self) -> "SourceDocument":
        expected_character_count = len(self.extracted_text or "")
        if self.character_count != expected_character_count:
            raise ValueError("character_count must equal the extracted_text length")
        if self.extraction_status == "ready" and not (self.extracted_text or "").strip():
            raise ValueError("ready source documents require non-empty extracted_text")
        if self.extraction_status == "failed":
            if self.extracted_text:
                raise ValueError("failed source documents cannot contain extracted_text")
            if not self.error:
                raise ValueError("failed source documents require error")
        return self

    def to_summary(self) -> SourceDocumentSummary:
        return SourceDocumentSummary.model_validate(self.model_dump(exclude={"extracted_text"}))


_ABSOLUTE_PATH_PATTERN = re.compile(
    r"(?:file://|(?:^|[\s\"'(])(?:[A-Za-z]:[\\/]|\\\\|/(?:[^/\s]+/)+[^/\s]*))",
    re.IGNORECASE,
)


def _safe_metadata_text(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if _ABSOLUTE_PATH_PATTERN.search(normalized):
        raise ValueError(f"{field_name} must not contain an absolute local path")
    return normalized
