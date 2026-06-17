"""Scene drafting service."""

from __future__ import annotations

from dataclasses import dataclass

from storygraph.core.errors import ContractError
from storygraph.models.context import ContextPack
from storygraph.models.draft import Draft
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
        critical_gaps = [gap for gap in context_pack.missing_context if gap.severity == "critical"]
        if critical_gaps:
            refs = ", ".join(gap.ref for gap in critical_gaps)
            raise ContractError(f"Cannot draft with critical missing context: {refs}")
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
