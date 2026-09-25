"""Explicit verbatim Source-to-Draft adoption, never metadata reconstruction."""

import hashlib
import json

from pydantic import BaseModel, ConfigDict, Field

from storygraph.core.errors import GraphStoreError
from storygraph.core.time import utc_now
from storygraph.models.draft import Draft
from storygraph.services.project_language import resolve_project_output_language
from storygraph.services.graph_query import GraphQueryService
from storygraph.services.text_span import utf16_span
from storygraph.stores.memory_graph import InMemoryGraphStore


class SourceDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source_document_id: str = Field(min_length=1, max_length=200)
    expected_source_updated_at: str = Field(min_length=1, max_length=100)
    expected_source_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    expected_text: str = Field(min_length=1, max_length=200000)
    expected_current_draft_id: str | None = Field(..., min_length=1, max_length=200)


def adopt_source_draft(*, graph, source_store, draft_store, project_id, scene_id, request):
    if not isinstance(graph, InMemoryGraphStore):
        raise GraphStoreError(
            "source_adoption_backend_unsupported",
            "Source adoption currently requires the local JSON or memory graph.",
        )
    # Shared lock order: graph, source, draft. No reverse acquisition.
    with graph.persistence_guard(), source_store._lock:
        GraphQueryService(graph).scene_node(project_id=project_id, scene_id=scene_id)
        document = source_store.get(project_id=project_id, source_id=request.source_document_id)
        language = resolve_project_output_language(graph, project_id)
        if document.language != language:
            raise GraphStoreError(
                "source_language_mismatch",
                "Verbatim adoption requires the Source and project languages to match. Use the Source as an explicit Agent reference to generate translated prose.",
            )
        if (
            document.extraction_status != "ready"
            or not document.extracted_text
            or document.updated_at != request.expected_source_updated_at
            or document.checksum_sha256 != request.expected_source_checksum
        ):
            raise GraphStoreError(
                "source_stale", "The source changed; reload it before adopting text."
            )
        utf16_span(document.extracted_text, request.start, request.end, request.expected_text)
        provenance = {
            "kind": "source_document",
            "source_document_id": document.id,
            "source_checksum_sha256": document.checksum_sha256,
            "source_updated_at": document.updated_at,
            "extracted_text_sha256": hashlib.sha256(document.extracted_text.encode()).hexdigest(),
            "start": request.start,
            "end": request.end,
            "offset_unit": "utf16",
            "text_sha256": hashlib.sha256(request.expected_text.encode()).hexdigest(),
            "previous_draft_id": request.expected_current_draft_id,
        }
        identity = json.dumps([project_id, scene_id, provenance], sort_keys=True)
        now = utc_now()
        draft = Draft(
            id="draft_src_" + hashlib.sha256(identity.encode()).hexdigest()[:32],
            project_id=project_id,
            scene_id=scene_id,
            content_language=language,
            version=1,
            text=request.expected_text,
            provenance=provenance,
            created_at=now,
            updated_at=now,
        )
        return draft_store.adopt_source_if_current(
            draft, request.expected_current_draft_id
        ).model_dump()
