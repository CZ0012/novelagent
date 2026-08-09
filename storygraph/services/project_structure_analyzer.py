"""Project-level imported manuscript structure analysis."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
from typing import Any

from storygraph.core.errors import ContractError
from storygraph.models.project import CrossLanguagePolicy, OutputLanguage, localized
from storygraph.services.llm_provider import LLMMessage, LLMProvider, LLMRequest
from storygraph.services.project_language import (
    authoritative_language_message,
    enforce_source_language_policy,
    validate_generated_output_language,
)


@dataclass(frozen=True)
class ProjectStructureDraft:
    body: str
    outline: dict[str, Any]
    truncated: bool
    created_via: str


class RuleBasedProjectStructureAnalyzer:
    """Deterministic fallback for local tests and unconfigured workspaces."""

    def __init__(
        self,
        *,
        output_language: OutputLanguage,
        max_source_chars: int = 40000,
        max_chapters: int = 12,
        max_scenes_per_chapter: int = 8,
    ) -> None:
        self.output_language = output_language
        self.max_source_chars = max_source_chars
        self.max_chapters = max_chapters
        self.max_scenes_per_chapter = max_scenes_per_chapter

    def analyze(
        self,
        *,
        project_id: str,
        title: str,
        source_text: str,
        source_language: str,
        cross_language_policy: CrossLanguagePolicy = "project_only",
    ) -> ProjectStructureDraft:
        enforce_source_language_policy(
            output_language=self.output_language,
            source_languages=[source_language],
            policy=cross_language_policy,
        )
        if source_language != self.output_language:
            raise ContractError(
                "Cross-language structure analysis requires a configured LLM provider."
            )
        text, truncated = self._source_slice(source_text)
        chapters = self._chapters_from_text(title=title, text=text)
        outline = self._normalize_outline(
            {
                "schema": "project_structure_draft_v1",
                "project_id": project_id,
                "source_title": title,
                "summary": self._summary(text)
                or localized(
                    self.output_language,
                    zh=f"从《{title}》导入生成的项目结构初稿。",
                    en=f"Initial project structure imported from {title}.",
                ),
                "chapters": chapters,
            },
            project_id=project_id,
            title=title,
        )
        if truncated:
            outline["truncated"] = True
        return ProjectStructureDraft(
            body=json.dumps(outline, ensure_ascii=False, indent=2),
            outline=outline,
            truncated=truncated,
            created_via="api",
        )

    def _source_slice(self, text: str) -> tuple[str, bool]:
        if len(text) <= self.max_source_chars:
            return text, False
        return text[: self.max_source_chars], True

    def _chapters_from_text(self, *, title: str, text: str) -> list[dict[str, Any]]:
        paragraphs = self._paragraphs(text)
        if not paragraphs:
            return [self._chapter(title=title, chapter_index=1, paragraphs=[])]

        heading_pattern = re.compile(
            r"^\s*((第[一二三四五六七八九十百千万\d]+[章节回卷])|(chapter\s+\d+))[\s:：.-]*(.*)$",
            re.IGNORECASE,
        )
        chapters: list[dict[str, Any]] = []
        current_title: str | None = None
        current_paragraphs: list[str] = []
        for paragraph in paragraphs:
            match = heading_pattern.match(paragraph)
            if match:
                if current_title or current_paragraphs:
                    chapters.append(
                        self._chapter(
                            title=current_title
                            or localized(
                                self.output_language,
                                zh=f"{title} 片段",
                                en=f"{title} excerpt",
                            ),
                            chapter_index=len(chapters) + 1,
                            paragraphs=current_paragraphs,
                        )
                    )
                suffix = match.group(4).strip()
                current_title = f"{match.group(1).strip()} {suffix}".strip()
                current_paragraphs = []
                continue
            current_paragraphs.append(paragraph)

        if current_title or current_paragraphs:
            chapters.append(
                self._chapter(
                    title=current_title
                    or localized(
                        self.output_language,
                        zh="导入正文结构",
                        en="Imported manuscript structure",
                    ),
                    chapter_index=len(chapters) + 1,
                    paragraphs=current_paragraphs,
                )
            )

        if not chapters:
            chapters.append(self._chapter(title=title, chapter_index=1, paragraphs=paragraphs))
        return chapters[: self.max_chapters]

    def _chapter(self, *, title: str, chapter_index: int, paragraphs: list[str]) -> dict[str, Any]:
        scenes = self._scenes_from_paragraphs(paragraphs)
        return {
            "title": title
            or localized(
                self.output_language,
                zh=f"第 {chapter_index} 章",
                en=f"Chapter {chapter_index}",
            ),
            "chapter_index": chapter_index,
            "summary": self._summary(" ".join(paragraphs))
            or localized(
                self.output_language,
                zh="待作者补充章节摘要。",
                en="Chapter summary to be completed by the author.",
            ),
            "purpose": localized(
                self.output_language,
                zh="从导入正文自动生成的章节结构初稿，需作者确认。",
                en=(
                    "Initial chapter structure inferred from the imported manuscript; "
                    "author confirmation required."
                ),
            ),
            "scenes": scenes or [
                {
                    "title": localized(self.output_language, zh="场景 1", en="Scene 1"),
                    "scene_index": 1,
                    "summary": localized(
                        self.output_language,
                        zh="待作者补充场景摘要。",
                        en="Scene summary to be completed by the author.",
                    ),
                    "goal": "",
                    "conflict": "",
                    "timeline_position": None,
                    "pov_label": None,
                    "location_label": None,
                }
            ],
        }

    def _scenes_from_paragraphs(self, paragraphs: list[str]) -> list[dict[str, Any]]:
        usable = [paragraph for paragraph in paragraphs if len(paragraph.strip()) > 8]
        if not usable:
            return []
        scene_count = min(self.max_scenes_per_chapter, max(1, min(len(usable), 4)))
        group_size = max(1, math.ceil(len(usable) / scene_count))
        scenes: list[dict[str, Any]] = []
        for index in range(scene_count):
            group = usable[index * group_size : (index + 1) * group_size]
            if not group:
                continue
            summary = self._summary(" ".join(group))
            scenes.append(
                {
                    "title": self._scene_title(group[0], index + 1),
                    "scene_index": index + 1,
                    "summary": summary
                    or localized(
                        self.output_language,
                        zh="待作者补充场景摘要。",
                        en="Scene summary to be completed by the author.",
                    ),
                    "goal": summary or "",
                    "conflict": "",
                    "timeline_position": None,
                    "pov_label": None,
                    "location_label": None,
                }
            )
        return scenes

    @staticmethod
    def _paragraphs(text: str) -> list[str]:
        return [
            paragraph.strip()
            for paragraph in re.split(r"\n\s*\n|\r\n\s*\r\n", text)
            if paragraph.strip()
        ]

    @staticmethod
    def _summary(text: str) -> str:
        compact = re.sub(r"\s+", " ", text).strip()
        if not compact:
            return ""
        return compact[:120]

    def _scene_title(self, text: str, index: int) -> str:
        first_sentence = re.split(r"[。！？!?]", text.strip(), maxsplit=1)[0].strip()
        if len(first_sentence) > 18:
            first_sentence = first_sentence[:18]
        return first_sentence or localized(
            self.output_language,
            zh=f"场景 {index}",
            en=f"Scene {index}",
        )

    def _normalize_outline(
        self,
        payload: dict[str, Any],
        *,
        project_id: str,
        title: str,
    ) -> dict[str, Any]:
        chapters = payload.get("chapters")
        if not isinstance(chapters, list) or not chapters:
            raise ContractError("Project structure draft requires chapters array")
        normalized_chapters: list[dict[str, Any]] = []
        for chapter_index, raw_chapter in enumerate(chapters[: self.max_chapters], start=1):
            if not isinstance(raw_chapter, dict):
                continue
            scenes = raw_chapter.get("scenes")
            if not isinstance(scenes, list):
                scenes = []
            normalized_scenes = [
                self._normalize_scene(raw_scene, scene_index=index)
                for index, raw_scene in enumerate(scenes[: self.max_scenes_per_chapter], start=1)
                if isinstance(raw_scene, dict)
            ]
            if not normalized_scenes:
                normalized_scenes = [self._normalize_scene({}, scene_index=1)]
            normalized_chapters.append(
                {
                    "title": self._text(raw_chapter.get("title"), max_chars=120)
                    or localized(
                        self.output_language,
                        zh=f"第 {chapter_index} 章",
                        en=f"Chapter {chapter_index}",
                    ),
                    "chapter_index": self._positive_int(
                        raw_chapter.get("chapter_index"), chapter_index
                    ),
                    "summary": self._text(raw_chapter.get("summary"), max_chars=500),
                    "purpose": self._text(raw_chapter.get("purpose"), max_chars=300),
                    "scenes": normalized_scenes,
                }
            )
        if not normalized_chapters:
            normalized_chapters.append(self._chapter(title=title, chapter_index=1, paragraphs=[]))
        return {
            "schema": "project_structure_draft_v1",
            "project_id": project_id,
            "source_title": self._text(payload.get("source_title"), max_chars=500)
            or title[:500],
            "summary": self._text(payload.get("summary"), max_chars=1000),
            "chapters": normalized_chapters,
        }

    def _normalize_scene(self, raw_scene: dict[str, Any], *, scene_index: int) -> dict[str, Any]:
        return {
            "title": self._text(raw_scene.get("title"), max_chars=120)
            or localized(
                self.output_language,
                zh=f"场景 {scene_index}",
                en=f"Scene {scene_index}",
            ),
            "scene_index": self._positive_int(raw_scene.get("scene_index"), scene_index),
            "summary": self._text(raw_scene.get("summary"), max_chars=500),
            "goal": self._text(raw_scene.get("goal"), max_chars=300),
            "conflict": self._text(raw_scene.get("conflict"), max_chars=300),
            "timeline_position": self._nullable_text(
                raw_scene.get("timeline_position"), max_chars=120
            ),
            "pov_label": self._nullable_text(raw_scene.get("pov_label"), max_chars=120),
            "location_label": self._nullable_text(
                raw_scene.get("location_label"), max_chars=120
            ),
        }

    @staticmethod
    def _text(value: Any, *, max_chars: int) -> str:
        if value is None:
            return ""
        return str(value).strip()[:max_chars]

    @classmethod
    def _nullable_text(cls, value: Any, *, max_chars: int) -> str | None:
        text = cls._text(value, max_chars=max_chars)
        return text or None

    @staticmethod
    def _positive_int(value: Any, fallback: int) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return fallback
        return number if number > 0 else fallback


class LLMProjectStructureAnalyzer(RuleBasedProjectStructureAnalyzer):
    """LLM-backed analyzer with the same normalized output shape."""

    def __init__(
        self,
        *,
        provider: LLMProvider,
        model: str,
        output_language: OutputLanguage,
        prompt_path: Path | None = None,
        max_source_chars: int = 40000,
        max_chapters: int = 12,
        max_scenes_per_chapter: int = 8,
        temperature: float = 0.1,
    ) -> None:
        super().__init__(
            output_language=output_language,
            max_source_chars=max_source_chars,
            max_chapters=max_chapters,
            max_scenes_per_chapter=max_scenes_per_chapter,
        )
        self.provider = provider
        self.model = model
        self.prompt_path = (
            prompt_path or Path(__file__).parents[1] / "prompts" / "project_structure_analyzer.md"
        )
        self.temperature = temperature

    def analyze(
        self,
        *,
        project_id: str,
        title: str,
        source_text: str,
        source_language: str,
        cross_language_policy: CrossLanguagePolicy = "project_only",
    ) -> ProjectStructureDraft:
        enforce_source_language_policy(
            output_language=self.output_language,
            source_languages=[source_language],
            policy=cross_language_policy,
        )
        text, truncated = self._source_slice(source_text)
        response = self.provider.generate(
            LLMRequest(
                model=self.model,
                temperature=self.temperature,
                max_tokens=4096,
                messages=self._messages(
                    project_id=project_id,
                    title=title,
                    source_text=text,
                    source_language=source_language,
                    cross_language_policy=cross_language_policy,
                ),
            )
        )
        payload = self._parse_response(response.content)
        outline = self._normalize_outline(payload, project_id=project_id, title=title)
        validate_generated_output_language(
            output_language=self.output_language,
            fields=_outline_language_fields(outline),
        )
        if truncated:
            outline["truncated"] = True
        return ProjectStructureDraft(
            body=json.dumps(outline, ensure_ascii=False, indent=2),
            outline=outline,
            truncated=truncated,
            created_via="llm",
        )

    def _messages(
        self,
        *,
        project_id: str,
        title: str,
        source_text: str,
        source_language: str,
        cross_language_policy: CrossLanguagePolicy,
    ) -> list[LLMMessage]:
        prompt = self.prompt_path.read_text(encoding="utf-8")
        payload = {
            "project_id": project_id,
            "output_language": self.output_language,
            "source_language": source_language,
            "cross_language_policy": cross_language_policy,
            "source_title": title,
            "max_chapters": self.max_chapters,
            "max_scenes_per_chapter": self.max_scenes_per_chapter,
            "source_text": source_text,
        }
        return [
            LLMMessage(role="system", content=prompt),
            LLMMessage(
                role="system",
                content=authoritative_language_message(self.output_language),
            ),
            LLMMessage(role="user", content=json.dumps(payload, ensure_ascii=False, indent=2)),
        ]

    @staticmethod
    def _parse_response(content: str) -> dict[str, Any]:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
            cleaned = cleaned.removesuffix("```").strip()
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ContractError("LLM project structure analyzer response must be JSON") from exc
        if not isinstance(payload, dict):
            raise ContractError("LLM project structure analyzer response must be a JSON object")
        return payload


def _outline_language_fields(outline: dict[str, Any]) -> dict[str, str | None]:
    fields: dict[str, str | None] = {"summary": outline.get("summary")}
    for chapter_index, chapter in enumerate(outline.get("chapters", [])):
        if not isinstance(chapter, dict):
            continue
        prefix = f"chapters[{chapter_index}]"
        for key in ("title", "summary", "purpose"):
            value = chapter.get(key)
            fields[f"{prefix}.{key}"] = value if isinstance(value, str) else None
        for scene_index, scene in enumerate(chapter.get("scenes", [])):
            if not isinstance(scene, dict):
                continue
            scene_prefix = f"{prefix}.scenes[{scene_index}]"
            for key in (
                "title",
                "summary",
                "goal",
                "conflict",
            ):
                value = scene.get(key)
                fields[f"{scene_prefix}.{key}"] = value if isinstance(value, str) else None
    return fields
