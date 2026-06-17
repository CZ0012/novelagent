"""Local deterministic style-sample retrieval store."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Protocol

from storygraph.core.errors import ContractError
from storygraph.models.style import StyleSample, StyleSampleMatch


TOKEN_RE = re.compile(r"[A-Za-z0-9_\u4e00-\u9fff]+")


class StyleSampleStore(Protocol):
    def add(self, sample: StyleSample) -> StyleSample:
        raise NotImplementedError

    def get(self, sample_id: str) -> StyleSample:
        raise NotImplementedError

    def search(
        self,
        *,
        project_id: str,
        query: str,
        pov: str | None = None,
        tone: str | None = None,
        dialogue_style: str | None = None,
        tags: list[str] | None = None,
        limit: int = 3,
    ) -> list[StyleSampleMatch]:
        raise NotImplementedError


class SQLiteStyleSampleStore(StyleSampleStore):
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self._lock = RLock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS style_samples (
                  id TEXT PRIMARY KEY,
                  project_id TEXT NOT NULL,
                  source_ref TEXT NOT NULL,
                  pov TEXT,
                  tone TEXT,
                  dialogue_style TEXT,
                  created_at TEXT NOT NULL,
                  payload_json TEXT NOT NULL
                )
                """
            )
            self._connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_style_samples_project
                ON style_samples(project_id, created_at, id)
                """
            )
            self._connection.commit()

    def add(self, sample: StyleSample) -> StyleSample:
        with self._lock:
            if self._exists(sample.id):
                raise ContractError(f"Duplicate StyleSample id: {sample.id}")
            self._connection.execute(
                """
                INSERT INTO style_samples
                (id, project_id, source_ref, pov, tone, dialogue_style, created_at, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sample.id,
                    sample.project_id,
                    sample.source_ref,
                    sample.pov,
                    sample.tone,
                    sample.dialogue_style,
                    sample.created_at,
                    sample.model_dump_json(),
                ),
            )
            self._connection.commit()
            return sample

    def get(self, sample_id: str) -> StyleSample:
        with self._lock:
            row = self._connection.execute(
                "SELECT payload_json FROM style_samples WHERE id = ?",
                (sample_id,),
            ).fetchone()
            if row is None:
                raise ContractError(f"StyleSample not found: {sample_id}")
            return StyleSample.model_validate_json(row["payload_json"])

    def search(
        self,
        *,
        project_id: str,
        query: str,
        pov: str | None = None,
        tone: str | None = None,
        dialogue_style: str | None = None,
        tags: list[str] | None = None,
        limit: int = 3,
    ) -> list[StyleSampleMatch]:
        if limit < 1:
            raise ContractError("style sample search limit must be >= 1")
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT payload_json FROM style_samples
                WHERE project_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (project_id,),
            ).fetchall()
        query_terms = _tokens(" ".join([query, pov or "", tone or "", dialogue_style or ""]))
        requested_tags = {tag.lower() for tag in tags or []}
        matches: list[StyleSampleMatch] = []
        for row in rows:
            sample = StyleSample.model_validate_json(row["payload_json"])
            score, matched_terms = _score_sample(
                sample,
                query_terms=query_terms,
                pov=pov,
                tone=tone,
                dialogue_style=dialogue_style,
                requested_tags=requested_tags,
            )
            if score > 0:
                matches.append(
                    StyleSampleMatch(
                        sample=sample,
                        score=score,
                        matched_terms=matched_terms,
                    )
                )
        return sorted(matches, key=lambda match: (-match.score, match.sample.id))[:limit]

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _exists(self, sample_id: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM style_samples WHERE id = ?",
            (sample_id,),
        ).fetchone()
        return row is not None


def _score_sample(
    sample: StyleSample,
    *,
    query_terms: set[str],
    pov: str | None,
    tone: str | None,
    dialogue_style: str | None,
    requested_tags: set[str],
) -> tuple[float, list[str]]:
    sample_text = " ".join(
        [
            sample.text,
            sample.summary or "",
            sample.pov or "",
            sample.tone or "",
            sample.dialogue_style or "",
            " ".join(sample.tags),
        ]
    )
    sample_terms = _tokens(sample_text)
    matched_terms = sorted(query_terms & sample_terms)
    score = float(len(matched_terms))
    if pov and sample.pov == pov:
        score += 2.0
    if tone and sample.tone == tone:
        score += 1.5
    if dialogue_style and sample.dialogue_style == dialogue_style:
        score += 1.0
    tag_overlap = requested_tags & {tag.lower() for tag in sample.tags}
    score += len(tag_overlap) * 0.5
    return score, matched_terms


def _tokens(text: str) -> set[str]:
    return {match.group(0).lower() for match in TOKEN_RE.finditer(text)}

