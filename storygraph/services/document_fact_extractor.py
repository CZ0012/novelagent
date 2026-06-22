"""LLM-assisted fact-draft extraction from imported documents."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from storygraph.core.errors import ContractError
from storygraph.core.ids import new_id, slug_id
from storygraph.models.draft import Draft
from storygraph.services.llm_provider import LLMMessage, LLMProvider, LLMRequest


@dataclass(frozen=True)
class DocumentFactDraft:
    body: str
    facts: list[dict[str, Any]]
    truncated: bool


class LLMDocumentFactExtractor:
    """Turns source material into explicit fact markers for author review."""

    def __init__(
        self,
        *,
        provider: LLMProvider,
        model: str,
        prompt_path: Path | None = None,
        max_source_chars: int = 28000,
        max_facts: int = 16,
        temperature: float = 0.1,
    ) -> None:
        self.provider = provider
        self.model = model
        self.prompt_path = (
            prompt_path or Path(__file__).parents[1] / "prompts" / "document_fact_extractor.md"
        )
        self.max_source_chars = max_source_chars
        self.max_facts = max_facts
        self.temperature = temperature

    def extract(self, *, project_id: str, scene_id: str, source_draft: Draft) -> DocumentFactDraft:
        text, truncated = self._source_slice(source_draft.text)
        response = self.provider.generate(
            LLMRequest(
                model=self.model,
                temperature=self.temperature,
                max_tokens=4096,
                messages=self._messages(
                    project_id=project_id,
                    scene_id=scene_id,
                    source_draft=source_draft,
                    source_text=text,
                ),
            )
        )
        facts = self._parse_response(response.content)
        markers = [
            self._marker(index=index, fact=fact)
            for index, fact in enumerate(facts[: self.max_facts], start=1)
        ]
        header = [
            f"# LLM fact_draft from {source_draft.id}",
            "",
            "这些条目是从导入资料生成的候选事实草稿，尚未进入 Candidate Store 或 canon。",
            "作者可以编辑下方显式 fact 标记，再提交为候选事实进行审阅。",
        ]
        if truncated:
            header.append("注意：源文本较长，本次只读取了前部片段。")
        body = "\n".join([*header, "", *markers]).strip()
        return DocumentFactDraft(body=body, facts=facts, truncated=truncated)

    def _messages(
        self,
        *,
        project_id: str,
        scene_id: str,
        source_draft: Draft,
        source_text: str,
    ) -> list[LLMMessage]:
        prompt = self.prompt_path.read_text(encoding="utf-8")
        payload = {
            "project_id": project_id,
            "scene_id": scene_id,
            "source_draft_id": source_draft.id,
            "max_facts": self.max_facts,
            "source_text": source_text,
        }
        return [
            LLMMessage(role="system", content=prompt),
            LLMMessage(role="user", content=json.dumps(payload, ensure_ascii=False, indent=2)),
        ]

    def _source_slice(self, text: str) -> tuple[str, bool]:
        if len(text) <= self.max_source_chars:
            return text, False
        return text[: self.max_source_chars], True

    @staticmethod
    def _parse_response(content: str) -> list[dict[str, Any]]:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
            cleaned = cleaned.removesuffix("```").strip()
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ContractError("LLM document fact extractor response must be JSON") from exc
        if not isinstance(payload, dict):
            raise ContractError("LLM document fact extractor response must be a JSON object")
        facts = payload.get("facts")
        if not isinstance(facts, list):
            raise ContractError("LLM document fact extractor response requires facts array")
        return [fact for fact in facts if isinstance(fact, dict)]

    def _marker(self, *, index: int, fact: dict[str, Any]) -> str:
        subject = self._value(fact.get("subject")) or slug_id("entity", self._value(fact.get("quote")) or str(index))
        relation = self._value(fact.get("relation")) or "HAS_STATE"
        fact_id = self._value(fact.get("id")) or new_id("fact")
        fields: dict[str, str] = {
            "id": fact_id if fact_id.startswith("fact_") else slug_id("fact", fact_id),
            "fact_type": self._value(fact.get("fact_type")) or "CharacterState",
            "subject": subject,
            "relation": relation,
            "confidence": self._confidence(fact.get("confidence")),
            "operation": self._value(fact.get("operation")) or "update_node",
            "rationale": self._value(fact.get("rationale")) or "LLM extracted this from imported source material.",
        }
        object_id = self._value(fact.get("object"))
        if object_id:
            fields["object"] = object_id
        value = self._value(fact.get("value"))
        if value:
            fields["value"] = value
        quote = self._value(fact.get("quote"))
        if quote:
            fields["quote"] = quote
        properties = fact.get("properties")
        if isinstance(properties, dict):
            for key, raw_value in properties.items():
                value_text = self._value(raw_value)
                if key and value_text:
                    fields[str(key)] = value_text
        return "[[fact:" + ";".join(f"{key}={self._clean(value)}" for key, value in fields.items()) + "]]"

    @staticmethod
    def _value(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    @staticmethod
    def _confidence(value: Any) -> str:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            confidence = 0.75
        confidence = min(max(confidence, 0.0), 1.0)
        return f"{confidence:.2f}"

    @staticmethod
    def _clean(value: str) -> str:
        return (
            value.replace("\r", " ")
            .replace("\n", " ")
            .replace(";", "，")
            .replace("[[", "[ [")
            .replace("]]", "] ]")
            .strip()
        )
