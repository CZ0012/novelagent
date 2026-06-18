"""Scene drafting service."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

from storygraph.core.errors import ContractError
from storygraph.models.context import ContextPack
from storygraph.models.draft import Draft
from storygraph.services.llm_provider import LLMMessage, LLMProvider, LLMRequest
from storygraph.stores.draft_store import SQLiteDraftStore


@dataclass(frozen=True)
class DraftResult:
    text: str
    summary: str
    self_check: list[str]


class RuleBasedSceneWriter:
    """Deterministic local writer used until an LLM provider is configured."""

    def __init__(self, draft_store: SQLiteDraftStore | None = None) -> None:
        self.draft_store = draft_store

    def draft(self, context_pack: ContextPack) -> DraftResult:
        _validate_context_pack_for_drafting(context_pack)
        required_lines = "\n".join(f"- {item}" for item in context_pack.must_include)
        relationship_hint = "; ".join(context_pack.active_relationships[:3]) or "No active relation note."
        text = (
            f"Scene {context_pack.scene_id}\n\n"
            f"Goal: {context_pack.scene_goal}\n"
            f"Conflict: {context_pack.conflict}\n"
            f"POV: {context_pack.pov_character_id} at {context_pack.location_id}.\n\n"
            f"The scene keeps a {context_pack.style_constraints.tone or 'restrained'} tone. "
            f"The POV character pursues the immediate goal while pressure rises from the conflict. "
            f"Relationship pressure in play: {relationship_hint}\n\n"
            f"Required beats:\n{required_lines}\n\n"
            "The draft stays inside the current context pack and does not commit canon changes. "
            "Any state changes must be extracted later as CandidateFact records."
        )
        summary = (
            f"{context_pack.scene_id}: {context_pack.pov_character_id} attempts "
            f"{context_pack.scene_goal} amid {context_pack.conflict}."
        )
        self_check = [
            "Generated only the requested scene.",
            "Did not mutate canon.",
            "State changes require later candidate extraction and human review.",
        ]
        return DraftResult(text=text, summary=summary, self_check=self_check)

    def write_and_save(self, context_pack: ContextPack) -> Draft:
        if not self.draft_store:
            raise RuntimeError("write_and_save requires a draft store")
        result = self.draft(context_pack)
        return self.draft_store.create_draft(
            project_id=context_pack.project_id,
            scene_id=context_pack.scene_id,
            text=result.text,
            summary=result.summary,
        )


class LLMSceneWriter:
    """Scene writer backed by a configured LLM provider.

    The writer saves only to Draft Store. It receives no GraphStore handle, so it
    cannot commit canon directly.
    """

    def __init__(
        self,
        *,
        provider: LLMProvider,
        model: str,
        draft_store: SQLiteDraftStore | None = None,
        temperature: float = 0.2,
        prompt_path: Path | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.draft_store = draft_store
        self.temperature = temperature
        self.prompt_path = prompt_path or Path(__file__).parents[1] / "prompts" / "scene_writer.md"

    def draft(self, context_pack: ContextPack) -> DraftResult:
        _validate_context_pack_for_drafting(context_pack)
        response = self.provider.generate(
            LLMRequest(
                model=self.model,
                temperature=self.temperature,
                messages=self._messages(context_pack),
            )
        )
        result = _parse_llm_draft(response.content)
        _validate_draft_result(context_pack=context_pack, result=result)
        return result

    def write_and_save(self, context_pack: ContextPack) -> Draft:
        if not self.draft_store:
            raise RuntimeError("write_and_save requires a draft store")
        result = self.draft(context_pack)
        return self.draft_store.create_draft(
            project_id=context_pack.project_id,
            scene_id=context_pack.scene_id,
            text=result.text,
            summary=result.summary,
        )

    def _messages(self, context_pack: ContextPack) -> list[LLMMessage]:
        prompt_contract = self.prompt_path.read_text(encoding="utf-8")
        user_payload = {
            "instruction": (
                "Draft the current scene from this context_pack_v1. Return only a JSON object "
                "with string field `text`, string field `summary`, and array field `self_check`."
            ),
            "context_pack": context_pack.model_dump(),
        }
        return [
            LLMMessage(role="system", content=prompt_contract),
            LLMMessage(
                role="user",
                content=json.dumps(user_payload, ensure_ascii=False, indent=2),
            ),
        ]


def _validate_context_pack_for_drafting(context_pack: ContextPack) -> None:
    critical_gaps = [gap for gap in context_pack.missing_context if gap.severity == "critical"]
    if critical_gaps:
        refs = ", ".join(gap.ref for gap in critical_gaps)
        raise ContractError(f"Cannot draft with critical missing context: {refs}")
    if context_pack.contract_version != "context_pack_v1":
        raise ContractError("Scene writer requires context_pack_v1")
    if not context_pack.project_id or not context_pack.scene_id:
        raise ContractError("Context Pack must include project_id and scene_id")


def _parse_llm_draft(content: str) -> DraftResult:
    cleaned = _strip_json_fence(content)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ContractError("LLM scene writer response must be JSON") from exc
    if not isinstance(payload, dict):
        raise ContractError("LLM scene writer response must be a JSON object")
    text = payload.get("text")
    summary = payload.get("summary")
    self_check = payload.get("self_check")
    if not isinstance(text, str) or not text.strip():
        raise ContractError("LLM scene writer response requires non-empty text")
    if not isinstance(summary, str) or not summary.strip():
        raise ContractError("LLM scene writer response requires non-empty summary")
    if not isinstance(self_check, list) or not all(isinstance(item, str) for item in self_check):
        raise ContractError("LLM scene writer response requires string self_check items")
    return DraftResult(text=text.strip(), summary=summary.strip(), self_check=self_check)


def _strip_json_fence(content: str) -> str:
    match = re.fullmatch(r"\s*```(?:json)?\s*(.*?)\s*```\s*", content, flags=re.DOTALL)
    return match.group(1) if match else content.strip()


def _validate_draft_result(*, context_pack: ContextPack, result: DraftResult) -> None:
    text_lower = result.text.lower()
    missing_required = [
        item for item in context_pack.must_include if item and item.lower() not in text_lower
    ]
    if missing_required:
        raise ContractError(
            "LLM scene writer response omitted must_include elements: "
            + ", ".join(missing_required)
        )
    violated = [
        item for item in context_pack.must_not_violate if item and item.lower() in text_lower
    ]
    if violated:
        raise ContractError(
            "LLM scene writer response violated must_not_violate constraints: "
            + ", ".join(violated)
        )
