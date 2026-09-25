"""LLM-assisted fact-draft extraction from imported documents."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from storygraph.core.errors import ContractError, ModelOutputError
from storygraph.core.ids import new_id, slug_id
from storygraph.models.draft import Draft
from storygraph.models.project import CrossLanguagePolicy, OutputLanguage, localized
from storygraph.services.json_output import unwrap_json_fence
from storygraph.services.llm_provider import LLMMessage, LLMProvider, LLMRequest
from storygraph.services.project_language import (
    authoritative_language_message,
    enforce_source_language_policy,
    validate_generated_output_language,
)


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

    def extract(
        self,
        *,
        project_id: str,
        scene_id: str,
        source_draft: Draft,
        output_language: OutputLanguage,
        source_language: str,
        cross_language_policy: CrossLanguagePolicy = "project_only",
    ) -> DocumentFactDraft:
        enforce_source_language_policy(
            output_language=output_language,
            source_languages=[source_language],
            policy=cross_language_policy,
        )
        if (
            source_language != output_language
            or source_draft.content_language != output_language
            or source_draft.project_id != project_id
            or source_draft.scene_id != scene_id
        ):
            raise ContractError(
                "Document fact source Draft scope and language must match the project output language."
            )
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
                    output_language=output_language,
                    source_language=source_language,
                    cross_language_policy=cross_language_policy,
                ),
            )
        )
        facts = self._parse_response(response.content)
        validate_generated_output_language(
            output_language=output_language,
            fields=_fact_language_fields(facts),
        )
        markers = [
            self._marker(index=index, fact=fact, output_language=output_language)
            for index, fact in enumerate(facts[: self.max_facts], start=1)
        ]
        header = [
            localized(
                output_language,
                zh=f"# 来自 {source_draft.id} 的 LLM fact_draft",
                en=f"# LLM fact_draft from {source_draft.id}",
            ),
            "",
            localized(
                output_language,
                zh="这些条目是从导入资料生成的候选事实草稿，尚未进入 Candidate Store 或 canon。",
                en=(
                    "These entries are candidate fact drafts extracted from imported material; "
                    "they are not in the Candidate Store or canon."
                ),
            ),
            localized(
                output_language,
                zh="作者可以编辑下方显式 fact 标记，再提交为候选事实进行审阅。",
                en="The author may edit the explicit fact markers below before submitting them for review.",
            ),
        ]
        if truncated:
            header.append(
                localized(
                    output_language,
                    zh="注意：源文本较长，本次只读取了前部片段。",
                    en="Note: the source was long, so only its leading section was read.",
                )
            )
        body = "\n".join([*header, "", *markers]).strip()
        return DocumentFactDraft(body=body, facts=facts, truncated=truncated)

    def _messages(
        self,
        *,
        project_id: str,
        scene_id: str,
        source_draft: Draft,
        source_text: str,
        output_language: OutputLanguage,
        source_language: str,
        cross_language_policy: CrossLanguagePolicy,
    ) -> list[LLMMessage]:
        prompt = self.prompt_path.read_text(encoding="utf-8")
        payload = {
            "project_id": project_id,
            "scene_id": scene_id,
            "source_draft_id": source_draft.id,
            "output_language": output_language,
            "source_language": source_language,
            "cross_language_policy": cross_language_policy,
            "max_facts": self.max_facts,
            "source_text": source_text,
        }
        return [
            LLMMessage(role="system", content=prompt),
            LLMMessage(
                role="system",
                content=authoritative_language_message(output_language),
            ),
            LLMMessage(role="user", content=json.dumps(payload, ensure_ascii=False, indent=2)),
        ]

    def _source_slice(self, text: str) -> tuple[str, bool]:
        if len(text) <= self.max_source_chars:
            return text, False
        return text[: self.max_source_chars], True

    @staticmethod
    def _parse_response(content: str) -> list[dict[str, Any]]:
        try:
            payload = json.loads(unwrap_json_fence(content))
        except (json.JSONDecodeError, ValueError) as exc:
            raise ModelOutputError("LLM document fact extractor response must be JSON") from exc
        if not isinstance(payload, dict):
            raise ModelOutputError("LLM document fact extractor response must be a JSON object")
        facts = payload.get("facts")
        if not isinstance(facts, list):
            raise ModelOutputError("LLM document fact extractor response requires facts array")
        return [fact for fact in facts if isinstance(fact, dict)]

    def _marker(
        self,
        *,
        index: int,
        fact: dict[str, Any],
        output_language: OutputLanguage,
    ) -> str:
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
            "rationale": self._value(fact.get("rationale"))
            or localized(
                output_language,
                zh="LLM 从导入资料中提取了这条候选事实。",
                en="LLM extracted this candidate fact from imported source material.",
            ),
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


def _fact_language_fields(facts: list[dict[str, Any]]) -> dict[str, str | None]:
    fields: dict[str, str | None] = {}
    for fact_index, fact in enumerate(facts):
        for key in ("rationale", "value"):
            value = fact.get(key)
            fields[f"facts[{fact_index}].{key}"] = (
                value if isinstance(value, str) else None
            )
        _collect_property_text(
            fact.get("properties"),
            prefix=f"facts[{fact_index}].properties",
            fields=fields,
        )
    return fields


def _collect_property_text(
    value: Any,
    *,
    prefix: str,
    fields: dict[str, str | None],
) -> None:
    if isinstance(value, str):
        fields[prefix] = value
    elif isinstance(value, dict):
        for key, nested in value.items():
            _collect_property_text(nested, prefix=f"{prefix}.{key}", fields=fields)
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _collect_property_text(nested, prefix=f"{prefix}[{index}]", fields=fields)
