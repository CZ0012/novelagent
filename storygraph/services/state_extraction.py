"""Candidate fact extraction from draft text."""

from __future__ import annotations

import re

from storygraph.core.ids import new_id
from storygraph.core.time import utc_now
from storygraph.models.candidate import CandidateFact, ProposedGraphPatch, SourceSpan
from storygraph.models.common import EvidenceItem
from storygraph.models.draft import Draft


FACT_MARKER_RE = re.compile(r"\[\[fact:(?P<body>.*?)\]\]", re.DOTALL)


class RuleBasedStateExtractor:
    """Extracts explicit test/demo fact markers without inferring hidden intent."""

    def extract(self, *, project_id: str, draft: Draft) -> list[CandidateFact]:
        return self.extract_from_text(project_id=project_id, draft=draft, text=draft.text)

    def extract_from_text(
        self,
        *,
        project_id: str,
        draft: Draft,
        text: str,
        supporting_evidence: list[EvidenceItem] | None = None,
    ) -> list[CandidateFact]:
        candidates: list[CandidateFact] = []
        for match in FACT_MARKER_RE.finditer(text):
            raw_fields = self._parse_marker(match.group("body"))
            subject_id = raw_fields["subject"]
            relation = raw_fields["relation"]
            object_id = raw_fields.get("object")
            fact_type = raw_fields.get("fact_type", "CharacterRelationship")
            candidate_id = raw_fields.get("id", new_id("fact"))
            confidence = float(raw_fields.get("confidence", "0.8"))
            operation = raw_fields.get("operation", "create_relation" if object_id else "update_node")
            rationale = raw_fields.get(
                "rationale",
                "The draft explicitly marked this state change for extraction.",
            )
            patch_properties = self._patch_properties(raw_fields)
            patch = ProposedGraphPatch(
                operation=operation,  # type: ignore[arg-type]
                target=self._target(subject_id, relation, object_id),
                properties=patch_properties,
                source_ref=draft.id,
            )
            source_span = self._source_span(
                draft=draft,
                marker_text=match.group(0),
                marker_start=match.start(),
                marker_end=match.end(),
                quote=raw_fields.get("quote"),
            )
            candidates.append(
                CandidateFact(
                    id=candidate_id,
                    project_id=project_id,
                    fact_type=fact_type,
                    subject_id=subject_id,
                    relation=relation,
                    object_id=object_id,
                    value=raw_fields.get("value"),
                    source_scene_id=draft.scene_id,
                    source_draft_id=draft.id,
                    source_span=source_span,
                    confidence=confidence,
                    status="DRAFT_FACT",
                    rationale=rationale,
                    evidence=[
                        EvidenceItem(
                            kind="draft_text",
                            ref=draft.id,
                            quote=source_span.quote,
                            note="Explicit extraction marker.",
                        ),
                        *(supporting_evidence or []),
                    ],
                    proposed_graph_patch=patch,
                    created_at=utc_now(),
                )
            )
        return candidates

    @staticmethod
    def _parse_marker(body: str) -> dict[str, str]:
        fields: dict[str, str] = {}
        for part in body.split(";"):
            if not part.strip():
                continue
            key, sep, value = part.partition("=")
            if not sep:
                continue
            fields[key.strip()] = value.strip()
        missing = {"subject", "relation"} - set(fields)
        if missing:
            raise ValueError(f"Fact marker missing fields: {sorted(missing)}")
        return fields

    @staticmethod
    def _target(subject_id: str, relation: str, object_id: str | None) -> str:
        if object_id:
            return f"{subject_id} -> {relation} -> {object_id}"
        return subject_id

    @staticmethod
    def _patch_properties(fields: dict[str, str]) -> dict[str, str]:
        reserved = {
            "id",
            "fact_type",
            "subject",
            "relation",
            "object",
            "confidence",
            "operation",
            "rationale",
            "quote",
        }
        return {key: value for key, value in fields.items() if key not in reserved}

    @staticmethod
    def _source_span(
        *,
        draft: Draft,
        marker_text: str,
        marker_start: int,
        marker_end: int,
        quote: str | None,
    ) -> SourceSpan:
        normalized_quote = quote.strip() if quote else ""
        if normalized_quote:
            quote_start = draft.text.find(normalized_quote)
            if quote_start >= 0:
                return SourceSpan(
                    start_offset=quote_start,
                    end_offset=quote_start + len(normalized_quote),
                    quote=normalized_quote[:200],
                )
            return SourceSpan(
                start_offset=0,
                end_offset=0,
                quote=normalized_quote[:200],
            )
        return SourceSpan(
            start_offset=marker_start,
            end_offset=marker_end,
            quote=marker_text[:200],
        )
