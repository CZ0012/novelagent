"""Build compact scene context packs from canon graph state."""

from __future__ import annotations

from storygraph.core.ids import new_id
from storygraph.core.time import utc_now
from storygraph.models.context import (
    ContextBudget,
    ContextPack,
    ContextProvenance,
    KnowledgeBoundary,
    StyleConstraints,
)
from storygraph.stores.draft_store import SQLiteDraftStore
from storygraph.stores.graph_base import GraphStore
from storygraph.stores.style_sample_store import StyleSampleStore


class ContextPackBuilder:
    def __init__(
        self,
        graph_store: GraphStore,
        draft_store: SQLiteDraftStore | None = None,
        style_sample_store: StyleSampleStore | None = None,
    ) -> None:
        self.graph_store = graph_store
        self.draft_store = draft_store
        self.style_sample_store = style_sample_store

    def build(
        self,
        *,
        project_id: str,
        scene_id: str,
        target_tokens: int = 4000,
        author_instruction_refs: list[str] | None = None,
    ) -> ContextPack:
        scene_context = self.graph_store.query_scene_context(scene_id)
        scene = scene_context["scene"]
        props = scene.properties

        required_characters = list(
            dict.fromkeys(
                [
                    props.get("pov_character_id"),
                    *props.get("required_characters", []),
                ]
            )
        )
        required_characters = [character_id for character_id in required_characters if character_id]
        knowledge = [
            self.graph_store.get_character_knowledge(
                character_id,
                scene_id=scene_id,
                timeline_position=props.get("timeline_position"),
            )
            for character_id in required_characters
        ]

        active_relationships = [
            self._relationship_text(relation)
            for relation in scene_context.get("active_relationships", [])
        ]
        world_rules = [
            f"{node.id}: {node.properties.get('rule', node.properties.get('summary', ''))}"
            for node in scene_context.get("world_rules", [])
        ]
        foreshadowing = [
            f"{node.id}: {node.properties.get('clue_text', node.properties.get('hidden_meaning', ''))}"
            for node in scene_context.get("unresolved_foreshadowing", [])
        ]

        previous_scene_summary = None
        draft_refs: list[str] = []
        previous_scene_id = props.get("previous_scene_id")
        if previous_scene_id and self.draft_store:
            draft = self.draft_store.latest_for_scene(project_id, previous_scene_id)
            if draft:
                previous_scene_summary = draft.summary
                draft_refs.append(draft.id)

        style_props = props.get("style_constraints", {})
        style = StyleConstraints(
            pov=style_props.get("pov", props.get("narrative_pov", "third-person limited")),
            tense=style_props.get("tense"),
            tone=style_props.get("tone", "restrained"),
            sentence_rhythm=style_props.get("sentence_rhythm"),
            diction=style_props.get("diction"),
            dialogue_style=style_props.get("dialogue_style"),
            banned_patterns=style_props.get("banned_patterns", []),
        )
        retrieved_style_samples = list(props.get("retrieved_style_samples", []))
        style_sample_refs = list(props.get("style_sample_refs", []))
        if self.style_sample_store:
            matches = self.style_sample_store.search(
                project_id=project_id,
                query=self._style_query(props, style),
                pov=style.pov,
                tone=style.tone,
                dialogue_style=style.dialogue_style,
                tags=props.get("style_tags", []),
                limit=3,
            )
            retrieved_style_samples.extend(
                self._style_sample_text(match.sample) for match in matches
            )
            style_sample_refs.extend(match.sample.id for match in matches)

        pack = ContextPack(
            project_id=project_id,
            scene_id=scene_id,
            chapter_id=props["chapter_id"],
            pov_character_id=props["pov_character_id"],
            location_id=props["location_id"],
            timeline_position=props.get("timeline_position", ""),
            scene_goal=props.get("goal", ""),
            conflict=props.get("conflict", ""),
            required_characters=required_characters,
            active_relationships=active_relationships,
            knowledge_boundaries=knowledge,
            must_include=props.get("must_include", []),
            must_not_violate=props.get("must_not_violate", []),
            unresolved_foreshadowing=foreshadowing,
            relevant_world_rules=world_rules,
            previous_scene_summary=previous_scene_summary,
            style_constraints=style,
            retrieved_style_samples=retrieved_style_samples,
            provenance=ContextProvenance(
                graph_query_ids=[new_id("graph_query")],
                draft_refs=draft_refs,
                style_sample_refs=style_sample_refs,
                author_instruction_refs=author_instruction_refs or [],
                built_at=utc_now(),
            ),
            budget=ContextBudget(target_tokens=target_tokens),
        )
        return self._apply_budget(pack, target_tokens)

    @staticmethod
    def _relationship_text(relation) -> str:
        strength = relation.properties.get("strength")
        suffix = f" strength={strength}" if strength is not None else ""
        return f"{relation.source_id} {relation.type} {relation.target_id}{suffix}"

    @staticmethod
    def _style_query(props: dict, style: StyleConstraints) -> str:
        return " ".join(
            str(value)
            for value in [
                props.get("goal", ""),
                props.get("conflict", ""),
                props.get("emotional_turn", ""),
                style.pov,
                style.tone,
                style.dialogue_style,
                style.diction,
                style.sentence_rhythm,
            ]
            if value
        )

    @staticmethod
    def _style_sample_text(sample) -> str:
        snippet = sample.text.strip()
        if len(snippet) > 1200:
            snippet = snippet[:1197].rstrip() + "..."
        return f"{sample.id}: {snippet}"

    @staticmethod
    def _estimate_tokens(pack: ContextPack) -> int:
        serialized = pack.model_dump_json()
        return max(1, len(serialized) // 4)

    def _apply_budget(self, pack: ContextPack, target_tokens: int) -> ContextPack:
        working = pack
        dropped_items: list[str] = []
        trim_steps = [
            (
                "P6",
                "retrieved_style_samples",
                "style samples",
                lambda current: current.model_copy(update={"retrieved_style_samples": []}),
            ),
            (
                "P4",
                "unresolved_foreshadowing",
                "unresolved foreshadowing",
                lambda current: current.model_copy(update={"unresolved_foreshadowing": []}),
            ),
            (
                "P3",
                "relevant_world_rules",
                "world rules",
                lambda current: current.model_copy(update={"relevant_world_rules": []}),
            ),
            (
                "P5",
                "previous_scene_summary",
                "previous scene summary",
                lambda current: current.model_copy(update={"previous_scene_summary": None}),
            ),
        ]

        for priority, field_name, label, trim in trim_steps:
            estimated_tokens = self._estimate_tokens(working)
            if estimated_tokens <= target_tokens:
                break
            value = getattr(working, field_name)
            if not value:
                continue
            before = estimated_tokens
            working = trim(working)
            after = self._estimate_tokens(working)
            dropped_items.append(
                f"{priority} dropped {label} to satisfy budget; estimated_tokens {before}->{after}"
            )

        final_estimate = self._estimate_tokens(working)
        if final_estimate > target_tokens:
            dropped_items.append(
                f"Protected P0-P2 context still exceeds target by {final_estimate - target_tokens} tokens"
            )
        return working.model_copy(
            update={
                "budget": working.budget.model_copy(
                    update={"estimated_tokens": final_estimate, "dropped_items": dropped_items}
                )
            }
        )
