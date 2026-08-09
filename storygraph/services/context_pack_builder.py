"""Build compact scene context packs from canon graph state."""

from __future__ import annotations

from storygraph.core.errors import ContractError, GraphStoreError
from storygraph.core.time import utc_now
from storygraph.models.context import (
    ContextBudget,
    ContextGap,
    ContextPack,
    ContextProvenance,
    KnowledgeBoundary,
    StyleConstraints,
)
from storygraph.models.graph import GraphNode
from storygraph.models.project import OutputLanguage, localized
from storygraph.services.project_language import resolve_project_output_language
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
        missing_context: list[ContextGap] = []
        output_language = resolve_project_output_language(self.graph_store, project_id)
        scoped_scene = self.graph_store.get_node(scene_id)
        self._ensure_scene_scope(project_id, scoped_scene)
        self._ensure_scene_reference_scope(project_id, scoped_scene)
        scene_context = self._query_scene_context(
            scene_id,
            output_language,
            missing_context,
        )
        scene = scene_context["scene"]
        props = scene.properties
        self._ensure_scene_scope(project_id, scene)
        graph_query_ids = self._graph_query_plan(scene_id=scene_id, props=props)

        required_characters = list(
            dict.fromkeys(
                [
                    props.get("pov_character_id"),
                    *props.get("required_characters", []),
                ]
            )
        )
        required_characters = [character_id for character_id in required_characters if character_id]
        self._report_missing_scene_fields(
            props,
            scene_id,
            output_language,
            missing_context,
        )
        self._report_missing_nodes(
            required_characters=required_characters,
            location_id=props.get("location_id"),
            scene_context=scene_context,
            output_language=output_language,
            missing_context=missing_context,
        )
        knowledge = []
        for character_id in required_characters:
            boundary = self._safe_character_knowledge(
                character_id=character_id,
                scene_id=scene_id,
                timeline_position=props.get("timeline_position"),
                output_language=output_language,
                missing_context=missing_context,
            )
            if boundary:
                knowledge.append(boundary)

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
            if draft and draft.content_language == output_language:
                previous_scene_summary = draft.summary
                draft_refs.append(draft.id)
            elif draft:
                missing_context.append(
                    ContextGap(
                        kind="draft_language_mismatch",
                        ref=previous_scene_id,
                        severity="critical",
                        message=localized(
                            output_language,
                            zh="上一场景草稿没有可信的当前项目语言快照。",
                            en=(
                                "The previous scene draft does not have a trusted snapshot "
                                "for the current project language."
                            ),
                        ),
                        source=scene_id,
                    )
                )
            else:
                missing_context.append(
                    ContextGap(
                        kind="missing_draft",
                        ref=previous_scene_id,
                        severity="medium",
                        message=localized(
                            output_language,
                            zh="场景引用了上一场景，但没有可用的草稿摘要。",
                            en=(
                                "Scene references a previous scene, but no draft summary "
                                "is available."
                            ),
                        ),
                        source=scene_id,
                    )
                )

        style_props = props.get("style_constraints", {})
        style = StyleConstraints(
            pov=style_props.get(
                "pov",
                props.get("narrative_pov")
                or localized(
                    output_language,
                    zh="第三人称有限视角",
                    en="third-person limited",
                ),
            ),
            tense=style_props.get("tense"),
            tone=style_props.get("tone")
            or localized(output_language, zh="克制", en="restrained"),
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
                language=output_language,
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
            output_language=output_language,
            scene_id=scene_id,
            chapter_id=props.get("chapter_id", ""),
            pov_character_id=props.get("pov_character_id", ""),
            location_id=props.get("location_id", ""),
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
            missing_context=missing_context,
            provenance=ContextProvenance(
                graph_query_ids=graph_query_ids,
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

    def _query_scene_context(
        self,
        scene_id: str,
        output_language: OutputLanguage,
        missing_context: list[ContextGap],
    ) -> dict:
        try:
            return self.graph_store.query_scene_context(scene_id)
        except GraphStoreError as exc:
            if exc.category != "not_found":
                raise
            scene = self.graph_store.get_node(scene_id)
            missing_context.append(
                ContextGap(
                    kind="incomplete_graph_context",
                    ref=scene_id,
                    severity="high",
                    message=localized(
                        output_language,
                        zh=f"图谱场景上下文查询不完整：{exc}",
                        en=f"Graph scene-context query was incomplete: {exc}",
                    ),
                    source=scene_id,
                )
            )
            return {
                "scene": scene,
                "characters": [],
                "location": None,
                "active_relationships": [],
                "world_rules": [],
                "unresolved_foreshadowing": [],
            }

    @staticmethod
    def _graph_query_plan(*, scene_id: str, props: dict) -> list[str]:
        required_characters = list(
            dict.fromkeys(
                [
                    props.get("pov_character_id"),
                    *props.get("required_characters", []),
                ]
            )
        )
        required_characters = [character_id for character_id in required_characters if character_id]
        plan = [
            f"context_pack_v1:query_scene_context:{scene_id}",
            f"context_pack_v1:query_world_rules:scene_scope:{scene_id}",
            f"context_pack_v1:query_foreshadowing:unresolved:{scene_id}",
        ]
        location_id = props.get("location_id")
        if location_id:
            plan.append(f"context_pack_v1:get_location_state:{location_id}")
        for character_id in required_characters:
            plan.append(f"context_pack_v1:get_character_state:{character_id}")
            plan.append(
                f"context_pack_v1:get_character_knowledge:{scene_id}:{character_id}"
            )
        return plan

    @staticmethod
    def _ensure_scene_scope(
        project_id: str,
        scene: GraphNode,
    ) -> None:
        if scene.type != "Scene" or scene.properties.get("project_id") != project_id:
            raise ContractError("Scene does not belong to the requested project.")

    def _ensure_scene_reference_scope(self, project_id: str, scene: GraphNode) -> None:
        props = scene.properties
        required_characters = props.get("required_characters", [])
        if not isinstance(required_characters, list):
            raise ContractError("Scene required_characters must be a list.")
        references = [
            (props.get("chapter_id"), "Chapter"),
            (props.get("pov_character_id"), "Character"),
            (props.get("location_id"), "Location"),
            (props.get("previous_scene_id"), "Scene"),
            *((character_id, "Character") for character_id in required_characters),
        ]
        for node_id, expected_type in references:
            if not node_id:
                continue
            try:
                node = self.graph_store.get_node(str(node_id))
            except GraphStoreError as exc:
                if exc.category == "not_found":
                    continue
                raise
            if (
                node.type != expected_type
                or node.properties.get("project_id") != project_id
            ):
                raise ContractError(
                    "Scene reference does not belong to the requested project."
                )

    @staticmethod
    def _report_missing_scene_fields(
        props: dict,
        scene_id: str,
        output_language: OutputLanguage,
        missing_context: list[ContextGap],
    ) -> None:
        for field_name in ["chapter_id", "pov_character_id", "location_id"]:
            if not props.get(field_name):
                missing_context.append(
                    ContextGap(
                        kind="missing_scene_field",
                        ref=field_name,
                        severity="critical",
                        message=localized(
                            output_language,
                            zh=f"场景 {scene_id} 缺少必需字段 {field_name}。",
                            en=f"Scene {scene_id} is missing required field {field_name}.",
                        ),
                        source=scene_id,
                    )
                )

    @staticmethod
    def _report_missing_nodes(
        *,
        required_characters: list[str],
        location_id: str | None,
        scene_context: dict,
        output_language: OutputLanguage,
        missing_context: list[ContextGap],
    ) -> None:
        found_characters = {node.id for node in scene_context.get("characters", [])}
        for character_id in required_characters:
            if character_id not in found_characters:
                missing_context.append(
                    ContextGap(
                        kind="missing_node",
                        ref=character_id,
                        severity="critical",
                        message=localized(
                            output_language,
                            zh=f"正典中没有找到必需角色 {character_id}。",
                            en=(
                                f"Required character {character_id} was not found in canon."
                            ),
                        ),
                    )
                )
        if location_id and scene_context.get("location") is None:
            missing_context.append(
                ContextGap(
                    kind="missing_node",
                    ref=location_id,
                    severity="critical",
                    message=localized(
                        output_language,
                        zh=f"正典中没有找到必需地点 {location_id}。",
                        en=f"Required location {location_id} was not found in canon.",
                    ),
                )
            )

    def _safe_character_knowledge(
        self,
        *,
        character_id: str,
        scene_id: str,
        timeline_position: str | None,
        output_language: OutputLanguage,
        missing_context: list[ContextGap],
    ) -> KnowledgeBoundary | None:
        try:
            return self.graph_store.get_character_knowledge(
                character_id,
                scene_id=scene_id,
                timeline_position=timeline_position,
            )
        except GraphStoreError as exc:
            if exc.category != "not_found":
                raise
            already_reported = any(
                gap.kind == "missing_node" and gap.ref == character_id
                for gap in missing_context
            )
            if not already_reported:
                missing_context.append(
                    ContextGap(
                        kind="missing_node",
                        ref=character_id,
                        severity="critical",
                        message=localized(
                            output_language,
                            zh=f"无法为缺失角色 {character_id} 构建知识边界。",
                            en=(
                                "Cannot build knowledge boundary for missing character "
                                f"{character_id}."
                            ),
                        ),
                        source=scene_id,
                    )
                )
            return None

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
                localized(pack.output_language, zh="风格样本", en="style samples"),
                lambda current: current.model_copy(update={"retrieved_style_samples": []}),
            ),
            (
                "P4",
                "unresolved_foreshadowing",
                localized(
                    pack.output_language,
                    zh="未解决的伏笔",
                    en="unresolved foreshadowing",
                ),
                lambda current: current.model_copy(update={"unresolved_foreshadowing": []}),
            ),
            (
                "P3",
                "relevant_world_rules",
                localized(pack.output_language, zh="世界规则", en="world rules"),
                lambda current: current.model_copy(update={"relevant_world_rules": []}),
            ),
            (
                "P5",
                "previous_scene_summary",
                localized(
                    pack.output_language,
                    zh="上一场景摘要",
                    en="previous scene summary",
                ),
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
                localized(
                    pack.output_language,
                    zh=(
                        f"{priority} 为满足预算已移除{label}；"
                        f"estimated_tokens {before}->{after}"
                    ),
                    en=(
                        f"{priority} dropped {label} to satisfy budget; "
                        f"estimated_tokens {before}->{after}"
                    ),
                )
            )

        final_estimate = self._estimate_tokens(working)
        if final_estimate > target_tokens:
            dropped_items.append(
                localized(
                    pack.output_language,
                    zh=(
                        "受保护的 P0-P2 上下文仍超出目标 "
                        f"{final_estimate - target_tokens} tokens"
                    ),
                    en=(
                        "Protected P0-P2 context still exceeds target by "
                        f"{final_estimate - target_tokens} tokens"
                    ),
                )
            )
        return working.model_copy(
            update={
                "budget": working.budget.model_copy(
                    update={"estimated_tokens": final_estimate, "dropped_items": dropped_items}
                )
            }
        )
