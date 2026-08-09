"""Scene drafting service."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

from storygraph.core.errors import ContractError
from storygraph.models.context import ContextPack
from storygraph.models.draft import Draft
from storygraph.models.project import localized
from storygraph.services.llm_provider import LLMMessage, LLMProvider, LLMRequest
from storygraph.services.project_language import authoritative_language_message
from storygraph.services.project_language import validate_generated_output_language
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
        _validate_rule_based_context_language(context_pack)
        required_lines = "\n".join(f"- {item}" for item in context_pack.must_include)
        relationship_hint = "; ".join(context_pack.active_relationships[:3]) or localized(
            context_pack.output_language,
            zh="没有可用的关系提示。",
            en="No active relation note.",
        )
        if context_pack.output_language == "zh-CN":
            text = (
                f"场景 {context_pack.scene_id}\n\n"
                f"目标：{context_pack.scene_goal}\n"
                f"冲突：{context_pack.conflict}\n"
                f"视角：{context_pack.pov_character_id}，地点：{context_pack.location_id}。\n\n"
                f"场景保持{context_pack.style_constraints.tone or '克制'}的语气。"
                "视角人物追求当前目标，冲突带来的压力逐步上升。"
                f"当前关系压力：{relationship_hint}\n\n"
                f"必须包含：\n{required_lines}\n\n"
                "草稿只使用当前上下文包，不直接修改 canon。"
                "任何状态变化都必须随后提取为 CandidateFact 并由作者审阅。"
            )
            summary = (
                f"{context_pack.scene_id}：{context_pack.pov_character_id}在"
                f"{context_pack.conflict}中尝试{context_pack.scene_goal}。"
            )
            self_check = [
                "只生成了指定场景。",
                "没有修改 canon。",
                "状态变化仍需提取为候选事实并由作者审阅。",
            ]
        else:
            text = (
                f"Scene {context_pack.scene_id}\n\n"
                f"Goal: {context_pack.scene_goal}\n"
                f"Conflict: {context_pack.conflict}\n"
                f"POV: {context_pack.pov_character_id} at {context_pack.location_id}.\n\n"
                f"The scene keeps a {context_pack.style_constraints.tone or 'restrained'} tone. "
                "The POV character pursues the immediate goal while pressure rises from the conflict. "
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
            content_language=context_pack.output_language,
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
            content_language=context_pack.output_language,
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
            "output_language": context_pack.output_language,
            "context_pack": context_pack.model_dump(),
        }
        return [
            LLMMessage(role="system", content=prompt_contract),
            LLMMessage(
                role="system",
                content=authoritative_language_message(context_pack.output_language),
            ),
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


def _validate_rule_based_context_language(context_pack: ContextPack) -> None:
    natural_language_values = [
        context_pack.scene_goal,
        context_pack.conflict,
        context_pack.previous_scene_summary or "",
        context_pack.style_constraints.tone or "",
        context_pack.style_constraints.diction or "",
        context_pack.style_constraints.dialogue_style or "",
        *context_pack.must_include,
        *context_pack.must_not_violate,
        *context_pack.relevant_world_rules,
        *context_pack.unresolved_foreshadowing,
    ]
    for value in natural_language_values:
        if not value.strip():
            continue
        contains_han = bool(re.search(r"[\u3400-\u9fff]", value))
        latin_count = len(re.findall(r"[A-Za-z]", value))
        mismatched = (
            context_pack.output_language == "en-US"
            and contains_han
        ) or (
            context_pack.output_language == "zh-CN"
            and not contains_han
            and latin_count >= 8
        )
        if mismatched:
            raise ContractError(
                "Rule-based scene generation cannot safely reuse context written in "
                "another language; configure an LLM or update the scene fields."
            )


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
    validate_generated_output_language(
        output_language=context_pack.output_language,
        fields={
            "text": result.text,
            "summary": result.summary,
            **{
                f"self_check[{index}]": item
                for index, item in enumerate(result.self_check)
            },
        },
    )
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
