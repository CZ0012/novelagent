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
        candidates: list[CandidateFact] = []
        for match in FACT_MARKER_RE.finditer(draft.text):
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
                    source_span=SourceSpan(
                        start_offset=match.start(),
                        end_offset=match.end(),
                        quote=match.group(0)[:200],
                    ),
                    confidence=confidence,
                    status="DRAFT_FACT",
                    rationale=rationale,
                    evidence=[
                        EvidenceItem(
                            kind="draft_text",
                            ref=draft.id,
                            quote=match.group(0)[:200],
                            note="Explicit extraction marker.",
                        )
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
        }
        return {key: value for key, value in fields.items() if key not in reserved}
